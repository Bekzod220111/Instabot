import re

from aiogram import Router, F
from aiogram.types import Message

from config import CHANNEL_ID
import database as db

router = Router()

# Matches an optional # then digits: "24", "#24", "Kino 24 - Titanik", etc.
NUMBER_PATTERN = re.compile(r"#?(\d+)")


def extract_number(caption: str | None) -> str | None:
    if not caption:
        return None
    match = NUMBER_PATTERN.search(caption)
    return match.group(1) if match else None


@router.channel_post(F.video)
async def handle_channel_video(message: Message):
    # Safety check: only react to posts from YOUR configured channel
    if CHANNEL_ID and message.chat.id != CHANNEL_ID:
        return

    number = extract_number(message.caption)
    if number is None:
        return  # no number found in caption, skip silently

    await db.add_movie(
        number=number,
        file_id=message.video.file_id,
        caption=message.caption,
        added_by=0,  # 0 marks "auto-added from channel"
    )


@router.channel_post(F.document)
async def handle_channel_document(message: Message):
    if CHANNEL_ID and message.chat.id != CHANNEL_ID:
        return

    number = extract_number(message.caption)
    if number is None:
        return

    await db.add_movie(
        number=number,
        file_id=message.document.file_id,
        caption=message.caption,
        added_by=0,
    )
