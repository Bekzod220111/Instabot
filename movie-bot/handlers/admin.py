import asyncio

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_IDS
from states import AddMovie, Broadcast
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
    total_blocked = await db.count_blocked_users()
    await message.answer(
        f"📊 Stats:\n"
        f"👥 Active users: {total_users}\n"
        f"🚫 Blocked: {total_blocked}\n"
        f"🎬 Movies: {total_movies}"
    )


@router.message(Command("blocked"))
async def cmd_blocked(message: Message):
    if not is_admin(message.from_user.id):
        return

    blocked_users = await db.get_blocked_users()

    if not blocked_users:
        await message.answer("No one has blocked the bot yet 🎉")
        return

    lines = ["🚫 Users who blocked the bot:\n"]
    for row in blocked_users:
        name = row["first_name"] or "Unknown"
        username = f"@{row['username']}" if row["username"] else "no username"
        lines.append(f"• {name} ({username}) — id: {row['user_id']}, blocked: {row['blocked_at']}")

    # Telegram messages have a ~4096 char limit; chunk if needed
    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i + 4000])


@router.message(Command("history"))
async def cmd_history(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /history <user_id>")
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("user_id must be a number.")
        return

    requests = await db.get_user_requests(user_id)

    if not requests:
        await message.answer(f"No search history found for user {user_id}.")
        return

    lines = [f"🔎 Search history for user {user_id}:\n"]
    for row in requests:
        status = "✅" if row["found"] else "❌"
        lines.append(f"{status} {row['number']} — {row['requested_at']}")

    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i + 4000])


@router.message(Command("recent"))
async def cmd_recent(message: Message):
    if not is_admin(message.from_user.id):
        return

    requests = await db.get_recent_requests(limit=30)

    if not requests:
        await message.answer("No searches logged yet.")
        return

    lines = ["🕐 Recent searches (all users):\n"]
    for row in requests:
        name = row["first_name"] or "Unknown"
        username = f"@{row['username']}" if row["username"] else f"id:{row['user_id']}"
        status = "✅" if row["found"] else "❌"
        lines.append(f"{status} {name} ({username}) searched {row['number']} — {row['requested_at']}")

    text = "\n".join(lines)
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i + 4000])


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    total_users = await db.count_users()
    await state.set_state(Broadcast.waiting_for_content)
    await message.answer(
        f"📢 Broadcast mode.\n\n"
        f"Send me anything (text, photo, video, etc.) and I'll send it to "
        f"all {total_users} users.\n\n"
        f"Send /cancel to abort."
    )


# --- Everything below reacts to state, and only runs if no command above matched ---

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
    await message.answer("Please send the number as text. (Or /cancel to stop.)")


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
    await message.answer("Please send a video file (or document). (Or /cancel to stop.)")


@router.message(Broadcast.waiting_for_content)
async def process_broadcast_content(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    user_ids = await db.get_active_user_ids()
    total = len(user_ids)

    if total == 0:
        await message.answer("No users to broadcast to yet.")
        return

    status_msg = await message.answer(f"📤 Sending to {total} users...")

    sent = 0
    blocked = 0
    failed = 0

    for user_id in user_ids:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            sent += 1
        except TelegramForbiddenError:
            # User blocked the bot or deleted their account — mark, don't delete
            blocked += 1
            await db.mark_user_blocked(user_id)
        except TelegramRetryAfter as e:
            # Telegram is asking us to slow down — wait and retry once
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                sent += 1
            except Exception:
                failed += 1
        except TelegramBadRequest:
            failed += 1

        # Stay comfortably under Telegram's ~30 msg/sec limit
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Broadcast finished.\n\n"
        f"Sent: {sent}\n"
        f"Blocked/removed: {blocked}\n"
        f"Failed: {failed}"
    )
