import os
import discord
from discord.ext import commands
import requests

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNUSBASE_KEY = os.getenv("SNUSBASE_API_KEY")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

def search_snusbase(term, search_type):
    url = "https://api.snusbase.com/data/search"
    headers = {"Auth": SNUSBASE_KEY, "Content-Type": "application/json"}
    body = {
        "terms": [term],
        "types": [search_type],
        "size": 5
    }
    r = requests.post(url, headers=headers, json=body)
    try:
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@bot.group()
async def breach(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Usage: `!breach <email|username|ip|combo|raw> <term>`")

@breach.command()
async def email(ctx, *, term):
    await ctx.send(f"Searching for email `{term}`...")
    data = search_snusbase(term, "email")
    await respond(ctx, data, term)

@breach.command()
async def username(ctx, *, term):
    await ctx.send(f"Searching for username `{term}`...")
    data = search_snusbase(term, "username")
    await respond(ctx, data, term)

@breach.command()
async def ip(ctx, *, term):
    await ctx.send(f"Searching for IP `{term}`...")
    data = search_snusbase(term, "ip")
    await respond(ctx, data, term)

@breach.command()
async def combo(ctx, *, term):
    await ctx.send(f"Searching for combo `{term}`...")
    data = search_snusbase(term, "combo")
    await respond(ctx, data, term)

@breach.command()
async def raw(ctx, *, term):
    await ctx.send(f"Running raw query `{term}`...")
    data = search_snusbase(term, "raw")
    await respond(ctx, data, term)

async def respond(ctx, data, term):
    if data.get("results"):
        reply = f"**Results for `{term}`:**\n"
        for db, entries in data["results"].items():
            reply += f"\n**{db}**\n"
            for entry in entries:
                reply += "```" + "\n".join(f"{k}: {v}" for k, v in entry.items() if k != "_domain") + "```\n"
        for chunk in [reply[i:i+2000] for i in range(0, len(reply), 2000)]:
            await ctx.send(chunk)
    else:
        await ctx.send("No results found, or error occurred.")

@bot.command()
async def help(ctx):
    await ctx.send(
        "**Snusbase Discord Bot Commands:**\n"
        "`!breach email <email>` — Search breaches by email\n"
        "`!breach username <username>` — Search breaches by username\n"
        "`!breach ip <ip_address>` — Search breaches by IP\n"
        "`!breach combo <combo>` — Search for combo string\n"
        "`!breach raw <query>` — Raw/experimental query\n"
    )

bot.run(DISCORD_TOKEN)
