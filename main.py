import discord
from discord.ext import commands
import os
from tradelines import scrape_and_group_by_limit

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

CHANNEL_BUCKET_MAP = {
    "under-2500": "0-2500",
    "2501-5000": "2501-5000",
    "5001-10000": "5001-10000",
    "10001-plus": "10001+"
}

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    bucket_key = CHANNEL_BUCKET_MAP.get(message.channel.name)
    if not bucket_key:
        return

    await message.channel.send("🔄 Fetching tradelines...")

    try:
        buckets, _, _ = scrape_and_group_by_limit()
        tradelines = buckets.get(bucket_key, [])[:5]

        if not tradelines:
            await message.channel.send("⚠️ No tradelines available right now.")
            return

        for t in tradelines:
            embed = discord.Embed(
                title=t['bank'],
                description=t['text'],
                color=discord.Color.blue()
            )
            embed.add_field(name="💰 Buy Now", value=f"[Click to buy](https://yourdomain.com{t['buy_link']})", inline=False)
            await message.channel.send(embed=embed)

    except Exception as e:
        await message.channel.send(f"❌ Error retrieving tradelines: {e}")

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
