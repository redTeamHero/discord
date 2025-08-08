# google_alerts_bot.py

import feedparser
import discord
import asyncio
import time
import os

# -------- CONFIG --------
RSS_FEED_URL = 'https://www.google.com/alerts/feeds/15905049311287711625/8527519402525634190'  # Replace with your actual feed
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # Set this in your environment or .env file
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '1403391784356155615'))  # Replace with your channel ID or use .env
CHECK_INTERVAL = 10  # In seconds
# ------------------------

intents = discord.Intents.default()
client = discord.Client(intents=intents)
sent_links = set()

async def check_alerts():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Channel not found! Check CHANNEL_ID.")
        return

    print(f"✅ Monitoring Google Alerts for: {RSS_FEED_URL}")

    while not client.is_closed():
        feed = feedparser.parse(RSS_FEED_URL)
        for entry in feed.entries:
            if entry.link not in sent_links:
                sent_links.add(entry.link)
                title = entry.title
                link = entry.link
                summary = entry.get('summary', '')

                message = f"**{title}**\n{summary}\n{link}"
                await channel.send(message)

        await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f'🤖 Logged in as {client.user}')

client.loop.create_task(check_alerts())
client.run(DISCORD_TOKEN)
