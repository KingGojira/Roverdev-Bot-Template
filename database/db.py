import aiosqlite
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ghost.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open(SCHEMA_PATH, 'r') as f:
            await db.executescript(f.read())
        await db.commit()


# ─── Guild Config ─────────────────────────────────────────────────────────────

async def get_guild_config(guild_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def ensure_guild_config(guild_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
    return await get_guild_config(guild_id)


async def update_guild_config(guild_id: str, **kwargs) -> None:
    if not kwargs:
        return
    await ensure_guild_config(guild_id)
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [guild_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE guild_config SET {set_clause} WHERE guild_id = ?", values)
        await db.commit()


# ─── Warnings ─────────────────────────────────────────────────────────────────

async def add_warn(guild_id: str, user_id: str, moderator_id: str, reason: str) -> int:
    import time
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?,?,?,?,?)",
            (guild_id, user_id, moderator_id, reason, int(time.time()))
        )
        await db.commit()
        return cur.lastrowid


async def get_warns(guild_id: str, user_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (guild_id, user_id)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def remove_warn(warn_id: int, guild_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM warns WHERE id = ? AND guild_id = ?", (warn_id, guild_id))
        await db.commit()
        return cur.rowcount > 0


async def clear_warns(guild_id: str, user_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM warns WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()
        return cur.rowcount


# ─── Jail ─────────────────────────────────────────────────────────────────────

async def jail_member(guild_id: str, user_id: str, saved_roles: list[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO jail (guild_id, user_id, saved_roles) VALUES (?,?,?)",
            (guild_id, user_id, json.dumps(saved_roles))
        )
        await db.commit()


async def get_jail_data(guild_id: str, user_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM jail WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        row = await cur.fetchone()
        if row:
            data = dict(row)
            data['saved_roles'] = json.loads(data['saved_roles'])
            return data
        return None


async def unjail_member(guild_id: str, user_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM jail WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()


# ─── Levels ───────────────────────────────────────────────────────────────────

async def get_level_data(guild_id: str, user_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        row = await cur.fetchone()
        if row:
            return dict(row)
        return {'guild_id': guild_id, 'user_id': user_id, 'xp': 0, 'level': 0, 'messages': 0}


async def update_level_data(guild_id: str, user_id: str, xp: int, level: int, messages: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO levels (guild_id, user_id, xp, level, messages) VALUES (?,?,?,?,?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level, messages=excluded.messages",
            (guild_id, user_id, xp, level, messages)
        )
        await db.commit()


async def get_leaderboard(guild_id: str, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT ?",
            (guild_id, limit)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_xp_cooldown(guild_id: str, user_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT last_message FROM xp_cooldown WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def set_xp_cooldown(guild_id: str, user_id: str, timestamp: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO xp_cooldown (guild_id, user_id, last_message) VALUES (?,?,?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET last_message=excluded.last_message",
            (guild_id, user_id, timestamp)
        )
        await db.commit()


# ─── Reaction Roles ───────────────────────────────────────────────────────────

async def add_reaction_role(guild_id: str, channel_id: str, message_id: str, emoji: str, role_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reaction_roles (guild_id, channel_id, message_id, emoji, role_id) VALUES (?,?,?,?,?)",
            (guild_id, channel_id, message_id, emoji, role_id)
        )
        await db.commit()


async def get_reaction_roles(guild_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM reaction_roles WHERE guild_id = ?", (guild_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_reaction_role(message_id: str, emoji: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM reaction_roles WHERE message_id = ? AND emoji = ?",
            (message_id, emoji)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def remove_reaction_role(guild_id: str, message_id: str, emoji: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (guild_id, message_id, emoji)
        )
        await db.commit()
        return cur.rowcount > 0


# ─── Giveaways ────────────────────────────────────────────────────────────────

async def create_giveaway(guild_id: str, channel_id: str, prize: str, winner_count: int,
                           host_id: str, end_time: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, prize, winner_count, host_id, end_time) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, channel_id, prize, winner_count, host_id, end_time)
        )
        await db.commit()
        return cur.lastrowid


async def set_giveaway_message(giveaway_id: int, message_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id))
        await db.commit()


async def get_giveaway_by_id(giveaway_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,))
        row = await cur.fetchone()
        if row:
            data = dict(row)
            data['entries'] = json.loads(data['entries'])
            return data
        return None


async def get_giveaway_by_message(message_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM giveaways WHERE message_id = ?", (message_id,))
        row = await cur.fetchone()
        if row:
            data = dict(row)
            data['entries'] = json.loads(data['entries'])
            return data
        return None


async def update_giveaway_entries(giveaway_id: int, entries: list[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE giveaways SET entries = ? WHERE id = ?",
            (json.dumps(entries), giveaway_id)
        )
        await db.commit()


async def end_giveaway(giveaway_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,))
        await db.commit()


async def get_active_giveaways() -> list[dict]:
    import time
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ?", (int(time.time()),)
        )
        rows = await cur.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data['entries'] = json.loads(data['entries'])
            result.append(data)
        return result


# ─── Tempbans ─────────────────────────────────────────────────────────────────

async def add_tempban(guild_id: str, user_id: str, expires_at: int, reason: str = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO tempbans (guild_id, user_id, expires_at, reason) VALUES (?,?,?,?)",
            (guild_id, user_id, expires_at, reason)
        )
        await db.commit()


async def remove_tempban(guild_id: str, user_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()


async def get_expired_tempbans() -> list[dict]:
    import time
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tempbans WHERE expires_at <= ?", (int(time.time()),)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
