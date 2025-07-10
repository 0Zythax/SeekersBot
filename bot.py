import discord, os, asyncio
from discord.ext import commands
from dotenv import load_dotenv

bot = commands.Bot(intents = discord.Intents.all(), command_prefix = "!", help_command=None)

async def main():
    print(r"""
                   __        _ 
      ___ ___ ___ / /_____ _(_)
     (_-</ -_) -_)  '_/ _ `/ / 
    /___/\__/\__/_/\_\\_,_/_/  
                           
    brought to you by yours truly
    0Zythax/Zythax
    """)
    
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            print(f"init cog {filename[:-3]}")
            await bot.load_extension(f"cogs.{filename[:-3]}")
    await bot.start(os.getenv("TOKEN"))

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main=main())