# google_worker.py
import os
import re
import html
from urllib.parse import urlparse, parse_qs
from textwrap import shorten

import feedparser
import discord
from discord.ext import commands, tasks

MAX_SUMMARY_CHARS = int(os.getenv("MAX_SUMMARY_CHARS", "300"))

def clean_text(s: str) -> str:
    # HTML entities → text
    s = html.unescape(s or "")
    # strip tags
    s = re.sub(r"<[^>]+>", "", s)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s

def unwrap_google_redirect(link: str) -> str:
    if not link:
        return link
    try:
        if "google.com/url" in link:
            q = parse_qs(urlparse(link).query)
            real = q.get("url") or q.get("q")  # some feeds use ?q=
            if real and isinstance(real, list) and real[0]:
                return real[0]
    except Exception:
        pass
    return link

class AlertsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        raw = os.getenv("CHANNEL_ID", "0")
        if raw.startswith("http"):
            raw = raw.rstrip("/").split("/")[-1]
        self.channel_id = int(raw)
        self.feed_url = os.getenv("RSS_FEED_URL", "https://hnrss.org/newest?points=100")
        self.check_seconds = int(os.getenv("CHECK_INTERVAL", "120"))
        self.sent_links: set[str] = set()
        self.poll_feed.start()

    def cog_unload(self):
        self.poll_feed.cancel()

    @tasks.loop(seconds=60)  # initial; change after first successful run
    async def poll_feed(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("❌ AlertsCog: channel not found. Check CHANNEL_ID & permissions.")
            return

        feed = feedparser.parse(self.feed_url)
        print(f"📰 AlertsCog: fetched {len(feed.entries)} entries")

        for e in feed.entries:
            title = clean_text(getattr(e, "title", "Untitled"))
            summary = clean_text(getattr(e, "summary", "")) or ""
            summary = shorten(summary, width=MAX_SUMMARY_CHARS, placeholder="…")

            link = unwrap_google_redirect(getattr(e, "link", ""))

            if not link or link in self.sent_links:
                continue

            self.sent_links.add(link)

            # send nicely formatted message
            content = f"**{title}**\n{summary}\n{link}"
            try:
                await channel.send(content)
            except Exception as ex:
                print("AlertsCog send error:", ex)

        # after first pass, switch to configured cadence
        self.poll_feed.change_interval(seconds=self.check_seconds)

    @poll_feed.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsCog(bot))
