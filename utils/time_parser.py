import re

_UNITS = {
    's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
    'w': 604800, 'week': 604800, 'weeks': 604800,
}


def parse_time(time_str: str) -> int:
    """Parse a time string like '1d2h30m' into total seconds. Returns -1 on failure."""
    matches = re.findall(r'(\d+)\s*([a-zA-Z]+)', time_str.strip().lower())
    if not matches:
        try:
            return int(time_str)
        except ValueError:
            return -1

    total = 0
    for amount, unit in matches:
        if unit not in _UNITS:
            return -1
        total += int(amount) * _UNITS[unit]
    return total


def format_time(seconds: int) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s" if s else f"{m}m"
    elif seconds < 86400:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}h {m}m" if m else f"{h}h"
    else:
        d, rem = divmod(seconds, 86400)
        h = rem // 3600
        return f"{d}d {h}h" if h else f"{d}d"
