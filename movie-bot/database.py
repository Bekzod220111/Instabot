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
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.execute(CREATE_USERS_TABLE_SQL)
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
    """Record a user interaction: insert if new, update last_seen if existing."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = CURRENT_TIMESTAMP
            """,
            (user_id, username, first_name),
        )
        await db.commit()


async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0
