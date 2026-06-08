import discord
from discord.ext import commands
import time
import json
from database import db


class AntinukeEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_antinuke_cfg(self, guild_id: int) -> dict | None:
        cfg = await db.get_guild_config(str(guild_id))
        if not cfg or not cfg.get("antinuke_enabled"):
            return None
        return cfg

    def _record_action(self, guild_id: int, user_id: int, action: str) -> int:
        now = time.time()
        key = (guild_id, user_id)
        actions = self.bot.antinuke_actions.setdefault(key, [])
        # purge entries older than 10 seconds
        actions = [entry for entry in actions if now - entry["ts"] < 10 and entry["type"] == action]
        actions.append({"type": action, "ts": now})
        self.bot.antinuke_actions[key] = actions
        return len(actions)

    async def _punish(self, guild: discord.Guild, executor: discord.Member | discord.User,
                      cfg: dict, reason: str):
        action = cfg.get("antinuke_punish", "ban").lower()
        try:
            if action == "ban":
                await guild.ban(executor, reason=f"[Antinuke] {reason}", delete_message_days=0)
            elif action == "kick":
                member = guild.get_member(executor.id)
                if member:
                    await member.kick(reason=f"[Antinuke] {reason}")
            elif action == "strip":
                member = guild.get_member(executor.id)
                if member:
                    roles = [r for r in member.roles
                             if not r.managed and r != guild.default_role
                             and r < guild.me.top_role]
                    await member.remove_roles(*roles, reason=f"[Antinuke] {reason}")
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Try to notify in modlog channel
        from utils.modlog import log_action
        if hasattr(executor, 'guild') or guild.get_member(executor.id):
            target = guild.get_member(executor.id) or executor
            try:
                await log_action(guild, "ANTINUKE", target, guild.me, reason)
            except Exception:
                pass

    def _is_whitelisted(self, user_id: int, cfg: dict, guild: discord.Guild) -> bool:
        if user_id == self.bot.user.id:
            return True
        if guild.owner_id == user_id:
            return True
        whitelist = json.loads(cfg.get("antinuke_whitelist") or "[]")
        return str(user_id) in whitelist

    async def _get_executor(self, guild: discord.Guild, action: discord.AuditLogAction) -> discord.Member | None:
        try:
            async for entry in guild.audit_logs(limit=1, action=action):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                    return entry.user
        except discord.Forbidden:
            pass
        return None

    # ── Ban ───────────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.ban)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "ban")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg, f"Mass ban detected ({count} bans in 10s)")

    # ── Channel Delete ────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.channel_delete)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "channel_delete")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg,
                               f"Mass channel delete detected ({count} deletions in 10s)")

    # ── Channel Create ────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.channel_create)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "channel_create")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg,
                               f"Mass channel creation detected ({count} in 10s)")

    # ── Role Create ───────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.role_create)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "role_create")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg,
                               f"Mass role creation detected ({count} in 10s)")

    # ── Role Delete ───────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.role_delete)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "role_delete")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg,
                               f"Mass role deletion detected ({count} in 10s)")

    # ── Kick (via member_remove audit log) ────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        cfg = await self._get_antinuke_cfg(guild.id)
        if not cfg:
            return
        executor = await self._get_executor(guild, discord.AuditLogAction.kick)
        if not executor or self._is_whitelisted(executor.id, cfg, guild):
            return
        count = self._record_action(guild.id, executor.id, "kick")
        if count >= cfg.get("antinuke_threshold", 3):
            await self._punish(guild, executor, cfg,
                               f"Mass kick detected ({count} kicks in 10s)")


async def setup(bot):
    await bot.add_cog(AntinukeEvents(bot))
