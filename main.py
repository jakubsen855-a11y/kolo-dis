import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import asyncio
import random
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv


# =========================
# KONFIGURACE
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("Chybí DISCORD_TOKEN v Environment Variables")


INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True


bot = commands.Bot(
    command_prefix="!",
    intents=INTENTS
)


# =========================
# DATABASE SQLITE
# =========================

db = sqlite3.connect("kolo.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS punishments (
    user_id INTEGER PRIMARY KEY,
    guild_id INTEGER,
    end_time TEXT,
    voice_id INTEGER,
    created_by INTEGER
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    voice_id INTEGER
)
""")


db.commit()



# =========================
# TRESTY
# =========================


TIMES = [
    ("1 minuta", 60),
    ("5 minut", 300),
    ("10 minut", 600),
    ("30 minut", 1800),
    ("1 hodina", 3600),
    ("6 hodin", 21600),
    ("12 hodin", 43200),
    ("1 den", 86400),
    ("2 dny", 172800),
    ("3 dny", 259200),
    ("5 dní", 432000),
    ("7 dní", 604800),
]


active_games = {}



# =========================
# READY
# =========================


@bot.event
async def on_ready():

    print("--------------------------------")
    print(f"Bot online: {bot.user}")
    print("--------------------------------")


    try:
        synced = await bot.tree.sync()
        print(f"Slash příkazy: {len(synced)}")
    except Exception as e:
        print(e)


    check_punishments.start()



# =========================
# EMBED
# =========================


def embed(title, text, color=0x5865F2):

    e = discord.Embed(
        title=title,
        description=text,
        color=color,
        timestamp=datetime.utcnow()
    )

    return e



# =========================
# SET VOICE
# =========================


@bot.tree.command(
    name="setvoice",
    description="Nastaví voice kanál pro KOLO"
)
async def setvoice(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Nemáš práva.",
            ephemeral=True
        )
        return


    if not interaction.user.voice:

        await interaction.response.send_message(
            "❌ Musíš být ve voice kanálu.",
            ephemeral=True
        )
        return


    channel = interaction.user.voice.channel


    cursor.execute(
        """
        INSERT OR REPLACE INTO settings
        VALUES (?,?)
        """,
        (
            interaction.guild.id,
            channel.id
        )
    )

    db.commit()


    await interaction.response.send_message(

        embed=embed(
            "🔊 Voice nastaven",
            f"KOLO bude používat:\n{channel.mention}"
        )

    )



# =========================
# KOLO
# =========================


@bot.tree.command(
    name="kolo",
    description="Spustí kolo trestu"
)
@app_commands.describe(
    hrac="Hráč který dostane trest"
)
async def kolo(
    interaction: discord.Interaction,
    hrac: discord.Member
):


    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(
            "❌ Nemáš práva.",
            ephemeral=True
        )

        return



    if hrac.id in active_games:

        await interaction.response.send_message(
            "❌ Tento hráč už má aktivní trest.",
            ephemeral=True
        )

        return



    cursor.execute(
        "SELECT voice_id FROM settings WHERE guild_id=?",
        (interaction.guild.id,)
    )

    data = cursor.fetchone()


    if not data:

        await interaction.response.send_message(
            "❌ Nejprve nastav voice pomocí /setvoice",
            ephemeral=True
        )

        return



    active_games[hrac.id] = {

        "guild": interaction.guild.id,
        "starter": interaction.user.id

    }



    await interaction.response.send_message(

        embed=embed(
            "🎲 KOLO ŠTĚSTÍ",
            f"""
Hráč:
{hrac.mention}

Napište číslo **1-6**
"""
        )

    )



    def check(message):

        return (
            message.channel == interaction.channel
            and message.author != bot.user
            and message.content.isdigit()
            and 1 <= int(message.content) <= 6
        )


    try:

        msg = await bot.wait_for(
            "message",
            timeout=60,
            check=check
        )


    except asyncio.TimeoutError:


        active_games.pop(hrac.id,None)


        await interaction.followup.send(

            embed=embed(
                "⌛ Čas vypršel",
                "Nikdo nehádal číslo."
            )

        )

        return



    punishment = random.choice(TIMES)


    end = datetime.utcnow() + timedelta(
        seconds=punishment[1]
    )


    cursor.execute(
        """
        INSERT OR REPLACE INTO punishments
        VALUES (?,?,?,?,?)
        """,
        (
            hrac.id,
            interaction.guild.id,
            end.isoformat(),
            data[0],
            interaction.user.id
        )
    )

    db.commit()



    await interaction.followup.send(

        embed=embed(
            "🎯 TREST",
            f"""
