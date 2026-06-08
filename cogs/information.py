import discord
from discord import app_commands
from discord.ext import commands
import time
from utils.embeds import ghost_embed, error_embed, GHOST_COLOR


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Ping ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx):
        start = time.monotonic()
        msg = await ctx.send("Pinging…")
        latency = (time.monotonic() - start) * 1000

        embed = ghost_embed(
            title="🏓 Pong!",
            description=(
                f"> **Websocket:** `{round(self.bot.latency * 1000)}ms`\n"
                f"> **Response:** `{round(latency)}ms`"
            ),
            bot=self.bot
        )
        await msg.edit(content=None, embed=embed)

    # ── Help ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="help", description="Show the help menu")
    @app_commands.describe(command="A specific command to get info on")
    async def help(self, ctx, *, command: str = None):
        prefix = "-"
        if ctx.guild:
            from database.db import get_guild_config
            cfg = await get_guild_config(str(ctx.guild.id))
            prefix = cfg["prefix"] if cfg else "-"

        if command:
            cmd = self.bot.get_command(command)
            if not cmd:
                return await ctx.send(embed=error_embed(f"Command `{command}` not found.", bot=self.bot))
            embed = ghost_embed(
                title=f"📖 `{prefix}{cmd.qualified_name}`",
                description=cmd.description or "No description provided.",
                bot=self.bot
            )
            embed.add_field(name="Usage", value=f"`{prefix}{cmd.qualified_name} {cmd.signature}`", inline=False)
            if hasattr(cmd, 'aliases') and cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in cmd.aliases), inline=False)
            return await ctx.send(embed=embed)

        categories = {}
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            cog_name = cmd.cog_name or "Other"
            categories.setdefault(cog_name, []).append(f"`{cmd.name}`")

        embed = ghost_embed(
            title="👻 Ghost — Help",
            description=f"Use `{prefix}help <command>` for more info on a command.\nPrefix: `{prefix}` | Slash commands also work.",
            bot=self.bot
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        icons = {
            "Information": "📋", "Moderation": "🔨", "Settings": "⚙️",
            "Levels": "⭐", "Roles": "🎭", "Music": "🎵",
            "Giveaway": "🎉", "Fun": "🎲",
        }
        for cat, cmds in sorted(categories.items()):
            icon = icons.get(cat, "•")
            embed.add_field(name=f"{icon} {cat}", value=" ".join(sorted(cmds)), inline=False)

        await ctx.send(embed=embed)

    # ── User Info ─────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="userinfo", description="Show information about a user")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    @commands.guild_only()
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [r.mention for r in reversed(member.roles) if r != ctx.guild.default_role]

        embed = ghost_embed(title=f"👤 {member}", bot=self.bot)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Account Created",
                        value=f"<t:{int(member.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Joined Server",
                        value=f"<t:{int(member.joined_at.timestamp())}:F>" if member.joined_at else "Unknown",
                        inline=True)
        embed.add_field(name="Highest Role",
                        value=member.top_role.mention if member.top_role != ctx.guild.default_role else "@everyone",
                        inline=True)
        if roles:
            embed.add_field(name=f"Roles [{len(roles)}]",
                            value=" ".join(roles[:20]) + (" …" if len(roles) > 20 else ""),
                            inline=False)
        embed.color = member.color if member.color.value else GHOST_COLOR
        await ctx.send(embed=embed)

    # ── Server Info ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="serverinfo", description="Show information about the server")
    @commands.guild_only()
    async def serverinfo(self, ctx):
        g = ctx.guild
        bots    = sum(1 for m in g.members if m.bot)
        humans  = g.member_count - bots
        online  = sum(1 for m in g.members if m.status != discord.Status.offline and not m.bot)
        channels = (f"<:text:> {len(g.text_channels)} text • "
                    f"🔊 {len(g.voice_channels)} voice • "
                    f"📁 {len(g.categories)} categories")

        embed = ghost_embed(title=f"🌐 {g.name}", bot=self.bot)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Owner",        value=f"<@{g.owner_id}>",         inline=True)
        embed.add_field(name="ID",           value=f"`{g.id}`",                inline=True)
        embed.add_field(name="Created",      value=f"<t:{int(g.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Members",      value=f"👥 {humans} humans • 🤖 {bots} bots\n🟢 {online} online", inline=True)
        embed.add_field(name="Channels",     value=channels,                   inline=False)
        embed.add_field(name="Roles",        value=str(len(g.roles)),          inline=True)
        embed.add_field(name="Emojis",       value=str(len(g.emojis)),         inline=True)
        embed.add_field(name="Boost Level",  value=f"Level {g.premium_tier} ({g.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Verification", value=str(g.verification_level).title(), inline=True)
        if g.banner:
            embed.set_image(url=g.banner.url)
        await ctx.send(embed=embed)

    # ── Avatar ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(member="The member whose avatar to show")
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = ghost_embed(title=f"🖼️ {member.display_name}'s Avatar", bot=self.bot)
        embed.set_image(url=member.display_avatar.url)
        links = (f"[PNG]({member.display_avatar.with_format('png').url}) • "
                 f"[JPG]({member.display_avatar.with_format('jpg').url}) • "
                 f"[WEBP]({member.display_avatar.with_format('webp').url})")
        if member.display_avatar.is_animated():
            links += f" • [GIF]({member.display_avatar.with_format('gif').url})"
        embed.description = links
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Information(bot))
