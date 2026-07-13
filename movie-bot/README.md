# Movie Code Bot

A Telegram bot that lets your channel subscribers send a number (the code you
post next to each movie on your channel) and get the actual movie file back
in a private chat.

## How it works

- **Auto-detect from your channel (recommended)**: add the bot as an admin
  in your private channel. Post the trailer/movie there with the number
  somewhere in the caption (`24`, `#24`, `Kino 24 - Titanik` all work). The
  bot automatically picks it up — no manual step needed.
- **Manual add (fallback)**: send `/add`, then the number, then the video
  file, directly to the bot in a private chat.
- **Users**: send a plain number (e.g. `24`) to the bot in private, and it
  replies with the matching video.

Telegram's `file_id` is reusable forever (as long as the bot doesn't change
and the file isn't deleted from Telegram's servers), so you only need to
upload each movie once — the bot never re-downloads or re-uploads the file
after that.

## Project structure

```
movie-bot/
├── bot.py              # entry point
├── config.py           # loads .env
├── database.py         # aiosqlite queries
├── states.py            # FSM states for /add flow
├── handlers/
│   ├── admin.py        # /add, /delete, /count, /cancel
│   └── user.py         # /start + number lookup
├── requirements.txt
└── .env.example
```

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.

2. Find your own Telegram numeric user ID (send a message to
   [@userinfobot](https://t.me/userinfobot)) — this goes in `ADMIN_IDS`.

3. Install dependencies:
   ```bash
   pip install -r requirements.txt --break-system-packages
   ```

4. Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```
   ```
   BOT_TOKEN=123456:ABC-your-real-token
   ADMIN_IDS=111111111,222222222
   DB_PATH=movies.db
   ```

5. **(Optional but recommended) Set up channel auto-detect:**
   - Add your bot as an **admin** in your private channel (Channel Settings →
     Administrators → Add Admin → search your bot).
   - Get your channel's numeric ID: forward any message from the channel to
     [@userinfobot](https://t.me/userinfobot) or
     [@getidsbot](https://t.me/getidsbot) — it'll be a negative number like
     `-1001234567890`.
   - Add it to `.env`:
     ```
     CHANNEL_ID=-1001234567890
     ```
   - Now, whenever you post a trailer/movie in the channel with a number in
     the caption, the bot saves it automatically. No admin action needed.

6. Run it:
   ```bash
   python bot.py
   ```

## Usage

**Adding a movie (admin only, in a private chat with the bot):**
```
/add
> 24
(send the video file)
✅ Movie saved under number 24.
```

**A user looking up a movie:**
```
24
```
→ bot replies with the video.

**Other admin commands:**
- `/delete <number>` — remove a movie
- `/count` — see how many movies are stored
- `/cancel` — cancel an in-progress `/add`

## Notes on scaling this up

- Right now `/add` requires you to manually watch the channel and copy each
  video into the bot one at a time. If that becomes tedious, the next step
  is making the bot a **channel admin** so it can read channel posts
  directly (via `channel_post` updates) and auto-register videos — you'd
  still assign the number, but you wouldn't need to re-upload/forward the
  file.
- For deployment on PythonAnywhere: this bot uses **long polling**
  (`start_polling`), which needs a persistently running process. PythonAnywhere's
  free tier doesn't support always-on background tasks — you'd need at least
  a paid "Always-on task", or a VPS. Let me know if you want to set that part
  up.
- SQLite is fine for this use case (single bot process, moderate traffic).
  If you outgrow it, moving to Postgres is a small change since the query
  layer is already isolated in `database.py`.
