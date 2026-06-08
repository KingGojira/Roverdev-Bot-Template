import discord

GHOST_COLOR   = 0x2b2d31
ERROR_COLOR   = 0xe74c3c
SUCCESS_COLOR = 0x57f287
WARNING_COLOR = 0xfee75c
INFO_COLOR    = 0x5865f2


def _apply_footer(embed: discord.Embed, bot=None) -> discord.Embed:
    if bot and bot.user:
        embed.set_footer(text="👻 Ghost", icon_url=bot.user.display_avatar.url)
    else:
        embed.set_footer(text="👻 Ghost")
    return embed


def ghost_embed(title: str = None, description: str = None,
                color: int = GHOST_COLOR, bot=None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    return _apply_footer(embed, bot)


def success_embed(description: str, title: str = None, bot=None) -> discord.Embed:
    embed = discord.Embed(
        title=title or "✅ Success",
        description=description,
        color=SUCCESS_COLOR
    )
    return _apply_footer(embed, bot)


def error_embed(description: str, title: str = None, bot=None) -> discord.Embed:
    embed = discord.Embed(
        title=title or "❌ Error",
        description=description,
        color=ERROR_COLOR
    )
    return _apply_footer(embed, bot)


def warning_embed(description: str, title: str = None, bot=None) -> discord.Embed:
    embed = discord.Embed(
        title=title or "⚠️ Warning",
        description=description,
        color=WARNING_COLOR
    )
    return _apply_footer(embed, bot)


def info_embed(title: str, description: str = None, bot=None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=INFO_COLOR)
    return _apply_footer(embed, bot)


def progress_bar(current: int, total: int, length: int = 20) -> str:
    filled = int(length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (length - filled)
    return f"`{bar}` {current}/{total}"
