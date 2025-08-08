import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from scrape import scrape_and_group_by_limit

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class TradelineButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(label="Under $2500", style=discord.ButtonStyle.primary, custom_id="limit_0_2500"))
        self.add_item(discord.ui.Button(label="$2501–$5000", style=discord.ButtonStyle.primary, custom_id="limit_2501_5000"))
        self.add_item(discord.ui.Button(label="$5001–$10000", style=discord.ButtonStyle.primary, custom_id="limit_5001_10000"))
        self.add_item(discord.ui.Button(label="$10,001+", style=discord.ButtonStyle.primary, custom_id="limit_10001_plus"))

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)

    # Send the buttons only if in the right channel
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == "purchase-tradelines":
                await channel.send("Click below to view tradelines:", view=TradelineButtons())

@bot.event
async def on_interaction(interaction: Interaction):
    if interaction.type == discord.InteractionType.component:
        buckets, _, _ = scrape_and_group_by_limit()
        mapping = {
            "limit_0_2500": buckets.get("0-2500", []),
            "limit_2501_5000": buckets.get("2501-5000", []),
            "limit_5001_10000": buckets.get("5001-10000", []),
            "limit_10001_plus": buckets.get("10001+", [])
        }
        tradelines = mapping.get(interaction.data['custom_id'], [])[:5]  # Limit to 5 entries per response

        if not tradelines:
            await interaction.response.send_message("No tradelines found in this range.", ephemeral=True)
            return

        embed = discord.Embed(title="📊 Available Tradelines", color=0x00ff99)
        for t in tradelines:
            embed.add_field(
                name=f"{t['bank']} - ${t['price']:.2f}",
                value=f"💳 Limit: ${t['limit']:,}\n📅 Opened: {t['opened']}\n[Buy Now]({t.get('buy_link', '#')})",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
