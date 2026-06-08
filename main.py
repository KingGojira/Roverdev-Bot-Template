import discord
from discord.ext import commands, tasks
import os
import asyncio
import time
import random
from dotenv import load_dotenv
from database.db import init_db, get_guild_config, get_active_giveaways, end_giveaway, get_expired_tempbans, remove_tempban

load_dotenv()

TOKEN  = os.getenv("TOKEN")
OWNERS = [int(x) for x in os.getenv("OWNERS", "").split(",") if x.strip().isdigit()]


async def get_prefix(bot, message):
    if not message.guild:
        return commands.when_mentioned_or("-")(bot, message)
    config = await get_guild_config(str(message.guild.id))
    prefix = config["prefix"] if config and config.get("prefix") else "-"
    return commands.when_mentioned_or(prefix)(bot, message)


intents = discord.Intents.all()


class Ghost(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            owner_ids=set(OWNERS),
        )
        self.music_queues: dict  = {}
        self.antinuke_actions: dict = {}
        self.join_tracker: dict  = {}
        self.raid_mode: dict     = {}

    async def setup_hook(self):
        await init_db()

        # Load persistent giveaway view
        from cogs.giveaway import GiveawayView
        self.add_view(GiveawayView())

        # Load cogs
        for folder in ("cogs", "events"):
            for filename in sorted(os.listdir(folder)):
                if filename.endswith(".py") and not filename.startswith("_"):
                    ext = f"{folder}.{filename[:-3]}"
                    try:
                        await self.load_extension(ext)
                        print(f"[Ghost] Loaded {ext}")
                    except Exception as e:
                        print(f"[Ghost] Failed to load {ext}: {e}")

        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            print(f"[Ghost] Synced {len(synced)} slash command(s)")
        except Exception as e:
            print(f"[Ghost] Slash sync failed: {e}")

        # Start background tasks
        self.background_task.start()

    async def on_ready(self):
        print(f"[Ghost] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[Ghost] Serving {len(self.guilds)} guild(s)")

    async def on_command_error(self, ctx, error):
        from utils.embeds import error_embed
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=error_embed(f"You need `{perms}` to use this command.", bot=self), ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(embed=error_embed(f"I need `{perms}` to do that.", bot=self), ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=error_embed(f"Missing argument: `{error.param.name}`\nUsage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`", bot=self), ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=error_embed(str(error), bot=self), ephemeral=True)
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=error_embed("This command can only be used in a server.", bot=self))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=error_embed(f"You're on cooldown. Try again in `{error.retry_after:.1f}s`.", bot=self), ephemeral=True)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(embed=error_embed("You don't have permission to use this command.", bot=self), ephemeral=True)
        else:
            print(f"[Ghost] Unhandled error in {ctx.command}: {error}")

    @tasks.loop(seconds=30)
    async def background_task(self):
        await self._check_giveaways()
        await self._check_tempbans()
        await self._rotate_status()

    @background_task.before_loop
    async def before_background(self):
        await self.wait_until_ready()

    _status_idx = 0
    _statuses = [
        discord.Activity(type=discord.ActivityType.watching,  name="-help | Ghost"),
        discord.Activity(type=discord.ActivityType.listening, name="your commands"),
        discord.Activity(type=discord.ActivityType.playing,   name="with moderation"),
    ]

    async def _rotate_status(self):
        await self.change_presence(activity=self._statuses[self._status_idx % len(self._statuses)])
        self._status_idx += 1

    async def _check_giveaways(self):
        from cogs.giveaway import finish_giveaway
        expired = await get_active_giveaways()
        for gw in expired:
            await finish_giveaway(self, gw)

    async def _check_tempbans(self):
        expired = await get_expired_tempbans()
        for row in expired:
            guild = self.get_guild(int(row["guild_id"]))
            if guild:
                try:
                    await guild.unban(discord.Object(id=int(row["user_id"])),
                                      reason="Tempban expired")
                except (discord.NotFound, discord.Forbidden):
                    pass
            await remove_tempban(row["guild_id"], row["user_id"])


bot = Ghost()

if __name__ == "__main__":
    if not TOKEN:
        print("[Ghost] ERROR: No TOKEN found in environment. Copy .env.example to .env and set your token.")
        exit(1)
    bot.run(TOKEN)
