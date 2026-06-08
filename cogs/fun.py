import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.embeds import ghost_embed


_8BALL_RESPONSES = [
    # Positive
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    # Neutral
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    # Negative
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="eightball",
                              description="Ask the magic 8-ball a question",
                              aliases=["8ball"])
    @app_commands.describe(question="Your question for the 8-ball")
    async def eightball(self, ctx, *, question: str):
        response = random.choice(_8BALL_RESPONSES)
        embed = ghost_embed(bot=self.bot)
        embed.add_field(name="🎱 Question", value=question,  inline=False)
        embed.add_field(name="Answer",    value=f"**{response}**", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="coinflip",
                              description="Flip a coin",
                              aliases=["flip", "coin"])
    async def coinflip(self, ctx):
        result = random.choice(["Heads", "Tails"])
        emoji  = "🪙"
        embed  = ghost_embed(
            title=f"{emoji} Coin Flip",
            description=f"It landed on **{result}**!",
            bot=self.bot
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roll", description="Roll a dice (default: 1d6)")
    @app_commands.describe(dice="Dice notation e.g. 1d6, 2d20")
    async def roll(self, ctx, dice: str = "1d6"):
        try:
            parts = dice.lower().split("d")
            count = int(parts[0]) if parts[0] else 1
            sides = int(parts[1])
            if not (1 <= count <= 20 and 2 <= sides <= 1000):
                raise ValueError
        except (ValueError, IndexError):
            from utils.embeds import error_embed
            return await ctx.send(embed=error_embed("Invalid dice notation. Example: `1d6`, `2d20`", bot=self.bot))
        rolls  = [random.randint(1, sides) for _ in range(count)]
        total  = sum(rolls)
        embed  = ghost_embed(
            title=f"🎲 Rolled {dice}",
            description=f"**Results:** {', '.join(str(r) for r in rolls)}\n**Total:** `{total}`",
            bot=self.bot
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
