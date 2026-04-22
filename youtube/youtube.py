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
    def __init__(self, delay=2):
        self.delay = delay
        self.last = 0

    async def wait(self):
        now = time.time()
        if now - self.last < self.delay:
            await asyncio.sleep(self.delay - (now - self.last))
        self.last = time.time()


rate_limiter = RateLimiter(2)


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

            entries = info.get("entries", []) if info else []

            for e in entries:
                if e and e.get("webpage_url"):
                    self.search_cache[query] = e["webpage_url"]
                    return e["webpage_url"]

        except Exception as e:
            logger.error(f"Search error: {e}")

        return None

    # ---------------- FORMAT LIST ----------------
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
    async def download(self, url, format_id):

        await rate_limiter.wait()

        def _dl():
            opts = {
                'format': format_id,
                'outtmpl': str(self.temp_dir / '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'retries': 10,
                'fragment_retries': 10,
                'concurrent_fragment_downloads': 3
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

    # ================= /yt =================
    @app.on_message(filters.command("yt"))
    async def yt(client: Client, message: Message):

        if len(message.command) < 2:
            return await message.reply("❌ Send video name or link")

        query = message.text.split(maxsplit=1)[1]

        status = await message.reply("🔍 Searching video... 🎬")

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
            "🎬 **Select Quality 👇**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ================= /song =================
    @app.on_message(filters.command("song"))
    async def song(client: Client, message: Message):

        if len(message.command) < 2:
            return await message.reply("❌ Send song name or link")

        query = message.text.split(maxsplit=1)[1]

        status = await message.reply("🎧 Searching song... 🎶")

        url = query if query.startswith("http") else await ytbot.search(query)

        if not url:
            return await status.edit("❌ No Song Found 😢")

        file, title = await ytbot.download(url, "bestaudio")

        caption = f"""
🎵 **{title}**
━━━━━━━━━━━━━━
✨ Downloaded Successfully 💥
"""

        await client.send_audio(
            chat_id=message.chat.id,
            audio=file,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )

        os.remove(file)
        await status.delete()

    # ================= CALLBACK =================
    @app.on_callback_query(filters.regex("^yt\\|"))
    async def callback(client: Client, query: CallbackQuery):

        _, format_id, uid = query.data.split("|")

        url = ytbot.store.get(uid)

        if not url:
            return await query.message.edit("❌ Session expired")

        await query.message.edit("📥 Downloading... 🎬")

        file, title = await ytbot.download(url, format_id)

        caption = f"""
🎬 **{title}**
━━━━━━━━━━━━━━
⚡ Quality Selected
🔥 Downloaded Successfully
"""

        await client.send_video(
            chat_id=query.message.chat.id,
            video=file,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )

        os.remove(file)
        await query.message.delete()
