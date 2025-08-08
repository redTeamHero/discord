
import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from scrape import scrape_and_group_by_limit

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command(name='tradelines')
async def tradelines(ctx):
    view = View()
    for label in ["0-2500", "2501-5000", "5001-10000", "10001+"]:
        view.add_item(TradelineButton(label))
    await ctx.send("Select a tradeline category:", view=view)

class TradelineButton(Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        buckets, _, _ = scrape_and_group_by_limit()
        tradelines = buckets.get(self.label, [])

        if not tradelines:
            await interaction.response.send_message(f"No tradelines found for {self.label}.", ephemeral=True)
            return

        embeds = []
        for t in tradelines[:5]:  # Limit to first 5 for brevity
            embed = discord.Embed(
                title=f"{t['bank']} - ${t['limit']:,} Limit",
                description=t['text'],
                color=discord.Color.blue()
            )
            embed.add_field(name="Price", value=f"${t['price']}", inline=True)
            embed.set_footer(text="Everyday Winners Tradeline Bot")
            embeds.append(embed)

        for embed in embeds:
            await interaction.channel.send(embed=embed)

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
