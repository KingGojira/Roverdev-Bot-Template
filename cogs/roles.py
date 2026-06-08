import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import success_embed, error_embed, ghost_embed
from database import db


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Add Reaction Role ─────────────────────────────────────────────────────
    @commands.hybrid_command(name="reactionrole",
                              description="Add a reaction role to a message")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @app_commands.describe(
        channel="Channel the message is in",
        message_id="ID of the message",
        emoji="Emoji to react with",
        role="Role to assign"
    )
    async def reactionrole(self, ctx, channel: discord.TextChannel,
                            message_id: str, emoji: str, role: discord.Role):
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, ValueError):
            return await ctx.send(embed=error_embed("Message not found.", bot=self.bot))

        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("That role is higher than my highest role.", bot=self.bot))

        await db.add_reaction_role(str(ctx.guild.id), str(channel.id),
                                   str(message.id), emoji, str(role.id))
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await ctx.send(embed=error_embed("Couldn't add reaction — invalid emoji?", bot=self.bot))

        await ctx.send(embed=success_embed(
            f"Reaction role added!\n**Message:** [Jump]({message.jump_url})\n"
            f"**Emoji:** {emoji} → **Role:** {role.mention}", bot=self.bot))

    # ── Remove Reaction Role ──────────────────────────────────────────────────
    @commands.hybrid_command(name="reactionrole-remove",
                              description="Remove a reaction role from a message")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(
        message_id="ID of the message",
        emoji="Emoji to remove the role from"
    )
    async def reactionrole_remove(self, ctx, message_id: str, emoji: str):
        removed = await db.remove_reaction_role(str(ctx.guild.id), message_id, emoji)
        if not removed:
            return await ctx.send(embed=error_embed("No reaction role found for that message/emoji.", bot=self.bot))
        await ctx.send(embed=success_embed("Reaction role removed.", bot=self.bot))

    # ── List Reaction Roles ───────────────────────────────────────────────────
    @commands.hybrid_command(name="reactionroles",
                              description="List all reaction roles in this server")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def reactionroles(self, ctx):
        rows = await db.get_reaction_roles(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=error_embed("No reaction roles configured.", bot=self.bot))
        embed = ghost_embed(title="🎭 Reaction Roles", bot=self.bot)
        lines = []
        for r in rows[:25]:
            role = ctx.guild.get_role(int(r["role_id"]))
            role_str = role.mention if role else f"<deleted: {r['role_id']}>"
            channel = ctx.guild.get_channel(int(r["channel_id"]))
            ch_str = channel.mention if channel else f"<deleted>"
            lines.append(f"{r['emoji']} → {role_str} in {ch_str} (msg `{r['message_id']}`)")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

    # ── Raw Reaction Add ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        emoji_str = str(payload.emoji)
        rr = await db.get_reaction_role(str(payload.message_id), emoji_str)
        if not rr:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        role = guild.get_role(int(rr["role_id"]))
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Reaction Role")
            except (discord.Forbidden, discord.HTTPException):
                pass

    # ── Raw Reaction Remove ───────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        emoji_str = str(payload.emoji)
        rr = await db.get_reaction_role(str(payload.message_id), emoji_str)
        if not rr:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        role = guild.get_role(int(rr["role_id"]))
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Reaction Role removed")
            except (discord.Forbidden, discord.HTTPException):
                pass


async def setup(bot):
    await bot.add_cog(Roles(bot))
