import discord
from discord.ext import commands
import random
import time
from database import db


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


class XPEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return

        cfg = await db.get_guild_config(str(message.guild.id))
        prefix = cfg["prefix"] if cfg and cfg.get("prefix") else "-"
        if message.content.startswith(prefix):
            return

        guild_id = str(message.guild.id)
        user_id  = str(message.author.id)
        now      = int(time.time())

        # 60-second cooldown per user per guild
        last = await db.get_xp_cooldown(guild_id, user_id)
        if now - last < 60:
            return

        await db.set_xp_cooldown(guild_id, user_id, now)

        data = await db.get_level_data(guild_id, user_id)
        xp       = data["xp"] + random.randint(15, 25)
        level    = data["level"]
        messages = data["messages"] + 1

        leveled_up = False
        while xp >= xp_for_level(level):
            xp    -= xp_for_level(level)
            level += 1
            leveled_up = True

        await db.update_level_data(guild_id, user_id, xp, level, messages)

        if leveled_up and cfg and cfg.get("level_messages", 1):
            level_channel_id = cfg.get("level_channel")
            channel = (
                message.guild.get_channel(int(level_channel_id))
                if level_channel_id else message.channel
            )
            if channel:
                embed = discord.Embed(
                    description=(
                        f"🎉 {message.author.mention} leveled up to **Level {level}**!"
                    ),
                    color=0xf1c40f
                )
                embed.set_footer(text="👻 Ghost")
                try:
                    await channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass


async def setup(bot):
    await bot.add_cog(XPEvents(bot))
