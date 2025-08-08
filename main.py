import discord
from discord.ext import commands
import random
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

WELCOME_CHANNEL_NAME = "Everyday Winners"
DEFAULT_ROLE_NAME = "Visitor"
WELCOME_MESSAGE = '''
👋 Welcome to Everyday Winners!

You're one step closer to rebuilding your credit and taking back financial control.

✅ Check #start-here to get started  
📚 Visit the Learning Center for legal education (FCRA, FDCPA, etc.)  
🛠️ Open a ticket if you need help

Let’s win, every day.
'''

@bot.event
async def on_ready():
    print(f"🤖 Bot is online as {bot.user}")

@bot.event
async def on_member_join(member):
    guild = member.guild
    role = discord.utils.get(guild.roles, name=DEFAULT_ROLE_NAME)
    if role:
        await member.add_roles(role)
    try:
        await member.send(WELCOME_MESSAGE)
    except discord.Forbidden:
        print(f"Couldn't DM {member.name}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🔧 Setting up server...")

    role_names = ["Visitor", "Client", "Referral Partner", "Admin", "Bot"]
    for role_name in role_names:
        if not discord.utils.get(ctx.guild.roles, name=role_name):
            await ctx.guild.create_role(name=role_name)

    categories = {
        "📢 WELCOME": ["start-here", "announcements", "faq"],
        "👥 COMMUNITY": ["general-chat", "credit-wins", "ask-a-question"],
        "📚 LEARNING CENTER": [
            "fcra-education", "fdcpa-education", "tila-education", "gila-education",
            "hipaa-education", "tenant-landlord-law", "fcba-education", "credit-hacks"
        ],
        "💳 TRADELINES": ["under-150", "151-300", "301-500", "500-plus", "authorized-users", "business-credit"],
        "🎓 CLIENT ZONE": ["start-here-client", "file-uploads", "dispute-center", "coaching-calls"],
        "🛠️ SUPPORT": ["open-ticket", "bot-help"]
    }

    for cat_name, ch_names in categories.items():
        cat = await ctx.guild.create_category(cat_name)
        for ch in ch_names:
            await ctx.guild.create_text_channel(ch, category=cat)

    await ctx.send("✅ Server setup complete!")

@bot.command()
async def ticket(ctx):
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    category = discord.utils.get(guild.categories, name="🛠️ SUPPORT")
    if not category:
        category = await guild.create_category("🛠️ SUPPORT")

    channel_name = f"ticket-{ctx.author.name}".replace(" ", "-").lower()
    existing = discord.utils.get(category.channels, name=channel_name)
    if existing:
        await ctx.send("❗ You already have an open ticket.")
        return

    ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
    await ticket_channel.send(f"📨 Hello {ctx.author.mention}, welcome to your private support ticket. Type `!close` to close this ticket.")
    await ctx.send(f"✅ Ticket created: {ticket_channel.mention}")

@bot.command()
async def close(ctx):
    if "ticket" in ctx.channel.name:
        await ctx.send("❌ Closing ticket in 5 seconds...")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=5))
        await ctx.channel.delete()
    else:
        await ctx.send("⚠️ This command can only be used inside a ticket channel.")


