import os
import discord
from discord import app_commands
from discord.ext import commands
import requests

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNUSBASE_KEY = os.getenv("SNUSBASE_API_KEY")

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",  # fallback if you ever want to use text commands
            intents=discord.Intents.default(),
            application_id=None,  # Optional: or set your app ID
        )
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

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

async def format_results(term, data):
    if data.get("results"):
        reply = f"**Results for `{term}`:**\n"
        for db, entries in data["results"].items():
            reply += f"\n**{db}**\n"
            for entry in entries:
                reply += "```" + "\n".join(f"{k}: {v}" for k, v in entry.items() if k != "_domain") + "```\n"
        return reply[:2000]  # Discord's message length limit
    else:
        return "No results found, or error occurred."

@bot.tree.command(name="breach", description="Query breach database")
@app_commands.describe(
    type="Type of search (email, username, ip, combo, raw)",
    term="The term to search for (e.g., email, username, IP)"
)
@app_commands.choices(type=[
    app_commands.Choice(name="Email", value="email"),
    app_commands.Choice(name="Username", value="username"),
    app_commands.Choice(name="IP", value="ip"),
    app_commands.Choice(name="Combo", value="combo"),
    app_commands.Choice(name="Raw", value="raw"),
])
async def breach(interaction: discord.Interaction, type: app_commands.Choice[str], term: str):
    """Search breaches by type and term"""
    await interaction.response.defer()
    data = search_snusbase(term, type.value)
    reply = await format_results(term, data)
    await interaction.followup.send(reply)

@bot.tree.command(name="help", description="List bot commands")
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Snusbase Discord Bot `/` Commands:**\n"
        "`/breach type:<type> term:<term>` — Search by email, username, ip, combo, or raw\n"
        "`/help` — Show this message",
        ephemeral=True
    )

bot.run(DISCORD_TOKEN)
