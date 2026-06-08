import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time as _time
from utils.embeds import success_embed, error_embed, ghost_embed
from utils.modlog import log_action
from utils.time_parser import parse_time, format_time
from database import db


def _hierarchy_ok(ctx_or_inter, target: discord.Member) -> bool:
    guild = ctx_or_inter.guild
    me = guild.me
    author = ctx_or_inter.author if hasattr(ctx_or_inter, 'author') else ctx_or_inter.user
    return me.top_role > target.top_role and author.top_role > target.top_role


async def _dm_user(user, embed):
    try:
        await user.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Ban ───────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not _hierarchy_ok(ctx, member):
            return await ctx.send(embed=error_embed("I can't ban that member — check role hierarchy.", bot=self.bot))
        dm_embed = ghost_embed(title=f"🔨 Banned from {ctx.guild.name}",
                               description=f"**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await member.ban(reason=f"[{ctx.author}] {reason}", delete_message_days=1)
        await log_action(ctx.guild, "BAN", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been banned.\n**Reason:** {reason}", bot=self.bot))

    # ── Unban ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="unban", description="Unban a user by ID or tag")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(user="User ID or Username#Discriminator to unban", reason="Reason")
    async def unban(self, ctx, user: str, *, reason: str = "No reason provided"):
        bans = [entry async for entry in ctx.guild.bans()]
        target = None
        if user.isdigit():
            target = next((e.user for e in bans if str(e.user.id) == user), None)
        else:
            target = next((e.user for e in bans if str(e.user) == user), None)
        if not target:
            return await ctx.send(embed=error_embed("That user is not banned.", bot=self.bot))
        await ctx.guild.unban(target, reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "UNBAN", target, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{target}** has been unbanned.", bot=self.bot))

    # ── Kick ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not _hierarchy_ok(ctx, member):
            return await ctx.send(embed=error_embed("I can't kick that member — check role hierarchy.", bot=self.bot))
        dm_embed = ghost_embed(title=f"👢 Kicked from {ctx.guild.name}",
                               description=f"**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await member.kick(reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "KICK", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been kicked.\n**Reason:** {reason}", bot=self.bot))

    # ── Mute ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="mute", description="Mute a member using the mute role")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Member to mute", reason="Reason")
    async def mute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        cfg = await db.ensure_guild_config(str(ctx.guild.id))
        if not cfg.get("mute_role"):
            return await ctx.send(embed=error_embed("No mute role set. Run `-setup` first.", bot=self.bot))
        role = ctx.guild.get_role(int(cfg["mute_role"]))
        if not role:
            return await ctx.send(embed=error_embed("Mute role not found. Run `-setup` again.", bot=self.bot))
        if role in member.roles:
            return await ctx.send(embed=error_embed("That member is already muted.", bot=self.bot))
        await member.add_roles(role, reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "MUTE", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been muted.\n**Reason:** {reason}", bot=self.bot))

    # ── Unmute ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="unmute", description="Unmute a muted member")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Member to unmute", reason="Reason")
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        cfg = await db.get_guild_config(str(ctx.guild.id))
        if not cfg or not cfg.get("mute_role"):
            return await ctx.send(embed=error_embed("No mute role configured.", bot=self.bot))
        role = ctx.guild.get_role(int(cfg["mute_role"]))
        if not role or role not in member.roles:
            return await ctx.send(embed=error_embed("That member is not muted.", bot=self.bot))
        await member.remove_roles(role, reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "UNMUTE", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been unmuted.", bot=self.bot))

    # ── Warn ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member.bot:
            return await ctx.send(embed=error_embed("You can't warn bots.", bot=self.bot))
        warn_id = await db.add_warn(str(ctx.guild.id), str(member.id), str(ctx.author.id), reason)
        warns = await db.get_warns(str(ctx.guild.id), str(member.id))
        dm_embed = ghost_embed(title=f"⚠️ Warning in {ctx.guild.name}",
                               description=f"**Reason:** {reason}\n**Warn #{warn_id}** — You now have **{len(warns)}** warning(s).",
                               bot=self.bot)
        await _dm_user(member, dm_embed)
        await log_action(ctx.guild, "WARN", member, ctx.author, reason, extra=f"Warn ID: #{warn_id} | Total: {len(warns)}")
        await ctx.send(embed=success_embed(
            f"**{member}** has been warned (ID: `#{warn_id}`).\n**Reason:** {reason}\n**Total Warnings:** {len(warns)}",
            bot=self.bot))

    # ── Warnings ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="warnings", description="View a member's warnings")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to check")
    async def warnings(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        warns = await db.get_warns(str(ctx.guild.id), str(member.id))
        embed = ghost_embed(title=f"⚠️ Warnings — {member}", bot=self.bot)
        if not warns:
            embed.description = "This member has no warnings."
        else:
            lines = []
            for w in warns[:15]:
                ts = f"<t:{w['timestamp']}:R>"
                lines.append(f"`#{w['id']}` **{w['reason']}** — by <@{w['moderator_id']}> {ts}")
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"👻 Ghost — {len(warns)} total warning(s)")
        await ctx.send(embed=embed)

    # ── Clear Warns ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="clearwarns", description="Clear all warnings for a member")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to clear warnings for")
    async def clearwarns(self, ctx, member: discord.Member):
        count = await db.clear_warns(str(ctx.guild.id), str(member.id))
        await log_action(ctx.guild, "CLEARWARNS", member, ctx.author,
                         reason=f"Cleared {count} warning(s)")
        await ctx.send(embed=success_embed(f"Cleared **{count}** warning(s) for **{member}**.", bot=self.bot))

    # ── Jail ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="jail", description="Jail a member (remove all roles, assign jail role)")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Member to jail", reason="Reason")
    async def jail(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        cfg = await db.ensure_guild_config(str(ctx.guild.id))
        if not cfg.get("jail_role"):
            return await ctx.send(embed=error_embed("No jail role set. Run `-setup` first.", bot=self.bot))
        jail_role = ctx.guild.get_role(int(cfg["jail_role"]))
        if not jail_role:
            return await ctx.send(embed=error_embed("Jail role not found. Run `-setup` again.", bot=self.bot))
        if jail_role in member.roles:
            return await ctx.send(embed=error_embed("That member is already jailed.", bot=self.bot))
        saved = [str(r.id) for r in member.roles if not r.managed and r != ctx.guild.default_role]
        roles_to_remove = [r for r in member.roles if not r.managed and r != ctx.guild.default_role]
        await member.remove_roles(*roles_to_remove, reason=f"[Jail] {ctx.author}")
        await member.add_roles(jail_role, reason=f"[{ctx.author}] {reason}")
        await db.jail_member(str(ctx.guild.id), str(member.id), saved)
        dm_embed = ghost_embed(title=f"🔒 Jailed in {ctx.guild.name}",
                               description=f"**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await log_action(ctx.guild, "JAIL", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been jailed.\n**Reason:** {reason}", bot=self.bot))

    # ── Unjail ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="unjail", description="Release a member from jail")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Member to unjail", reason="Reason")
    async def unjail(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        cfg = await db.get_guild_config(str(ctx.guild.id))
        jail_data = await db.get_jail_data(str(ctx.guild.id), str(member.id))
        if not jail_data:
            return await ctx.send(embed=error_embed("That member is not jailed.", bot=self.bot))
        jail_role = ctx.guild.get_role(int(cfg["jail_role"])) if cfg and cfg.get("jail_role") else None
        if jail_role:
            await member.remove_roles(jail_role, reason=f"[Unjail] {ctx.author}")
        roles_to_restore = []
        for role_id in jail_data["saved_roles"]:
            role = ctx.guild.get_role(int(role_id))
            if role and role < ctx.guild.me.top_role:
                roles_to_restore.append(role)
        if roles_to_restore:
            await member.add_roles(*roles_to_restore, reason=f"[Unjail restore] {ctx.author}")
        await db.unjail_member(str(ctx.guild.id), str(member.id))
        await log_action(ctx.guild, "UNJAIL", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been released from jail.", bot=self.bot))

    # ── Tempban ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="tempban", description="Temporarily ban a member")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Member to tempban", duration="Duration e.g. 1d, 2h", reason="Reason")
    async def tempban(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        secs = parse_time(duration)
        if secs <= 0:
            return await ctx.send(embed=error_embed("Invalid duration. Example: `1d`, `2h30m`.", bot=self.bot))
        if not _hierarchy_ok(ctx, member):
            return await ctx.send(embed=error_embed("I can't ban that member — check role hierarchy.", bot=self.bot))
        expires_at = int(_time.time()) + secs
        dm_embed = ghost_embed(title=f"⏱️ Tempbanned from {ctx.guild.name}",
                               description=f"**Duration:** {format_time(secs)}\n**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await member.ban(reason=f"[Tempban {format_time(secs)}] [{ctx.author}] {reason}", delete_message_days=1)
        await db.add_tempban(str(ctx.guild.id), str(member.id), expires_at, reason)
        await log_action(ctx.guild, "TEMPBAN", member, ctx.author, reason, extra=f"Duration: {format_time(secs)}")
        await ctx.send(embed=success_embed(
            f"**{member}** has been banned for **{format_time(secs)}**.\n**Reason:** {reason}", bot=self.bot))

    # ── Softban ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="softban", description="Ban then immediately unban a member (clears recent messages)")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Member to softban", reason="Reason")
    async def softban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not _hierarchy_ok(ctx, member):
            return await ctx.send(embed=error_embed("I can't ban that member — check role hierarchy.", bot=self.bot))
        dm_embed = ghost_embed(title=f"🔄 Softbanned from {ctx.guild.name}",
                               description=f"**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await member.ban(reason=f"[Softban] [{ctx.author}] {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason="Softban unban")
        await log_action(ctx.guild, "SOFTBAN", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been softbanned.\n**Reason:** {reason}", bot=self.bot))

    # ── Hardban ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="hardban", description="Ban a member and delete all their recent messages")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(member="Member to hardban", reason="Reason")
    async def hardban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not _hierarchy_ok(ctx, member):
            return await ctx.send(embed=error_embed("I can't ban that member — check role hierarchy.", bot=self.bot))
        dm_embed = ghost_embed(title=f"🔨 Hardbanned from {ctx.guild.name}",
                               description=f"**Reason:** {reason}", bot=self.bot)
        await _dm_user(member, dm_embed)
        await member.ban(reason=f"[Hardban] [{ctx.author}] {reason}", delete_message_days=7)
        await log_action(ctx.guild, "HARDBAN", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"**{member}** has been hardbanned.\n**Reason:** {reason}", bot=self.bot))

    # ── Timeout ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="timeout", description="Timeout a member")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to timeout", duration="Duration e.g. 1h, 30m", reason="Reason")
    async def timeout(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        secs = parse_time(duration)
        if secs <= 0:
            return await ctx.send(embed=error_embed("Invalid duration. Example: `1h`, `30m`.", bot=self.bot))
        if secs > 2419200:
            return await ctx.send(embed=error_embed("Timeout cannot exceed 28 days.", bot=self.bot))
        import datetime
        until = discord.utils.utcnow() + datetime.timedelta(seconds=secs)
        await member.timeout(until, reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "TIMEOUT", member, ctx.author, reason, extra=f"Duration: {format_time(secs)}")
        await ctx.send(embed=success_embed(
            f"**{member}** has been timed out for **{format_time(secs)}**.\n**Reason:** {reason}", bot=self.bot))

    # ── Untimeout ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="untimeout", description="Remove a member's timeout")
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(member="Member to remove timeout from", reason="Reason")
    async def untimeout(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if not member.is_timed_out():
            return await ctx.send(embed=error_embed("That member is not timed out.", bot=self.bot))
        await member.timeout(None, reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "UNTIMEOUT", member, ctx.author, reason)
        await ctx.send(embed=success_embed(f"Removed timeout for **{member}**.", bot=self.bot))

    # ── Purge ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="purge", description="Bulk delete messages from a channel")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Number of messages to delete (1–100)", member="Only delete messages from this member")
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        if not 1 <= amount <= 100:
            return await ctx.send(embed=error_embed("Amount must be between 1 and 100.", bot=self.bot))
        def check(m):
            return member is None or m.author == member
        deleted = await ctx.channel.purge(limit=amount, check=check, before=ctx.message)
        if hasattr(ctx, 'message') and ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.NotFound:
                pass
        confirm = await ctx.send(embed=success_embed(f"Deleted **{len(deleted)}** message(s).", bot=self.bot))
        await asyncio.sleep(4)
        try:
            await confirm.delete()
        except discord.NotFound:
            pass

    # ── Lock ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="lock", description="Lock a channel so members can't send messages")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @app_commands.describe(channel="Channel to lock (defaults to current)", reason="Reason")
    async def lock(self, ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite,
                                      reason=f"[{ctx.author}] {reason}")
        await log_action(ctx.guild, "LOCK", channel, ctx.author, reason)
        await ctx.send(embed=success_embed(f"🔒 {channel.mention} has been locked.\n**Reason:** {reason}", bot=self.bot))

    # ── Unlock ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="unlock", description="Unlock a locked channel")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @app_commands.describe(channel="Channel to unlock", reason="Reason")
    async def unlock(self, ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite,
                                      reason=f"[{ctx.author}] {reason}")
        await ctx.send(embed=success_embed(f"🔓 {channel.mention} has been unlocked.", bot=self.bot))

    # ── Slowmode ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="slowmode", description="Set slowmode for a channel")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @app_commands.describe(duration="Slowmode delay e.g. 5s, 1m (0 to disable)", channel="Target channel")
    async def slowmode(self, ctx, duration: str, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        secs = parse_time(duration)
        if secs < 0:
            return await ctx.send(embed=error_embed("Invalid duration.", bot=self.bot))
        if secs > 21600:
            return await ctx.send(embed=error_embed("Slowmode cannot exceed 6 hours.", bot=self.bot))
        await channel.edit(slowmode_delay=secs)
        if secs == 0:
            await ctx.send(embed=success_embed(f"Slowmode disabled in {channel.mention}.", bot=self.bot))
        else:
            await ctx.send(embed=success_embed(f"Slowmode set to `{format_time(secs)}` in {channel.mention}.", bot=self.bot))

    # ── Strip Staff ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="stripstaff", description="Remove all staff roles from a member")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(member="Member to strip staff roles from", reason="Reason")
    async def stripstaff(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        staff_perms = (
            discord.Permissions.ban_members,
            discord.Permissions.kick_members,
            discord.Permissions.manage_guild,
            discord.Permissions.manage_roles,
            discord.Permissions.manage_channels,
            discord.Permissions.administrator,
            discord.Permissions.moderate_members,
        )
        roles_to_remove = [
            r for r in member.roles
            if not r.managed and r != ctx.guild.default_role
            and r < ctx.guild.me.top_role
            and any(getattr(r.permissions, p.name, False) for p in staff_perms)
        ]
        if not roles_to_remove:
            return await ctx.send(embed=error_embed("That member has no removable staff roles.", bot=self.bot))
        await member.remove_roles(*roles_to_remove, reason=f"[Stripstaff] [{ctx.author}] {reason}")
        await log_action(ctx.guild, "STRIPSTAFF", member, ctx.author, reason,
                         extra=f"Removed: {', '.join(r.name for r in roles_to_remove)}")
        await ctx.send(embed=success_embed(
            f"Removed **{len(roles_to_remove)}** staff role(s) from **{member}**.", bot=self.bot))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
