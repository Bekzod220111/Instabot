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
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    is_blocked INTEGER DEFAULT 0,
    blocked_at TEXT
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.execute(CREATE_USERS_TABLE_SQL)

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


async def touch_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """Record a user interaction: insert if new, update last_seen if existing.
    Also un-marks them as blocked, in case they'd blocked the bot before and came back."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen, is_blocked, blocked_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, NULL)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = CURRENT_TIMESTAMP,
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
            "UPDATE users SET is_blocked = 1, blocked_at = CURRENT_TIMESTAMP WHERE user_id = ?",
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
