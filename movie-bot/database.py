import aiosqlite

from config import DB_PATH


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movies (
    number TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    caption TEXT,
    added_by INTEGER
);
"""

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    first_seen TEXT DEFAULT (datetime('now', '+5 hours')),
    last_seen TEXT DEFAULT (datetime('now', '+5 hours')),
    is_blocked INTEGER DEFAULT 0,
    blocked_at TEXT
);
"""

CREATE_REQUESTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    number TEXT NOT NULL,
    found INTEGER NOT NULL,
    requested_at TEXT DEFAULT (datetime('now', '+5 hours'))
);
"""

CREATE_BROADCAST_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS broadcast_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sent_at TEXT DEFAULT (datetime('now', '+5 hours'))
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.execute(CREATE_USERS_TABLE_SQL)
        await db.execute(CREATE_REQUESTS_TABLE_SQL)
        await db.execute(CREATE_BROADCAST_MESSAGES_TABLE_SQL)

        # Migration for DBs created before is_blocked/blocked_at existed
        for stmt in (
            "ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN blocked_at TEXT",
        ):
            try:
                await db.execute(stmt)
            except aiosqlite.OperationalError:
                pass  # column already exists

        await db.commit()


async def add_movie(number: str, file_id: str, caption: str | None, added_by: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO movies (number, file_id, caption, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(number) DO UPDATE SET
                file_id = excluded.file_id,
                caption = excluded.caption,
                added_by = excluded.added_by
            """,
            (number, file_id, caption, added_by),
        )
        await db.commit()


async def get_movie(number: str) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT number, file_id, caption FROM movies WHERE number = ?",
            (number,),
        )
        return await cursor.fetchone()


async def delete_movie(number: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM movies WHERE number = ?", (number,))
        await db.commit()
        return cursor.rowcount > 0


async def count_movies() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM movies")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_movies() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT number, caption FROM movies")
        return await cursor.fetchall()


async def touch_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """Record a user interaction: insert if new, update last_seen if existing.
    Also un-marks them as blocked, in case they'd blocked the bot before and came back."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen, is_blocked, blocked_at)
            VALUES (?, ?, ?, datetime('now', '+5 hours'), datetime('now', '+5 hours'), 0, NULL)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = datetime('now', '+5 hours'),
                is_blocked = 0,
                blocked_at = NULL
            """,
            (user_id, username, first_name),
        )
        await db.commit()


async def count_users() -> int:
    """Count active (non-blocked) users."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_active_user_ids() -> list[int]:
    """User IDs to actually send broadcasts to (excludes blocked users)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE is_blocked = 0")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def mark_user_blocked(user_id: int) -> None:
    """Mark a user as blocked instead of deleting them, so you keep a record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked = 1, blocked_at = datetime('now', '+5 hours') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_blocked_users() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, username, first_name, blocked_at FROM users "
            "WHERE is_blocked = 1 ORDER BY blocked_at DESC"
        )
        return await cursor.fetchall()


async def count_blocked_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def log_request(user_id: int, number: str, found: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (user_id, number, found) VALUES (?, ?, ?)",
            (user_id, number, 1 if found else 0),
        )
        await db.commit()


async def get_user_requests(user_id: int, limit: int = 20) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT number, found, requested_at FROM requests "
            "WHERE user_id = ? ORDER BY requested_at DESC LIMIT ?",
            (user_id, limit),
        )
        return await cursor.fetchall()


async def get_recent_requests(limit: int = 20) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT r.user_id, u.username, u.first_name, r.number, r.found, r.requested_at
            FROM requests r
            LEFT JOIN users u ON u.user_id = r.user_id
            ORDER BY r.requested_at DESC LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()


async def log_broadcast_message(broadcast_id: int, user_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO broadcast_messages (broadcast_id, user_id, message_id) VALUES (?, ?, ?)",
            (broadcast_id, user_id, message_id),
        )
        await db.commit()


async def get_broadcast_messages(broadcast_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, message_id FROM broadcast_messages WHERE broadcast_id = ?",
            (broadcast_id,),
        )
        return await cursor.fetchall()


async def delete_broadcast_messages_log(broadcast_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM broadcast_messages WHERE broadcast_id = ?",
            (broadcast_id,),
        )
        await db.commit()
