import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
from collections import deque
from functools import partial
from utils.embeds import ghost_embed, success_embed, error_embed, GHOST_COLOR

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": None,
}

FFMPEG_BASE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

FILTERS = {
    "8d":         "apulsator=hz=0.08",
    "nightcore":  "aresample=48000,atempo=1.25,asetrate=60000",
    "vaporwave":  "aresample=48000,atempo=0.8,asetrate=38400",
    "bassboost":  "bass=g=20",
    "normalizer": "dynaudnorm=p=0.9",
}


class Track:
    def __init__(self, data: dict, requester: discord.Member):
        self.title      = data.get("title", "Unknown")
        self.url        = data.get("url", "")
        self.webpage_url = data.get("webpage_url", "")
        self.duration   = data.get("duration", 0)
        self.thumbnail  = data.get("thumbnail", "")
        self.uploader   = data.get("uploader", "Unknown")
        self.requester  = requester

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "??:??"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


class MusicQueue:
    def __init__(self):
        self.voice_client: discord.VoiceClient | None = None
        self.current: Track | None = None
        self.queue:   deque = deque()
        self.loop:    bool  = False
        self.volume:  float = 0.5
        self.filter:  str | None = None
        self.text_channel: discord.TextChannel | None = None
        self._skip_event: asyncio.Event = asyncio.Event()

    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()

    def make_source(self) -> discord.AudioSource:
        af_opt = f'-vn -af "{FILTERS[self.filter]}"' if self.filter else "-vn"
        source = discord.FFmpegPCMAudio(
            self.current.url,
            before_options=FFMPEG_BASE_OPTIONS,
            options=af_opt,
        )
        return discord.PCMVolumeTransformer(source, volume=self.volume)


