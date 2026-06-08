import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import ghost_embed, error_embed, GHOST_COLOR, progress_bar
from database import db


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="rank", description="Show your level and XP progress")
    @commands.guild_only()
    @app_commands.describe(member="Member to check rank for")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data   = await db.get_level_data(str(ctx.guild.id), str(member.id))

        level    = data["level"]
        xp       = data["xp"]
        messages = data["messages"]
        needed   = xp_for_level(level)
        bar      = progress_bar(xp, needed)

        embed = ghost_embed(title=f"⭐ {member.display_name}'s Rank", bot=self.bot)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level",    value=str(level),    inline=True)
        embed.add_field(name="XP",       value=f"{xp}/{needed}", inline=True)
        embed.add_field(name="Messages", value=str(messages), inline=True)
        embed.add_field(name="Progress", value=bar,           inline=False)
        embed.color = member.color if member.color.value else GHOST_COLOR
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show the top members by XP")
    @commands.guild_only()
    async def leaderboard(self, ctx):
        rows = await db.get_leaderboard(str(ctx.guild.id), limit=10)
        if not rows:
            return await ctx.send(embed=error_embed("No XP data yet. Start chatting!", bot=self.bot))

        embed = ghost_embed(title=f"🏆 {ctx.guild.name} — Leaderboard", bot=self.bot)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines  = []
        for i, row in enumerate(rows, 1):
            user = ctx.guild.get_member(int(row["user_id"]))
            name = user.display_name if user else f"<@{row['user_id']}>"
            medal = medals.get(i, f"**#{i}**")
            lines.append(f"{medal} {name} — Level `{row['level']}` · `{row['xp']}` XP")

        embed.description = "\n".join(lines)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Levels(bot))
