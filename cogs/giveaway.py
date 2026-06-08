import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from utils.embeds import ghost_embed, success_embed, error_embed
from utils.time_parser import parse_time, format_time
from database import db


async def finish_giveaway(bot, gw: dict):
    """End a giveaway, pick winners, edit the message."""
    guild = bot.get_guild(int(gw["guild_id"]))
    if not guild:
        await db.end_giveaway(gw["id"])
        return

    channel = guild.get_channel(int(gw["channel_id"]))
    if not channel:
        await db.end_giveaway(gw["id"])
        return

    entries = gw["entries"]
    winner_count = gw["winner_count"]

    if not entries:
        winners_text = "No valid entries."
        winners = []
    else:
        sample = random.sample(entries, min(winner_count, len(entries)))
        winners = [f"<@{uid}>" for uid in sample]
        winners_text = ", ".join(winners)

    embed = discord.Embed(
        title="🎉 Giveaway Ended",
        description=(
            f"**Prize:** {gw['prize']}\n"
            f"**Winner(s):** {winners_text}\n"
            f"**Hosted by:** <@{gw['host_id']}>\n"
            f"**Entries:** {len(entries)}"
        ),
        color=0xf1c40f
    )
    embed.set_footer(text="👻 Ghost — Giveaway")

    try:
        message = await channel.fetch_message(int(gw["message_id"]))
        await message.edit(embed=embed, view=None)
        if winners:
            await channel.send(
                f"🎉 Congratulations {winners_text}! You won **{gw['prize']}**!"
            )
        else:
            await channel.send("🎉 The giveaway ended but there were no entries.")
    except (discord.NotFound, discord.HTTPException):
        pass

    await db.end_giveaway(gw["id"])


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="🎉", label="Enter Giveaway",
                       style=discord.ButtonStyle.primary,
                       custom_id="ghost_giveaway_enter")
    async def enter_giveaway(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        gw = await db.get_giveaway_by_message(str(interaction.message.id))
        if not gw:
            return await interaction.followup.send("This giveaway no longer exists.", ephemeral=True)
        if gw["ended"]:
            return await interaction.followup.send("This giveaway has already ended.", ephemeral=True)

        entries = list(gw["entries"])
        uid = str(interaction.user.id)
        if uid in entries:
            entries.remove(uid)
            await db.update_giveaway_entries(gw["id"], entries)
            await interaction.followup.send("❌ You left the giveaway.", ephemeral=True)
        else:
            entries.append(uid)
            await db.update_giveaway_entries(gw["id"], entries)
            await interaction.followup.send(f"🎉 You're in! **{len(entries)}** total entr{'y' if len(entries) == 1 else 'ies'}.", ephemeral=True)


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Create Giveaway ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="gcreate", description="Start a giveaway")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        duration="Duration e.g. 1d, 2h, 30m",
        winners="Number of winners",
        prize="What are you giving away?"
    )
    async def gcreate(self, ctx, duration: str, winners: int, *, prize: str):
        if winners < 1 or winners > 20:
            return await ctx.send(embed=error_embed("Winners must be between 1 and 20.", bot=self.bot))

        secs = parse_time(duration)
        if secs <= 0:
            return await ctx.send(embed=error_embed("Invalid duration. Example: `1d`, `2h30m`.", bot=self.bot))

        end_time = int(time.time()) + secs

        embed = discord.Embed(
            title="🎉 Giveaway!",
            description=(
                f"**Prize:** {prize}\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{end_time}:R> (<t:{end_time}:F>)\n"
                f"**Hosted by:** {ctx.author.mention}\n\n"
                f"Click the button below to enter!"
            ),
            color=0xf1c40f
        )
        embed.set_footer(text="👻 Ghost — Giveaway")

        view = GiveawayView()
        gw_id = await db.create_giveaway(
            str(ctx.guild.id), str(ctx.channel.id), prize, winners,
            str(ctx.author.id), end_time
        )

        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view)
            msg = await ctx.interaction.original_response()
        else:
            msg = await ctx.channel.send(embed=embed, view=view)
            try:
                await ctx.message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        await db.set_giveaway_message(gw_id, str(msg.id))
        await ctx.send(
            embed=success_embed(f"Giveaway started! [Jump to it]({msg.jump_url})", bot=self.bot),
            ephemeral=True
        )

    # ── End Giveaway ──────────────────────────────────────────────────────────
    @commands.hybrid_command(name="gend", description="Force-end a running giveaway")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(message_id="Message ID of the giveaway")
    async def gend(self, ctx, message_id: str):
        gw = await db.get_giveaway_by_message(message_id)
        if not gw:
            return await ctx.send(embed=error_embed("Giveaway not found.", bot=self.bot))
        if gw["ended"]:
            return await ctx.send(embed=error_embed("That giveaway has already ended.", bot=self.bot))
        if str(gw["guild_id"]) != str(ctx.guild.id):
            return await ctx.send(embed=error_embed("That giveaway is not in this server.", bot=self.bot))
        await finish_giveaway(self.bot, gw)
        await ctx.send(embed=success_embed("Giveaway ended.", bot=self.bot))

    # ── Reroll Giveaway ───────────────────────────────────────────────────────
    @commands.hybrid_command(name="greroll", description="Reroll the winner of an ended giveaway")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(message_id="Message ID of the ended giveaway")
    async def greroll(self, ctx, message_id: str):
        gw = await db.get_giveaway_by_message(message_id)
        if not gw:
            return await ctx.send(embed=error_embed("Giveaway not found.", bot=self.bot))
        if not gw["ended"]:
            return await ctx.send(embed=error_embed("That giveaway hasn't ended yet. Use `-gend` first.", bot=self.bot))

        entries = gw["entries"]
        if not entries:
            return await ctx.send(embed=error_embed("No entries to reroll from.", bot=self.bot))

        new_winner = random.choice(entries)
        await ctx.send(
            embed=success_embed(
                f"🎲 New winner: <@{new_winner}>! Congratulations on winning **{gw['prize']}**!",
                title="🎉 Rerolled",
                bot=self.bot
            )
        )


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
