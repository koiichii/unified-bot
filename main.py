import config
import discord
from discord.ext import commands
import asyncio
from utils.database import db

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

async def load_cogs():
    await bot.load_extension('cogs.pokemon')
    print("✅ Загружен ког: pokemon")

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} подключился к Discord!')
    await db.connect()

async def main():
    await load_cogs()
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(main())