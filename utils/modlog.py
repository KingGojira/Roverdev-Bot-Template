import discord
from database import db

_COLORS = {
    'BAN':       0xe74c3c,
    'UNBAN':     0x57f287,
    'KICK':      0xe67e22,
    'MUTE':      0x9b59b6,
    'UNMUTE':    0x57f287,
    'WARN':      0xfee75c,
    'CLEARWARNS':0x57f287,
    'JAIL':      0x95a5a6,
    'UNJAIL':    0x57f287,
    'TEMPBAN':   0xe74c3c,
    'SOFTBAN':   0xe67e22,
    'HARDBAN':   0xe74c3c,
    'TIMEOUT':   0x9b59b6,
    'UNTIMEOUT': 0x57f287,
    'PURGE':     0x3498db,
    'LOCK':      0xe74c3c,
    'UNLOCK':    0x57f287,
    'SLOWMODE':  0x3498db,
    'STRIPSTAFF':0xe67e22,
}


async def log_action(guild: discord.Guild, action: str, target, moderator,
                     reason: str = "No reason provided", extra: str = None) -> None:
    config = await db.get_guild_config(str(guild.id))
    if not config or not config.get('modlog_channel'):
        return

    channel = guild.get_channel(int(config['modlog_channel']))
    if not channel:
        return

    color = _COLORS.get(action.upper(), 0x2b2d31)
    embed = discord.Embed(title=f"🔨 {action.title()}", color=color,
                          timestamp=discord.utils.utcnow())
    embed.add_field(name="Target",
                    value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="Moderator",
                    value=f"{moderator.mention} (`{moderator.id}`)", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    if extra:
        embed.add_field(name="Additional Info", value=extra, inline=False)
    if hasattr(target, 'display_avatar'):
        embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="👻 Ghost")

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
