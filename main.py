import os
from dotenv import load_dotenv
from discord.ext import commands
import discord

current_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_path)
load_dotenv()

token = os.getenv("DISCORD_TOKEN")

# bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
print(bot.command_prefix)


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    await bot.load_extension("cogs.RebuildCommand")
    await bot.load_extension("cogs.BotControlCommand")


@bot.event
async def on_command_error(ctx, error):
    print(error)
    await ctx.send("Error: " + str(error))


bot.run(token)
