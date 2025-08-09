# google_worker.py
import os
import feedparser
from discord.ext import commands, tasks
import discord

class AlertsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_id = int(os.getenv("CHANNEL_ID", "0"))
        self.feed_url = os.getenv("RSS_FEED_URL", "https://hnrss.org/newest?points=100")
        self.check_seconds = int(os.getenv("CHECK_INTERVAL", "120"))
        self.sent_links = set()
        # start task after bot is ready
        self.poll_feed.start()

    def cog_unload(self):
        self.poll_feed.cancel()

    @tasks.loop(seconds=60)  # initial interval; we’ll switch after first run
    async def poll_feed(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("❌ AlertsCog: Channel not found. Check CHANNEL_ID & bot perms.")
            return

        feed = feedparser.parse(self.feed_url)
        print(f"📰 AlertsCog: fetched {len(feed.entries)} entries")
        for e in feed.entries:
            link = getattr(e, "link", None)
            title = getattr(e, "title", "Untitled")
            summary = getattr(e, "summary", "")
            if link and link not in self.sent_links:
                self.sent_links.add(link)
                try:
                    await channel.send(f"**{title}**\n{summary}\n{link}")
                except Exception as ex:
                    print("AlertsCog send error:", ex)

        # after first run, switch to configured interval
        self.poll_feed.change_interval(seconds=self.check_seconds)

    @poll_feed.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AlertsCog(bot))
