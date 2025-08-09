import os
import math
import discord
from discord.ext import commands, tasks
from discord import Interaction
import stripe
from scrape import scrape_and_group_by_limit
from dotenv import load_dotenv

load_dotenv()

# ---- ENV ----
stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "https://yourapp.onrender.com")
DISCORD_MAIN_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ---- BOT ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- CACHE (auto-refresh every 30 min) ----
CACHE_ITEMS: list[dict] = []
CACHE_BANKS: list[str] = []

def _flatten(buckets: dict) -> list[dict]:
    return [t for b in buckets.values() for t in b]

@tasks.loop(seconds=1800)  # 30 minutes
async def refresh_tradelines_cache():
    try:
        buckets, banks, _years = scrape_and_group_by_limit()
        global CACHE_ITEMS, CACHE_BANKS
        CACHE_ITEMS = _flatten(buckets)
        CACHE_BANKS = banks[:]
        print(f"[tradelines] cache refreshed: {len(CACHE_ITEMS)} items / {len(CACHE_BANKS)} banks")
    except Exception as e:
        print("[tradelines] cache refresh error:", e)

@refresh_tradelines_cache.before_loop
async def _before_refresh():
    # Run once immediately so the UI has data before the loop cadence
    try:
        buckets, banks, _years = scrape_and_group_by_limit()
        global CACHE_ITEMS, CACHE_BANKS
        CACHE_ITEMS = _flatten(buckets)
        CACHE_BANKS = banks[:]
        print(f"[tradelines] initial cache: {len(CACHE_ITEMS)} items / {len(CACHE_BANKS)} banks")
    except Exception as e:
        print("[tradelines] initial cache error:", e)

# ---- VIEWS ----
class BankPicker(discord.ui.View):
    """Dropdown of banks (max 25 due to Discord limit). After picking, opens pager."""
    def __init__(self):
        super().__init__(timeout=180)
        banks = (CACHE_BANKS or [])[:25] or ["(none)"]
        self.select = discord.ui.Select(
            placeholder="Select a Bank",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=b, value=b) for b in banks]
        )
        self.select.callback = self._chosen
        self.add_item(self.select)

    async def _chosen(self, interaction: Interaction):
        bank = self.select.values[0]
        items = [t for t in CACHE_ITEMS if t.get("bank") == bank]
        if not items:
            await interaction.response.send_message(
                f"No tradelines found for **{bank}**.", ephemeral=True
            )
            return

        pager = BankResultPager(bank, items, page_size=5)
        await interaction.response.send_message(
            embed=pager._build_embed(), view=pager, ephemeral=True
        )

class BankResultPager(discord.ui.View):
    """Shows 5 items at a time with Prev / Next and Back to bank picker."""
    def __init__(self, bank: str, items: list[dict], page_size: int = 5):
        super().__init__(timeout=300)
        self.bank = bank
        self.items = items
        self.page_size = page_size
        self.page = 0

    def _slice(self):
        start = self.page * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def _pages(self):
        return max(1, math.ceil(len(self.items) / self.page_size))

    def _build_embed(self):
        embed = discord.Embed(
            title=f"📊 {self.bank} Tradelines ({self.page+1}/{self._pages()})",
            color=0x00FF99
        )
        # Build up to 5 items for this page
        for t in self._slice():
            # Create a Stripe Checkout link per item on this page
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": int(float(t["price"]) * 100),
                            "product_data": {
                                "name": f"Tradeline - {t['bank']}",
                                "description": f"Limit ${int(t['limit']):,} | Opened {t['opened']}",
                            },
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=f"{BASE_DOMAIN}/success",
                    cancel_url=f"{BASE_DOMAIN}/cancel",
                )
                buy_link = session.url
            except Exception as e:
                print(f"Stripe error for {t.get('bank')}: {e}")
                buy_link = "#"

            embed.add_field(
                name=f"{t.get('bank')} - ${float(t.get('price',0)):.2f}",
                value=(
                    f"💳 Limit: ${int(t.get('limit',0)):,}\n"
                    f"📅 Opened: {t.get('opened')}\n"
                    f"[Buy Now]({buy_link})"
                ),
                inline=False,
            )
        return embed

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, _, interaction: Interaction):
        self.page = (self.page - 1) % self._pages()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, _, interaction: Interaction):
        self.page = (self.page + 1) % self._pages()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, _, interaction: Interaction):
        picker = BankPicker()
        await interaction.response.edit_message(
            content="Pick a **Bank** to explore tradelines:",
            embed=None,
            view=picker
        )

# ---- EVENTS ----
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print("Sync error:", e)

    # Post the starting message once in your channel
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == "purchase-tradelines":
                try:
                    await channel.send(
                        "Pick a **Bank** to explore tradelines:",
                        view=BankPicker()
                    )
                except discord.Forbidden:
                    print(f"Missing permission to send in {channel.name}")
                break

@bot.event
async def setup_hook():
    # start the 30-min cache refresher
    refresh_tradelines_cache.start()
    # load your Google Alerts worker extension
    # (make sure file is named google_worker.py with async setup(bot))
    await bot.load_extension("google_worker")

# ---- RUN ----
if __name__ == "__main__":
    if not DISCORD_MAIN_TOKEN:
        raise SystemExit("Set DISCORD_BOT_TOKEN in env.")
    bot.run(DISCORD_MAIN_TOKEN)
