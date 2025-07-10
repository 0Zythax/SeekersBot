import discord
from discord.ext import commands

class etc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, context: commands.Context, error: commands.CommandError):
        print(error)
        embed = discord.Embed()
        if isinstance(error, commands.MissingPermissions):
            embed.title = "Missing permissions!"
            embed.description = "You do not have the correct permissions to execute this command."
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "Wait a second!"
            embed.description = f"This command is currently on cooldown ({error.type.name}). Please try again after {error.retry_after} seconds."
        elif isinstance(error, commands.MissingRole):
            embed.title = "Missing permissions!"
            embed.description = "You do not have the correct permissions to execute this command. (role)"
        elif isinstance(error, commands.MissingRequiredArgument):
            embed.title = "Missing arguments."
            embed.description = "This command is missing the necessary arguments to run."
        elif isinstance(error, commands.TooManyArguments):
            embed.title = "Too many arguments."
            embed.description = "You have supplied too many arguments."
        elif isinstance(error, commands.CommandNotFound):
            embed.title = "Command not found."
            embed.description = "Command does not exist."
        else:
            embed.title = "An unexpected error has occured."
            embed.description = error
        await context.send(embed = embed)

def setup(bot : commands.Bot):
    return bot.add_cog(etc(bot))
