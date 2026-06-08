CREATE TABLE IF NOT EXISTS guild_config (
    guild_id            TEXT PRIMARY KEY,
    prefix              TEXT DEFAULT '-',
    modlog_channel      TEXT,
    jail_role           TEXT,
    mute_role           TEXT,
    welcome_channel     TEXT,
    welcome_message     TEXT DEFAULT 'Welcome {mention} to **{server}**! You are member #{memberCount}.',
    goodbye_channel     TEXT,
    goodbye_message     TEXT DEFAULT '**{user}** has left **{server}**.',
    autorole            TEXT,
    level_channel       TEXT,
    level_messages      INTEGER DEFAULT 1,
    antinuke_enabled    INTEGER DEFAULT 0,
    antinuke_threshold  INTEGER DEFAULT 3,
    antinuke_punish     TEXT DEFAULT 'ban',
    antinuke_whitelist  TEXT DEFAULT '[]',
    antiraid_enabled    INTEGER DEFAULT 0,
    antiraid_min_age    INTEGER DEFAULT 7,
    antiraid_no_avatar  INTEGER DEFAULT 0,
    antiraid_threshold  INTEGER DEFAULT 7
);

CREATE TABLE IF NOT EXISTS warns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    moderator_id    TEXT NOT NULL,
    reason          TEXT NOT NULL,
    timestamp       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS jail (
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    saved_roles     TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS levels (
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    xp              INTEGER DEFAULT 0,
    level           INTEGER DEFAULT 0,
    messages        INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS xp_cooldown (
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    last_message    INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS reaction_roles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    channel_id      TEXT NOT NULL,
    message_id      TEXT NOT NULL,
    emoji           TEXT NOT NULL,
    role_id         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS giveaways (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    channel_id      TEXT NOT NULL,
    message_id      TEXT,
    prize           TEXT NOT NULL,
    winner_count    INTEGER DEFAULT 1,
    host_id         TEXT NOT NULL,
    end_time        INTEGER NOT NULL,
    ended           INTEGER DEFAULT 0,
    entries         TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS tempbans (
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    expires_at      INTEGER NOT NULL,
    reason          TEXT,
    PRIMARY KEY (guild_id, user_id)
);
