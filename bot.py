import os
import tempfile
import discord
from discord import app_commands
from discord.ext import commands
import requests
import asyncio
import csv

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNUSBASE_KEY = os.getenv("SNUSBASE_API_KEY")

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.default(),
            application_id=None,
        )

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

def search_snusbase(term, search_type, from_offset=0, size=100, table=None):
    url = "https://api.snusbase.com/data/search"
    headers = {"Auth": SNUSBASE_KEY, "Content-Type": "application/json"}
    body = {
        "terms": [term] if term else [],
        "types": [search_type],
        "size": size,
        "from": from_offset
    }
    if table:
        body["tables"] = [table]
    r = requests.post(url, headers=headers, json=body)
    try:
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def listdbs_snusbase():
    # Returns a list of all breach db names
    url = "https://api.snusbase.com/data/metadata"
    headers = {"Auth": SNUSBASE_KEY}
    r = requests.get(url, headers=headers)
    try:
        return r.json().get("tables", [])
    except Exception as e:
        return []

def upload_anonfiles(filepath):
    url = 'https://api.anonfiles.com/upload'
    with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f)}
        r = requests.post(url, files=files)
    try:
        return r.json()["data"]["file"]["url"]["full"]
    except Exception:
        return None

def entries_to_csv(entries, filename):
    # entries: list of dicts
    fieldnames = set()
    for entry in entries:
        fieldnames.update(entry.keys())
    fieldnames = [k for k in fieldnames if k != "_domain"]
    with open(filename, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for entry in entries:
            entry2 = {k: v for k, v in entry.items() if k != "_domain"}
            writer.writerow(entry2)

@bot.tree.command(name="listdbs", description="List all available breach databases")
async def listdbs(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    dbs = listdbs_snusbase()
    if not dbs:
        await interaction.followup.send("No database list found.")
        return
    chunks = [dbs[i:i+50] for i in range(0, len(dbs), 50)]
    for chunk in chunks:
        await interaction.followup.send("\n".join(chunk))

@bot.tree.command(name="dumpdb", description="Dump an entire breach database as txt or csv")
@app_commands.describe(
    dbname="Exact database name (see /listdbs)",
    format="File format: txt or csv (default: txt)"
)
@app_commands.choices(format=[
    app_commands.Choice(name="txt", value="txt"),
    app_commands.Choice(name="csv", value="csv"),
])
async def dumpdb(interaction: discord.Interaction, dbname: str, format: app_commands.Choice[str]=None):
    await interaction.response.defer(thinking=True)

    results = []
    size = 100
    offset = 0
    total = 0
    while True:
        data = search_snusbase(term="", search_type="raw", from_offset=offset, size=size, table=dbname)
        found = False
        if data.get("results") and dbname in data["results"]:
            entries = data["results"][dbname]
            if entries:
                results.extend(entries)
                found = True
        if not found or (data.get("error")):
            break
        if len(entries) < size:
            break
        offset += size
        await asyncio.sleep(0.4)
    if not results:
        await interaction.followup.send(f"No results found for DB `{dbname}`.")
        return

    # Write to file
    suffix = ".csv" if format and format.value == "csv" else ".txt"
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=suffix, encoding="utf-8") as tmpf:
        filename = tmpf.name
        if suffix == ".csv":
            entries_to_csv(results, filename)
        else:
            tmpf.write("\n\n---\n\n".join(
                "\n".join(f"{k}: {v}" for k, v in entry.items() if k != "_domain") for entry in results))
            tmpf.flush()
            tmpf.seek(0)

    # Check file size
    filesize = os.path.getsize(filename)
    max_discord_size = 24 * 1024 * 1024  # 24 MB
    if filesize > max_discord_size:
        url = upload_anonfiles(filename)
        if url:
            await interaction.followup.send(
                f"File was too large for Discord ({filesize//1024//1024}MB). Uploaded to anonfiles:\n{url}")
        else:
            await interaction.followup.send(
                f"File is too large for Discord and anonfiles upload failed. Check your filters.")
        os.remove(filename)
    else:
        await interaction.followup.send(
            f"Full dump for `{dbname}` ({len(results)} records).",
            file=discord.File(filename, filename=f"{dbname}_dump{suffix}")
        )
        os.remove(filename)

@bot.tree.command(name="dump", description="Dump breach search results as txt or csv")
@app_commands.describe(
    type="Type of search (email, username, ip, combo, raw)",
    term="The term to search for",
    format="File format: txt or csv (default: txt)"
)
@app_commands.choices(type=[
    app_commands.Choice(name="Email", value="email"),
    app_commands.Choice(name="Username", value="username"),
    app_commands.Choice(name="IP", value="ip"),
    app_commands.Choice(name="Combo", value="combo"),
    app_commands.Choice(name="Raw", value="raw"),
])
@app_commands.choices(format=[
    app_commands.Choice(name="txt", value="txt"),
    app_commands.Choice(name="csv", value="csv"),
])
async def dump(interaction: discord.Interaction, type: app_commands.Choice[str], term: str, format: app_commands.Choice[str]=None):
    await interaction.response.defer(thinking=True)
    results = []
    size = 100
    offset = 0
    while True:
        data = search_snusbase(term, type.value, from_offset=offset, size=size)
        found = False
        if data.get("results"):
            for db, entries in data["results"].items():
                if entries:
                    results.extend(entries)
                    found = True
        if not found or (data.get("error")):
            break
        if all(len(entries) < size for entries in data["results"].values()):
            break
        offset += size
        await asyncio.sleep(0.4)

    if not results:
        await interaction.followup.send("No results found.")
        return

    suffix = ".csv" if format and format.value == "csv" else ".txt"
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=suffix, encoding="utf-8") as tmpf:
        filename = tmpf.name
        if suffix == ".csv":
            entries_to_csv(results, filename)
        else:
            tmpf.write("\n\n---\n\n".join(
                "\n".join(f"{k}: {v}" for k, v in entry.items() if k != "_domain") for entry in results))
            tmpf.flush()
            tmpf.seek(0)

    filesize = os.path.getsize(filename)
    max_discord_size = 24 * 1024 * 1024
    if filesize > max_discord_size:
        url = upload_anonfiles(filename)
        if url:
            await interaction.followup.send(
                f"File too large for Discord ({filesize//1024//1024}MB). Uploaded to anonfiles:\n{url}")
        else:
            await interaction.followup.send(
                f"File too large for Discord and anonfiles upload failed. Try smaller queries.")
        os.remove(filename)
    else:
        await interaction.followup.send(
            f"Dumped {len(results)} records for `{term}`.",
            file=discord.File(filename, filename=f"snusbase_dump_{term.replace('@','at').replace('.','dot')}{suffix}")
        )
        os.remove(filename)

@bot.tree.command(name="help", description="List bot commands")
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Snusbase Discord Bot `/` Commands:**\n"
        "`/breach type:<type> term:<term>` — Search by email, username, ip, combo, or raw\n"
        "`/dump type:<type> term:<term> [format:csv]` — Dump full search as .txt or .csv\n"
        "`/dumpdb dbname:<table> [format:csv]` — Dump ALL records in a breach table\n"
        "`/listdbs` — List all available DBs for dumping\n"
        "`/help` — Show this message",
        ephemeral=True
    )

bot.run(DISCORD_TOKEN)
