from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_IDS
from states import AddMovie
import database as db

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return  # silently ignore non-admins

    await state.set_state(AddMovie.waiting_for_number)
    await message.answer(
        "OK, let's add a new movie.\n\n"
        "Send me the number to assign to it (e.g. 24)."
    )


@router.message(AddMovie.waiting_for_number, F.text)
async def process_number(message: Message, state: FSMContext):
    number = message.text.strip()

    if not number:
        await message.answer("Please send a valid number/code.")
        return

    existing = await db.get_movie(number)
    if existing:
        await message.answer(
            f"⚠️ Number `{number}` is already used. Sending a new video will overwrite it.\n"
            "Now send me the video file.",
            parse_mode="Markdown",
        )
    else:
        await message.answer(f"Got it, number: {number}\nNow send me the video file.")

    await state.update_data(number=number)
    await state.set_state(AddMovie.waiting_for_video)


@router.message(AddMovie.waiting_for_number)
async def process_number_invalid(message: Message):
    await message.answer("Please send the number as text.")


@router.message(AddMovie.waiting_for_video, F.video)
async def process_video(message: Message, state: FSMContext):
    data = await state.get_data()
    number = data["number"]

    file_id = message.video.file_id
    caption = message.caption

    await db.add_movie(
        number=number,
        file_id=file_id,
        caption=caption,
        added_by=message.from_user.id,
    )

    await message.answer(f"✅ Movie saved under number {number}.")
    await state.clear()


@router.message(AddMovie.waiting_for_video, F.document)
async def process_document_as_video(message: Message, state: FSMContext):
    # In case the movie was uploaded/forwarded as a document/file instead of native video
    data = await state.get_data()
    number = data["number"]

    file_id = message.document.file_id
    caption = message.caption

    await db.add_movie(
        number=number,
        file_id=file_id,
        caption=caption,
        added_by=message.from_user.id,
    )

    await message.answer(f"✅ Movie (as document) saved under number {number}.")
    await state.clear()


@router.message(AddMovie.waiting_for_video)
async def process_video_invalid(message: Message):
    await message.answer("Please send a video file (or document).")


@router.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /delete <number>")
        return

    number = args[1].strip()
    deleted = await db.delete_movie(number)

    if deleted:
        await message.answer(f"🗑️ Deleted movie number {number}.")
    else:
        await message.answer(f"No movie found with number {number}.")


@router.message(Command("count"))
async def cmd_count(message: Message):
    if not is_admin(message.from_user.id):
        return

    total = await db.count_movies()
    await message.answer(f"📦 Total movies stored: {total}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    total_movies = await db.count_movies()
    total_users = await db.count_users()
    await message.answer(
        f"📊 Stats:\n"
        f"👥 Users: {total_users}\n"
        f"🎬 Movies: {total_movies}"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return

    await state.clear()
    await message.answer("❌ Cancelled.")