Číslo:
**{msg.content}**

Hráč:
{hrac.mention}

Doba:
⏰ **{punishment[0]}**
"""
        )

    )


    voice = interaction.guild.get_channel(data[0])


    if voice:

        try:

            await hrac.move_to(voice)

        except Exception as e:

            print(e)


# =========================
# KONTROLA TRESTŮ
# =========================


@tasks.loop(seconds=10)
async def check_punishments():

    now = datetime.utcnow()


    cursor.execute(
        "SELECT * FROM punishments"
    )

    rows = cursor.fetchall()


    for row in rows:

        user_id = row[0]
        guild_id = row[1]
        end_time = datetime.fromisoformat(row[2])
        voice_id = row[3]


        guild = bot.get_guild(guild_id)

        if not guild:
            continue


        member = guild.get_member(user_id)

        if not member:
            continue



        # konec trestu

        if now >= end_time:


            cursor.execute(
                "DELETE FROM punishments WHERE user_id=?",
                (user_id,)
            )

            db.commit()


            try:

                await member.move_to(None)


            except:

                pass


            try:

                await member.send(

                    embed=embed(
                        "✅ Trest skončil",
                        "Tvůj trest z KOLO byl ukončen."
                    )

                )

            except:

                pass


            continue




        # kontrola voice útěku

        if member.voice is None:


            channel = guild.get_channel(
                voice_id
            )


            if channel:

                try:

                    await member.move_to(channel)


                    log = guild.system_channel


                    if log:

                        await log.send(

                            embed=embed(
                                "🔒 Návrat hráče",
                                f"{member.mention} opustil voice.\nBot ho vrátil."
                            )

                        )

                except Exception as e:

                    print(
                        "VOICE ERROR:",
                        e
                    )




# =========================
# STOP KOLO
# =========================


@bot.tree.command(
    name="stopkolo",
    description="Ukončí trest hráče"
)
@app_commands.describe(
    hrac="Hráč kterému zrušit trest"
)
async def stopkolo(
    interaction: discord.Interaction,
    hrac: discord.Member
):


    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(
            "❌ Nemáš práva.",
            ephemeral=True
        )

        return



    cursor.execute(

        "DELETE FROM punishments WHERE user_id=?",

        (hrac.id,)

    )

    db.commit()



    active_games.pop(
        hrac.id,
        None
    )


    await interaction.response.send_message(

        embed=embed(
            "🛑 Trest zrušen",
            f"{hrac.mention} už nemá trest."
        )

    )



# =========================
# STATUS
# =========================


@bot.tree.command(
    name="status",
    description="Ukáže stav trestu"
)
@app_commands.describe(
    hrac="Hráč"
)
async def status(
    interaction: discord.Interaction,
    hrac: discord.Member
):


    cursor.execute(

        "SELECT end_time FROM punishments WHERE user_id=?",

        (hrac.id,)

    )


    data = cursor.fetchone()



    if not data:


        await interaction.response.send_message(

            "❌ Tento hráč nemá aktivní trest.",

            ephemeral=True

        )

        return



    end = datetime.fromisoformat(
        data[0]
    )


    remaining = end - datetime.utcnow()



    await interaction.response.send_message(

        embed=embed(
            "🎲 Stav trestu",

            f"""
Hráč:
{hrac.mention}

Končí:
{end.strftime("%d.%m.%Y %H:%M")}

Zbývá:
{remaining}
"""
        )

    )



# =========================
# LIST TRESTŮ
# =========================


@bot.tree.command(
    name="list",
    description="Seznam aktivních trestů"
)
async def list(interaction: discord.Interaction):


    cursor.execute(
        "SELECT user_id,end_time FROM punishments"
    )


    rows = cursor.fetchall()



    if not rows:


        await interaction.response.send_message(
            "✅ Žádné aktivní tresty."
        )

        return



    text = ""


    for row in rows:


        member = interaction.guild.get_member(
            row[0]
        )


        if member:

            text += (
                f"{member.mention} "
                f"- {row[1][:16]}\n"
            )



    await interaction.response.send_message(

        embed=embed(
            "🎲 Aktivní tresty",
            text
        )

    )



# =========================
# SHUTDOWN
# =========================


@bot.tree.command(
    name="shutdown",
    description="Vypne bota"
)
async def shutdown(
    interaction: discord.Interaction
):


    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(
            "❌ Nemáš práva.",
            ephemeral=True
        )

        return



    await interaction.response.send_message(

        embed=embed(
            "⚠️ Shutdown",
            "Bot se vypíná..."
        )

    )


    await bot.close()



# =========================
# SPUŠTĚNÍ
# =========================


bot.run(TOKEN)