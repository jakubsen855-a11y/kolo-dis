import os
import discord
from discord import app_commands
from discord.ext import commands

from kolo import setup_kolo

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix=!, intents=intents)

setup_kolo(bot)

@bot.event
async def on_ready()
    await bot.tree.sync()
    print(fPřihlášen jako {bot.user})

bot.run(TOKEN)