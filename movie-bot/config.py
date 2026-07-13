import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Comma-separated telegram user IDs of admins, e.g. "123456789,987654321"
ADMIN_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "").split(",")
    if uid.strip()
]

DB_PATH = os.getenv("DB_PATH", "movies.db")

# Your private channel's numeric ID (e.g. -1001234567890), used to auto-detect
# trailers/movies posted there. Leave empty to disable auto-detect.
_channel_id_raw = os.getenv("CHANNEL_ID", "").strip()
CHANNEL_ID = int(_channel_id_raw) if _channel_id_raw else None

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Check your .env file.")

if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is not set. Check your .env file.")