async def fetch_track(query: str, requester: discord.Member, loop: asyncio.AbstractEventLoop) -> Track | None:
    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
    func = partial(ytdl.extract_info, query, download=False)
    try:
        data = await loop.run_in_executor(None, func)
    except Exception:
        return None
    if not data:
        return None
    if "entries" in data:
        data = data["entries"][0]
    return Track(data, requester)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.bot.music_queues:
            self.bot.music_queues[guild_id] = MusicQueue()
        return self.bot.music_queues[guild_id]

    def _after_play(self, guild_id: int, error):
        if error:
            print(f"[Music] Playback error in guild {guild_id}: {error}")
        asyncio.run_coroutine_threadsafe(self._advance(guild_id), self.bot.loop)

    async def _advance(self, guild_id: int):
        mq = self._get_queue(guild_id)
        if mq.loop and mq.current:
            pass  # Keep current track, loop it
        elif mq.queue:
            mq.current = mq.queue.popleft()
        else:
            mq.current = None
            if mq.voice_client and mq.voice_client.is_connected():
                await asyncio.sleep(180)
                if mq.current is None and mq.voice_client and mq.voice_client.is_connected():
                    await mq.voice_client.disconnect()
                    self.bot.music_queues.pop(guild_id, None)
            return

        if mq.current and mq.voice_client and mq.voice_client.is_connected():
            source = mq.make_source()
            mq.voice_client.play(source, after=lambda e: self._after_play(guild_id, e))
            if mq.text_channel:
                embed = ghost_embed(
                    title="🎵 Now Playing",
                    description=f"[{mq.current.title}]({mq.current.webpage_url})",
                    bot=self.bot
                )
                embed.add_field(name="Duration",   value=mq.current.duration_str, inline=True)
                embed.add_field(name="Requested by", value=mq.current.requester.mention, inline=True)
                if mq.current.thumbnail:
                    embed.set_thumbnail(url=mq.current.thumbnail)
                try:
                    await mq.text_channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    def _check_voice(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False
        return True

    # ── Play ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="play", description="Play a song or YouTube/Spotify URL")
    @commands.guild_only()
    @app_commands.describe(query="Song name or URL to play")
    async def play(self, ctx, *, query: str):
        if not self._check_voice(ctx):
            return await ctx.send(embed=error_embed("You must be in a voice channel.", bot=self.bot))

        await ctx.defer()
        mq = self._get_queue(ctx.guild.id)
        mq.text_channel = ctx.channel

        if not mq.voice_client or not mq.voice_client.is_connected():
            mq.voice_client = await ctx.author.voice.channel.connect()
        elif mq.voice_client.channel != ctx.author.voice.channel:
            await mq.voice_client.move_to(ctx.author.voice.channel)

        track = await fetch_track(query, ctx.author, self.bot.loop)
        if not track:
            return await ctx.send(embed=error_embed("Could not find that song.", bot=self.bot))

        if mq.is_playing() or mq.is_paused():
            mq.queue.append(track)
            embed = ghost_embed(
                title="➕ Added to Queue",
                description=f"[{track.title}]({track.webpage_url})",
                bot=self.bot
            )
            embed.add_field(name="Duration", value=track.duration_str, inline=True)
            embed.add_field(name="Position", value=str(len(mq.queue)), inline=True)
            return await ctx.send(embed=embed)

        mq.current = track
        source = mq.make_source()
        mq.voice_client.play(source, after=lambda e: self._after_play(ctx.guild.id, e))

        embed = ghost_embed(
            title="🎵 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            bot=self.bot
        )
        embed.add_field(name="Duration",     value=track.duration_str,    inline=True)
        embed.add_field(name="Requested by", value=ctx.author.mention,    inline=True)
        embed.add_field(name="Volume",       value=f"{int(mq.volume*100)}%", inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await ctx.send(embed=embed)

    # ── Skip ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="skip", description="Skip the current song")
    @commands.guild_only()
    async def skip(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        if not mq.is_playing() and not mq.is_paused():
            return await ctx.send(embed=error_embed("Nothing is playing.", bot=self.bot))
        mq.voice_client.stop()
        await ctx.send(embed=success_embed("⏭️ Skipped.", bot=self.bot))

    # ── Stop ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="stop", description="Stop music and clear the queue")
    @commands.guild_only()
    async def stop(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        mq.queue.clear()
        mq.current = None
        mq.loop = False
        if mq.voice_client:
            mq.voice_client.stop()
            await mq.voice_client.disconnect()
        self.bot.music_queues.pop(ctx.guild.id, None)
        await ctx.send(embed=success_embed("⏹️ Stopped and disconnected.", bot=self.bot))

    # ── Pause ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="pause", description="Pause the current song")
    @commands.guild_only()
    async def pause(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        if not mq.is_playing():
            return await ctx.send(embed=error_embed("Nothing is playing.", bot=self.bot))
        mq.voice_client.pause()
        await ctx.send(embed=success_embed("⏸️ Paused.", bot=self.bot))

    # ── Resume ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="resume", description="Resume a paused song")
    @commands.guild_only()
    async def resume(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        if not mq.is_paused():
            return await ctx.send(embed=error_embed("Nothing is paused.", bot=self.bot))
        mq.voice_client.resume()
        await ctx.send(embed=success_embed("▶️ Resumed.", bot=self.bot))

    # ── Queue ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="queue", description="Show the music queue")
    @commands.guild_only()
    async def queue(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        embed = ghost_embed(title="🎵 Music Queue", bot=self.bot)
        if mq.current:
            embed.add_field(
                name="Now Playing",
                value=f"[{mq.current.title}]({mq.current.webpage_url}) `{mq.current.duration_str}`",
                inline=False
            )
        if not mq.queue:
            embed.description = (embed.description or "") + "\n\nThe queue is empty."
        else:
            lines = []
            for i, t in enumerate(list(mq.queue)[:10], 1):
                lines.append(f"`{i}.` [{t.title}]({t.webpage_url}) `{t.duration_str}` — {t.requester.mention}")
            if len(mq.queue) > 10:
                lines.append(f"… and `{len(mq.queue) - 10}` more")
            embed.add_field(name=f"Up Next ({len(mq.queue)} tracks)", value="\n".join(lines), inline=False)
        embed.add_field(name="Loop",   value="✅" if mq.loop else "❌",      inline=True)
        embed.add_field(name="Volume", value=f"{int(mq.volume*100)}%",        inline=True)
        embed.add_field(name="Filter", value=mq.filter or "None",            inline=True)
        await ctx.send(embed=embed)

    # ── Now Playing ───────────────────────────────────────────────────────────
    @commands.hybrid_command(name="nowplaying", description="Show the currently playing song")
    @commands.guild_only()
    async def nowplaying(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        if not mq.current:
            return await ctx.send(embed=error_embed("Nothing is currently playing.", bot=self.bot))
        track = mq.current
        embed = ghost_embed(
            title="🎵 Now Playing",
            description=f"[{track.title}]({track.webpage_url})",
            bot=self.bot
        )
        embed.add_field(name="Duration",     value=track.duration_str,       inline=True)
        embed.add_field(name="Requested by", value=track.requester.mention,   inline=True)
        embed.add_field(name="Volume",       value=f"{int(mq.volume*100)}%", inline=True)
        embed.add_field(name="Filter",       value=mq.filter or "None",      inline=True)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await ctx.send(embed=embed)

    # ── Volume ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="volume", description="Set the playback volume (1–150)")
    @commands.guild_only()
    @app_commands.describe(volume="Volume level 1–150")
    async def volume(self, ctx, volume: int):
        if not 1 <= volume <= 150:
            return await ctx.send(embed=error_embed("Volume must be between 1 and 150.", bot=self.bot))
        mq = self._get_queue(ctx.guild.id)
        mq.volume = volume / 100
        if mq.voice_client and mq.voice_client.source:
            mq.voice_client.source.volume = mq.volume
        await ctx.send(embed=success_embed(f"Volume set to `{volume}%`.", bot=self.bot))

    # ── Filter ────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="filter", description="Apply an audio filter")
    @commands.guild_only()
    @app_commands.describe(name="Filter name: 8d, nightcore, vaporwave, bassboost, normalizer, off")
    async def filter(self, ctx, name: str):
        name = name.lower()
        mq = self._get_queue(ctx.guild.id)

        if name == "off":
            mq.filter = None
            msg = "Audio filter removed."
        elif name not in FILTERS:
            opts = ", ".join(FILTERS.keys())
            return await ctx.send(embed=error_embed(f"Unknown filter. Options: `{opts}`, `off`", bot=self.bot))
        else:
            mq.filter = name
            msg = f"Filter set to `{name}`."

        # Restart playback with new filter if something is playing
        if mq.is_playing() and mq.current:
            mq.voice_client.stop()
            source = mq.make_source()
            mq.voice_client.play(source, after=lambda e: self._after_play(ctx.guild.id, e))

        await ctx.send(embed=success_embed(msg, bot=self.bot))

    # ── Loop ──────────────────────────────────────────────────────────────────
    @commands.hybrid_command(name="loop", description="Toggle loop for the current song")
    @commands.guild_only()
    async def loop(self, ctx):
        mq = self._get_queue(ctx.guild.id)
        mq.loop = not mq.loop
        status = "enabled" if mq.loop else "disabled"
        await ctx.send(embed=success_embed(f"Loop **{status}**.", bot=self.bot))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild_id = member.guild.id
        mq = self.bot.music_queues.get(guild_id)
        if not mq or not mq.voice_client:
            return
        vc = mq.voice_client
        if vc.channel and len([m for m in vc.channel.members if not m.bot]) == 0:
            await asyncio.sleep(60)
            mq2 = self.bot.music_queues.get(guild_id)
            if mq2 and mq2.voice_client and mq2.voice_client.is_connected():
                if len([m for m in mq2.voice_client.channel.members if not m.bot]) == 0:
                    await mq2.voice_client.disconnect()
                    self.bot.music_queues.pop(guild_id, None)


async def setup(bot):
    await bot.add_cog(Music(bot))
