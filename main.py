# main.py
import os
import math
import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
import stripe
from scrape import scrape_and_group_by_limit
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "https://yourapp.onrender.com")
DISCORD_MAIN_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- Cache (auto-refresh every 30 min) ----------------
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

# run one immediate refresh before the loop cadence applies
@refresh_tradelines_cache.before_loop
async def _before_refresh():
    try:
        buckets, banks, _years = scrape_and_group_by_limit()
        global CACHE_ITEMS, CACHE_BANKS
        CACHE_ITEMS = _flatten(buckets)
        CACHE_BANKS = banks[:]
        print(f"[tradelines] initial cache: {len(CACHE_ITEMS)} items / {len(CACHE_BANKS)} banks")
    except Exception as e:
        print("[tradelines] initial cache error:", e)

# ---------------- Filters ----------------
def _year_ok(year_filter: str, opened: str) -> bool:
    if year_filter == "any":
        return True
    try:
        y = int((opened or "").split()[0])
    except Exception:
        return False
    ranges = {
        "pre-2016": lambda v: v <= 2015,
        "2016-2019": lambda v: 2016 <= v <= 2019,
        "2020-2022": lambda v: 2020 <= v <= 2022,
        "2023-2024": lambda v: 2023 <= v <= 2024,
        "2025":      lambda v: v == 2025,
    }
    return ranges[year_filter](y)

def _price_ok(price_filter: str, price: float) -> bool:
    if price_filter == "any": return True
    if price_filter == "<500": return price < 500
    if price_filter == "500-1000": return 500 <= price <= 1000
    if price_filter == "1000-2000": return 1000 < price <= 2000
    if price_filter == "2000+": return price > 2000
    return True

def _limit_ok(limit_filter: str, limit: int) -> bool:
    if limit_filter == "any": return True
    if limit_filter == "<=2500": return limit <= 2500
    if limit_filter == "2501-5000": return 2501 <= limit <= 5000
    if limit_filter == "5001-10000": return 5001 <= limit <= 10000
    if limit_filter == "10001+": return limit >= 10001
    return True

def filter_items(bank: str, year_filter: str, price_filter: str, limit_filter: str) -> list[dict]:
    return [
        t for t in CACHE_ITEMS
        if (t.get("bank") == bank)
        and _year_ok(year_filter, t.get("opened",""))
        and _price_ok(price_filter, float(t.get("price", 0)))
        and _limit_ok(limit_filter, int(t.get("limit", 0)))
    ]

# ---------------- Views ----------------
class BankPicker(discord.ui.View):
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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            f"Filters for **{bank}** — pick then press **Show Results**:",
            view=FilterView(bank),
            ephemeral=True
        )

class FilterView(discord.ui.View):
    def __init__(self, bank: str):
        super().__init__(timeout=180)
        self.bank = bank

        self.year = discord.ui.Select(
            placeholder="Age (Opened Year)",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Any", value="any", default=True),
                discord.SelectOption(label="Pre-2016", value="pre-2016"),
                discord.SelectOption(label="2016–2019", value="2016-2019"),
                discord.SelectOption(label="2020–2022", value="2020-2022"),
                discord.SelectOption(label="2023–2024", value="2023-2024"),
                discord.SelectOption(label="2025", value="2025"),
            ],
        )
        self.price = discord.ui.Select(
            placeholder="Price",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Any", value="any", default=True),
                discord.SelectOption(label="< $500", value="<500"),
                discord.SelectOption(label="$500 – $1,000", value="500-1000"),
                discord.SelectOption(label="$1,000 – $2,000", value="1000-2000"),
                discord.SelectOption(label="$2,000+", value="2000+"),
            ],
        )
        self.limit = discord.ui.Select(
            placeholder="Credit Limit",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Any", value="any", default=True),
                discord.SelectOption(label="≤ $2,500", value="<=2500"),
                discord.SelectOption(label="$2,501 – $5,000", value="2501-5000"),
                discord.SelectOption(label="$5,001 – $10,000", value="5001-10000"),
                discord.SelectOption(label="$10,001+", value="10001+"),
            ],
        )

        self.add_item(self.year)
        self.add_item(self.price)
        self.add_item(self.limit)
        self.add_item(self.ShowButton(self))

    class ShowButton(discord.ui.Button):
        def __init__(self, parent: "FilterView"):
            super().__init__(label="Show Results", style=discord.ButtonStyle.primary)
            self.parent = parent

        async def callback(self, interaction: Interaction):
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            y = self.parent.year.values[0]
            p = self.parent.price.values[0]
            l = self.parent.limit.values[0]
            results = filter_items(self.parent.bank, y, p, l)
            if not results:
                await interaction.followup.send("No matches. Try different filters.", ephemeral=True)
                return
            pager = ResultPager(results)
            await pager.send_first(interaction)

class ResultPager(discord.ui.View):
    def __init__(self, items: list[dict], page_size: int = 5):
        super().__init__(timeout=300)
        self.items = items
        self.page_size = page_size
        self.page = 0

    def _page_slice(self):
        start = self.page * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def _total_pages(self):
        return max(1, math.ceil(len(self.items) / self.page_size))

    def _build_embed(self):
        embed = discord.Embed(
            title=f"📊 Tradelines ({self.page+1}/{self._total_pages()})",
            color=0x00FF99
        )
        # Build Stripe links for current page
        for t in self._page_slice():
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
                value=f"💳 Limit: ${int(t.get('limit',0)):,}\n📅 Opened: {t.get('opened')}\n[Buy Now]({buy_link})",
                inline=False,
            )
        return embed

    async def send_first(self, interaction: Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=self._build_embed(), view=self, ephemeral=True)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, _, interaction: Interaction):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self._total_pages() - 1
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, _, interaction: Interaction):
        if self.page < self._total_pages() - 1:
            self.page += 1
        else:
            self.page = 0
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

# ---------------- Events (minimal changes) ----------------
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print("Sync error:", e)

    # Post a single “start” message in the channel
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == "purchase-tradelines":
                try:
                    await channel.send("Pick a **Bank** to explore tradelines:", view=BankPicker())
                except discord.Forbidden:
                    print(f"Missing permission to send in {channel.name}")
                break

@bot.event
async def setup_hook():
    # start the 30-min cache refresher
    refresh_tradelines_cache.start()
    # keep your alerts cog
    from google_worker import setup as setup_alerts
    await setup_alerts(bot)

if __name__ == "__main__":
    if not DISCORD_MAIN_TOKEN:
        raise SystemExit("Set DISCORD_BOT_TOKEN in env.")
    bot.run(DISCORD_MAIN_TOKEN)
