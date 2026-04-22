import os
import time
import asyncio
import logging
from pathlib import Path

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------- CONFIG ----------------
class Config:
    TEMP_DIR = Path("temp")
    COOKIES_FILE = "cookies.txt"

Config.TEMP_DIR.mkdir(exist_ok=True)


# ---------------- RATE LIMIT ----------------
class RateLimiter:
    def __init__(self, delay=1.5):
        self.delay = delay
        self.last = 0

    async def wait(self):
        now = time.time()
        if now - self.last < self.delay:
            await asyncio.sleep(self.delay - (now - self.last))
        self.last = time.time()


rate_limiter = RateLimiter()


# ---------------- PROGRESS FUNCTION ----------------
async def progress(current, total, message: Message, start_time):
    if total == 0:
        return

    percent = int(current * 100 / total)

    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0

    remaining = (total - current) / speed if speed > 0 else 0

    bar_length = 10
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)

    text = (
        f"📥 Downloading...\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚡ {percent}% [{bar}]\n"
        f"🚀 Speed: {speed/1024/1024:.2f} MB/s\n"
        f"⏳ ETA: {int(remaining)} sec"
    )

    try:
        await message.edit_text(text)
    except:
        pass


# ---------------- BOT CORE ----------------
class YouTubeBot:

    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.store = {}
        self.cache = {}
        self.search_cache = {}

    # ---------------- SEARCH ----------------
    async def search(self, query: str):

        if query in self.search_cache:
            return self.search_cache[query]

        await rate_limiter.wait()

        def _run():
            opts = {
                'quiet': True,
                'default_search': 'ytsearch5',
                'noplaylist': True,
            }

            if os.path.exists(Config.COOKIES_FILE):
                opts['cookiefile'] = Config.COOKIES_FILE

            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(query, download=False)

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _run)

            entries = (info or {}).get("entries") or []

            for e in entries:
                if e and e.get("webpage_url"):
                    url = e["webpage_url"]
                    self.search_cache[query] = url
                    return url

        except Exception as e:
            logger.error(f"Search error: {e}")

        return None

    # ---------------- FORMATS ----------------
    def formats(self, url):

        if url in self.cache:
            return self.cache[url]

        opts = {'quiet': True, 'noplaylist': True}

        if os.path.exists(Config.COOKIES_FILE):
            opts['cookiefile'] = Config.COOKIES_FILE

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []

        for f in info.get("formats", []):
            if f.get("height"):
                formats.append({
                    "id": f["format_id"],
                    "quality": f"{f['height']}p"
                })

        seen = set()
        clean = []

        for f in formats:
            if f["quality"] not in seen:
                seen.add(f["quality"])
                clean.append(f)

        self.cache[url] = clean[:8]
        return clean[:8]

    # ---------------- DOWNLOAD ----------------
    async def download(self, url, format_id, status_msg=None):

        await rate_limiter.wait()

        def _dl():
            start = time.time()
            loop = asyncio.get_event_loop()
            last_update = 0

            def hook(d):
                nonlocal last_update

                if d.get('status') == 'downloading':
                    now = time.time()

                    if now - last_update < 1:
                        return

                    last_update = now

                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0

                    asyncio.run_coroutine_threadsafe(
                        progress(downloaded, total, status_msg, start),
                        loop
                    )

            opts = {
                'format': format_id,
                'outtmpl': str(self.temp_dir / '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'progress_hooks': [hook],
                'retries': 10,
                'fragment_retries': 10,
            }

            if os.path.exists(Config.COOKIES_FILE):
                opts['cookiefile'] = Config.COOKIES_FILE

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file = ydl.prepare_filename(info)
                return file, info.get("title", "Video")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _dl)


ytbot = YouTubeBot(Config.TEMP_DIR)


# ---------------- HANDLERS ----------------
def setup_handlers(app: Client):

    @app.on_message(filters.command("yt"))
    async def yt(client: Client, message: Message):

        if len(message.command) < 2:
            return await message.reply("❌ Send video name or link")

        query = message.text.split(maxsplit=1)[1]

        status = await message.reply("🔍 Searching... 🎬")

        url = query if query.startswith("http") else await ytbot.search(query)

        if not url:
            return await status.edit("❌ No Video Found 😢")

        formats = ytbot.formats(url)

        if not formats:
            return await status.edit("❌ No formats available")

        uid = str(time.time())
        ytbot.store[uid] = url

        buttons = [
            [InlineKeyboardButton(f"🎥 {f['quality']}", callback_data=f"yt|{f['id']}|{uid}")]
            for f in formats
        ]

        await status.edit(
            "🎬 Select Quality 👇",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ---------------- CALLBACK ----------------
    @app.on_callback_query(filters.regex("^yt\\|"))
    async def callback(client: Client, query: CallbackQuery):

        _, format_id, uid = query.data.split("|")

        url = ytbot.store.get(uid)

        if not url:
            return await query.message.edit("❌ Session expired")

        status_msg = query.message

        await query.message.edit("📥 Downloading... 🎬")

        file, title = await ytbot.download(url, format_id, status_msg)

        if not file:
            return await query.message.edit("❌ Download Failed 😢")

        await client.send_video(
            chat_id=query.message.chat.id,
            video=file,
            caption=f"🎬 **{title}**\n🔥 Downloaded Successfully",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            os.remove(file)
        except:
            pass

        await query.message.delete()


# ---------------- INIT WRAPPER ----------------
def setup_downloader_handler(app: Client):
    setup_handlers(app)
