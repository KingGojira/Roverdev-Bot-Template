import discord
from discord.ext import commands
import time
from database import db


class MemberEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _render_message(self, template: str, member: discord.Member) -> str:
        return (template
                .replace("{mention}", member.mention)
                .replace("{user}",    str(member))
                .replace("{server}",  member.guild.name)
                .replace("{memberCount}", str(member.guild.member_count)))

    # ── Member Join ───────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        cfg   = await db.ensure_guild_config(str(guild.id))

        # ── Antiraid check ────────────────────────────────────────────────────
        if cfg.get("antiraid_enabled"):
            now = time.time()
            tracker = self.bot.join_tracker.setdefault(guild.id, [])
            tracker.append(now)
            self.bot.join_tracker[guild.id] = [t for t in tracker if now - t < 5]

            threshold = cfg.get("antiraid_threshold", 7)
            if len(self.bot.join_tracker[guild.id]) >= threshold:
                self.bot.raid_mode[guild.id] = now + 30  # raid mode for 30s

            in_raid = self.bot.raid_mode.get(guild.id, 0) > now

            if in_raid or cfg.get("antiraid_min_age") or cfg.get("antiraid_no_avatar"):
                age_days = (discord.utils.utcnow() - member.created_at).days
                min_age  = cfg.get("antiraid_min_age", 0)
                no_avatar = cfg.get("antiraid_no_avatar", 0)
                no_av_flag = member.avatar is None

                should_kick = (in_raid and age_days < min_age) or (no_avatar and no_av_flag)
                if should_kick:
                    try:
                        await member.kick(reason="[Antiraid] Suspicious account")
                    except discord.Forbidden:
                        pass
                    return

        # ── Autorole ──────────────────────────────────────────────────────────
        if cfg.get("autorole"):
            role = guild.get_role(int(cfg["autorole"]))
            if role and role < guild.me.top_role:
                try:
                    await member.add_roles(role, reason="Autorole on join")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ── Welcome message ───────────────────────────────────────────────────
        if cfg.get("welcome_channel"):
            channel = guild.get_channel(int(cfg["welcome_channel"]))
            if channel:
                msg = self._render_message(
                    cfg.get("welcome_message",
                            "Welcome {mention} to **{server}**! You are member #{memberCount}."),
                    member
                )
                embed = discord.Embed(description=msg, color=0x57f287)
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text="👻 Ghost")
                try:
                    await channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    # ── Member Remove ─────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        cfg   = await db.get_guild_config(str(guild.id))
        if not cfg:
            return

        # ── Goodbye message ───────────────────────────────────────────────────
        if cfg.get("goodbye_channel"):
            channel = guild.get_channel(int(cfg["goodbye_channel"]))
            if channel:
                msg = self._render_message(
                    cfg.get("goodbye_message", "**{user}** has left **{server}**."),
                    member
                )
                embed = discord.Embed(description=msg, color=0xe74c3c)
                embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                embed.set_footer(text="👻 Ghost")
                try:
                    await channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass


async def setup(bot):
    await bot.add_cog(MemberEvents(bot))
