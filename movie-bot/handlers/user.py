from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import database as db

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await db.touch_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await message.answer(
        "👋 Salom! Kanalda ko'rgan filmning raqamini yuboring, men sizga filmni jo'nataman.\n\n"
        "(Send me the number you saw on the channel, and I'll send you the movie.)"
    )


@router.message(F.text)
async def lookup_movie(message: Message):
    number = message.text.strip()

    # Ignore anything that isn't a plausible short code (avoid clashing with random text)
    if not number or len(number) > 20:
        return

    await db.touch_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    movie = await db.get_movie(number)

    if movie is None:
        await db.log_request(user_id=message.from_user.id, number=number, found=False)
        await message.answer(f"❌ {number} raqamli film topilmadi.\n(No movie found for number {number}.)")
        return

    await db.log_request(user_id=message.from_user.id, number=number, found=True)
    await message.answer_video(
        video=movie["file_id"],
        caption=movie["caption"] or f"🎬 {movie['number']}",
    )
