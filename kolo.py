import random
import asyncio
import discord

KOLO_CHANNEL_NAME = "🎲 KOLO"

active_games = {}  # guild_id -> game data


TIMES = [
    ("1 minuta", 60),
    ("5 minut", 300),
    ("15 minut", 900),
    ("1 hodina", 3600),
    ("1 den", 86400),
    ("3 dny", 259200),
    ("7 dní", 604800),
]


def setup_kolo(bot):

    async def get_or_create_channel(guild):
        channel = discord.utils.get(guild.voice_channels, name=KOLO_CHANNEL_NAME)
        if channel:
            return channel
        return await guild.create_voice_channel(KOLO_CHANNEL_NAME)

    async def force_back(member, channel, game):
        while game["active"]:
            if member.voice is None or member.voice.channel != channel:
                try:
                    await member.move_to(channel)
                except:
                    pass
            await asyncio.sleep(5)

    @bot.tree.command(name="kolo", description="Spustí kolo štěstí")
    async def kolo(interaction: discord.Interaction, member: discord.Member):

        channel = await get_or_create_channel(interaction.guild)

        await interaction.response.send_message(
            f"🎲 {member.mention} hraje Kolo!\nNapiš číslo 1–6.",
        )

        game = {
            "member": member,
            "channel": channel,
            "active": True,
            "winner": None
        }

        active_games[interaction.guild.id] = game

        def check(m):
            return (
                m.guild == interaction.guild
                and m.content in ["1", "2", "3", "4", "5", "6"]
            )

        msg = await bot.wait_for("message", check=check)

        number = int(msg.content)

        time_name, seconds = random.choice(TIMES)

        await interaction.followup.send(
            f"🎯 Padlo číslo **{number}** → trest: **{time_name}**\n"
            f"👉 {member.mention} jde do 🎲 KOLO"
        )

        try:
            await member.move_to(channel)
        except:
            pass

        game["winner"] = member

        task = asyncio.create_task(force_back(member, channel, game))

        await asyncio.sleep(seconds)

        game["active"] = False
        task.cancel()

        await interaction.followup.send(
            f"✅ {member.mention} má konec kola!"
        )