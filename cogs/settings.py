import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.embeds import success_embed, error_embed, ghost_embed, info_embed
from database import db


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Setup ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="setup", description="Set up Ghost's moderation infrastructure")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def setup(self, ctx):
        await ctx.defer()
        guild = ctx.guild

        # Create modlog channel
        modlog_ch = discord.utils.get(guild.text_channels, name="mod-logs")
        if not modlog_ch:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            modlog_ch = await guild.create_text_channel("mod-logs", overwrites=overwrites,
                                                         reason="Ghost setup")

        # Create jail role
        jail_role = discord.utils.get(guild.roles, name="Jailed")
        if not jail_role:
            jail_role = await guild.create_role(name="Jailed", color=discord.Color.dark_gray(),
                                                reason="Ghost setup")
            for channel in guild.channels:
                try:
                    await channel.set_permissions(jail_role, send_messages=False,
                                                  add_reactions=False, connect=False,
                                                  reason="Ghost jail setup")
                except discord.Forbidden:
                    pass

        # Create jail channel
        jail_ch = discord.utils.get(guild.text_channels, name="jail")
        if not jail_ch:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                jail_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            jail_ch = await guild.create_text_channel("jail", overwrites=overwrites,
                                                        reason="Ghost setup")

        # Create mute role
        mute_role = discord.utils.get(guild.roles, name="Muted")
        if not mute_role:
            mute_role = await guild.create_role(name="Muted", color=discord.Color.dark_gray(),
                                                reason="Ghost setup")
            for channel in guild.text_channels:
                try:
                    await channel.set_permissions(mute_role, send_messages=False,
                                                  add_reactions=False, reason="Ghost mute setup")
                except discord.Forbidden:
                    pass

        await db.update_guild_config(str(guild.id),
                                     modlog_channel=str(modlog_ch.id),
                                     jail_role=str(jail_role.id),
                                     mute_role=str(mute_role.id))

        embed = success_embed(
            f"✅ Setup complete!\n\n"
            f"**Mod Logs:** {modlog_ch.mention}\n"
            f"**Jail Channel:** {jail_ch.mention}\n"
            f"**Jail Role:** {jail_role.mention}\n"
            f"**Mute Role:** {mute_role.mention}",
            title="⚙️ Ghost Setup",
            bot=self.bot
        )
        await ctx.send(embed=embed)

    # ── Set Prefix ────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="setprefix", description="Change the bot prefix for this server")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(prefix="New prefix (max 5 characters)")
    async def setprefix(self, ctx, prefix: str):
        if len(prefix) > 5:
            return await ctx.send(embed=error_embed("Prefix must be 5 characters or fewer.", bot=self.bot))
        await db.update_guild_config(str(ctx.guild.id), prefix=prefix)
        await ctx.send(embed=success_embed(f"Prefix changed to `{prefix}`", bot=self.bot))

    # ── Set Logs ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="setlogs", description="Set the moderation log channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to send mod logs to")
    async def setlogs(self, ctx, channel: discord.TextChannel):
        await db.update_guild_config(str(ctx.guild.id), modlog_channel=str(channel.id))
        await ctx.send(embed=success_embed(f"Mod log channel set to {channel.mention}", bot=self.bot))

    # ── Set Welcome ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="setwelcome", description="Configure the welcome message")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Welcome channel", message="Welcome message (use {mention},{user},{server},{memberCount})")
    async def setwelcome(self, ctx, channel: discord.TextChannel, *, message: str = None):
        updates = {"welcome_channel": str(channel.id)}
        if message:
            updates["welcome_message"] = message
        await db.update_guild_config(str(ctx.guild.id), **updates)
        cfg = await db.get_guild_config(str(ctx.guild.id))
        embed = success_embed(
            f"Welcome channel set to {channel.mention}\n**Message:** {cfg['welcome_message']}",
            bot=self.bot
        )
        embed.add_field(name="Variables",
                        value="`{mention}` `{user}` `{server}` `{memberCount}`", inline=False)
        await ctx.send(embed=embed)

    # ── Set Goodbye ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="setgoodbye", description="Configure the goodbye message")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Goodbye channel", message="Goodbye message (use {user},{server},{memberCount})")
    async def setgoodbye(self, ctx, channel: discord.TextChannel, *, message: str = None):
        updates = {"goodbye_channel": str(channel.id)}
        if message:
            updates["goodbye_message"] = message
        await db.update_guild_config(str(ctx.guild.id), **updates)
        cfg = await db.get_guild_config(str(ctx.guild.id))
        await ctx.send(embed=success_embed(
            f"Goodbye channel set to {channel.mention}\n**Message:** {cfg['goodbye_message']}",
            bot=self.bot
        ))

    # ── Autorole ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="autorole", description="Set a role to give new members on join")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(role="Role to assign on join (leave empty to disable)")
    async def autorole(self, ctx, role: discord.Role = None):
        await db.update_guild_config(str(ctx.guild.id), autorole=str(role.id) if role else None)
        if role:
            await ctx.send(embed=success_embed(f"Autorole set to {role.mention}", bot=self.bot))
        else:
            await ctx.send(embed=success_embed("Autorole disabled.", bot=self.bot))

    # ── Antinuke ──────────────────────────────────────────────────────────────
    @commands.hybrid_group(name="antinuke", description="Configure antinuke protection",
                            invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def antinuke(self, ctx):
        cfg = await db.ensure_guild_config(str(ctx.guild.id))
        whitelist = json.loads(cfg.get("antinuke_whitelist") or "[]")
        wl_mentions = " ".join(f"<@{uid}>" for uid in whitelist) or "None"
        embed = ghost_embed(title="🛡️ Antinuke Settings", bot=self.bot)
        embed.add_field(name="Status",     value="✅ Enabled" if cfg["antinuke_enabled"] else "❌ Disabled", inline=True)
        embed.add_field(name="Threshold",  value=str(cfg["antinuke_threshold"]),  inline=True)
        embed.add_field(name="Punishment", value=str(cfg["antinuke_punish"]).title(), inline=True)
        embed.add_field(name="Whitelist",  value=wl_mentions, inline=False)
        embed.description = (
            f"Use `-antinuke enable/disable/threshold/punish/whitelist` to configure.\n"
            f"Use `-antinuke whitelist add/remove @user`"
        )
        await ctx.send(embed=embed)

    @antinuke.command(name="enable", description="Enable antinuke protection")
    async def antinuke_enable(self, ctx):
        await db.update_guild_config(str(ctx.guild.id), antinuke_enabled=1)
        await ctx.send(embed=success_embed("Antinuke protection **enabled**.", bot=self.bot))

    @antinuke.command(name="disable", description="Disable antinuke protection")
    async def antinuke_disable(self, ctx):
        await db.update_guild_config(str(ctx.guild.id), antinuke_enabled=0)
        await ctx.send(embed=success_embed("Antinuke protection **disabled**.", bot=self.bot))

    @antinuke.command(name="threshold", description="Set the number of actions before triggering punishment")
    @app_commands.describe(amount="Number of actions in 10s to trigger punishment (1-10)")
    async def antinuke_threshold(self, ctx, amount: int):
        if not 1 <= amount <= 10:
            return await ctx.send(embed=error_embed("Threshold must be between 1 and 10.", bot=self.bot))
        await db.update_guild_config(str(ctx.guild.id), antinuke_threshold=amount)
        await ctx.send(embed=success_embed(f"Antinuke threshold set to `{amount}`.", bot=self.bot))

    @antinuke.command(name="punish", description="Set antinuke punishment action")
    @app_commands.describe(action="Punishment: ban, kick, or strip (remove roles)")
    async def antinuke_punish(self, ctx, action: str):
        action = action.lower()
        if action not in ("ban", "kick", "strip"):
            return await ctx.send(embed=error_embed("Valid options: `ban`, `kick`, `strip`.", bot=self.bot))
        await db.update_guild_config(str(ctx.guild.id), antinuke_punish=action)
        await ctx.send(embed=success_embed(f"Antinuke punishment set to `{action}`.", bot=self.bot))

    @antinuke.command(name="whitelist", description="Add or remove a user from the antinuke whitelist")
    @app_commands.describe(action="add or remove", member="The member to whitelist")
    async def antinuke_whitelist(self, ctx, action: str, member: discord.Member):
        action = action.lower()
        if action not in ("add", "remove"):
            return await ctx.send(embed=error_embed("Use `add` or `remove`.", bot=self.bot))
        cfg = await db.ensure_guild_config(str(ctx.guild.id))
        whitelist = json.loads(cfg.get("antinuke_whitelist") or "[]")
        uid = str(member.id)
        if action == "add":
            if uid in whitelist:
                return await ctx.send(embed=error_embed(f"{member.mention} is already whitelisted.", bot=self.bot))
            whitelist.append(uid)
            msg = f"{member.mention} added to antinuke whitelist."
        else:
            if uid not in whitelist:
                return await ctx.send(embed=error_embed(f"{member.mention} is not whitelisted.", bot=self.bot))
            whitelist.remove(uid)
            msg = f"{member.mention} removed from antinuke whitelist."
        await db.update_guild_config(str(ctx.guild.id), antinuke_whitelist=json.dumps(whitelist))
        await ctx.send(embed=success_embed(msg, bot=self.bot))

    # ── Antiraid ──────────────────────────────────────────────────────────────
    @commands.hybrid_group(name="antiraid", description="Configure antiraid protection",
                            invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def antiraid(self, ctx):
        cfg = await db.ensure_guild_config(str(ctx.guild.id))
        embed = ghost_embed(title="🛡️ Antiraid Settings", bot=self.bot)
        embed.add_field(name="Status",      value="✅ Enabled" if cfg["antiraid_enabled"] else "❌ Disabled", inline=True)
        embed.add_field(name="Join Threshold", value=str(cfg["antiraid_threshold"]), inline=True)
        embed.add_field(name="Min Account Age", value=f"{cfg['antiraid_min_age']} days", inline=True)
        embed.add_field(name="No Avatar Action", value="Kick" if cfg["antiraid_no_avatar"] else "Allow", inline=True)
        await ctx.send(embed=embed)

    @antiraid.command(name="enable", description="Enable antiraid protection")
    async def antiraid_enable(self, ctx):
        await db.update_guild_config(str(ctx.guild.id), antiraid_enabled=1)
        await ctx.send(embed=success_embed("Antiraid protection **enabled**.", bot=self.bot))

    @antiraid.command(name="disable", description="Disable antiraid protection")
    async def antiraid_disable(self, ctx):
        await db.update_guild_config(str(ctx.guild.id), antiraid_enabled=0)
        await ctx.send(embed=success_embed("Antiraid protection **disabled**.", bot=self.bot))

    @antiraid.command(name="threshold", description="Set join rate threshold to trigger raid mode")
    @app_commands.describe(amount="Number of joins in 5s to trigger raid mode (3-20)")
    async def antiraid_threshold(self, ctx, amount: int):
        if not 3 <= amount <= 20:
            return await ctx.send(embed=error_embed("Threshold must be between 3 and 20.", bot=self.bot))
        await db.update_guild_config(str(ctx.guild.id), antiraid_threshold=amount)
        await ctx.send(embed=success_embed(f"Antiraid join threshold set to `{amount}`.", bot=self.bot))

    @antiraid.command(name="minage", description="Set minimum account age required to join")
    @app_commands.describe(days="Minimum account age in days (0 to disable)")
    async def antiraid_minage(self, ctx, days: int):
        if days < 0:
            return await ctx.send(embed=error_embed("Days must be 0 or greater.", bot=self.bot))
        await db.update_guild_config(str(ctx.guild.id), antiraid_min_age=days)
        msg = f"Minimum account age set to `{days} days`." if days else "Account age check disabled."
        await ctx.send(embed=success_embed(msg, bot=self.bot))

    @antiraid.command(name="noavatar", description="Kick members with no avatar on join")
    @app_commands.describe(toggle="on or off")
    async def antiraid_noavatar(self, ctx, toggle: str):
        toggle = toggle.lower()
        if toggle not in ("on", "off"):
            return await ctx.send(embed=error_embed("Use `on` or `off`.", bot=self.bot))
        val = 1 if toggle == "on" else 0
        await db.update_guild_config(str(ctx.guild.id), antiraid_no_avatar=val)
        await ctx.send(embed=success_embed(f"No-avatar kick turned `{toggle}`.", bot=self.bot))


async def setup(bot):
    await bot.add_cog(Settings(bot))
