import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from scrape import scrape_and_group_by_limit
import stripe
import subprocess

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "https://yourapp.onrender.com")

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

    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == "purchase-tradelines":
                try:
                    await channel.send("Click below to view tradelines:", view=TradelineButtons())
                except discord.Forbidden:
                    print(f"Missing permission to send in {channel.name}")
                break

@bot.event
async def on_interaction(interaction: Interaction):
    if interaction.type == discord.InteractionType.component:
        await interaction.response.defer(ephemeral=True)

        buckets, _, _ = scrape_and_group_by_limit()
        mapping = {
            "limit_0_2500": buckets.get("0-2500", []),
            "limit_2501_5000": buckets.get("2501-5000", []),
            "limit_5001_10000": buckets.get("5001-10000", []),
            "limit_10001_plus": buckets.get("10001+", [])
        }
        tradelines = mapping.get(interaction.data['custom_id'], [])[:5]

        if not tradelines:
            await interaction.followup.send("No tradelines found in this range.", ephemeral=True)
            return

        embed = discord.Embed(title="📊 Available Tradelines", color=0x00ff99)
        for t in tradelines:
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": int(t['price'] * 100),
                            "product_data": {
                                "name": f"Tradeline - {t['bank']}",
                                "description": f"Limit ${t['limit']:,} | Opened {t['opened']}",
                            },
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=f"{BASE_DOMAIN}/success",
                    cancel_url=f"{BASE_DOMAIN}/cancel"
                )

                buy_link = session.url
            except Exception as e:
                buy_link = "#"
                print(f"Stripe error for {t['bank']}: {e}")

            embed.add_field(
                name=f"{t['bank']} - ${t['price']:.2f}",
                value=f"💳 Limit: ${t['limit']:,}\n📅 Opened: {t['opened']}\n[Buy Now]({buy_link})",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

subprocess.Popen(["python3", "google.py"])
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
