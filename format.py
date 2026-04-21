import yt_dlp
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ----------------------------
# PLATFORM DETECTOR
# ----------------------------
def detect_platform(url: str):
    url = url.lower()

    if "youtube" in url or "youtu.be" in url:
        return "youtube"
    elif "instagram" in url:
        return "instagram"
    elif "facebook" in url:
        return "facebook"
    elif "tiktok" in url:
        return "tiktok"
    elif "pinterest" in url:
        return "pinterest"
    elif "spotify" in url:
        return "spotify"
    else:
        return "unknown"


# ----------------------------
# FETCH INFO
# ----------------------------
def fetch_info(url: str):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


# ----------------------------
# FORMAT EXTRACTOR (FIXED)
# ----------------------------
def extract_formats(info):
    formats = []

    for f in info.get("formats", []):
        if f.get("vcodec") != "none":

            height = f.get("height") or 0

            formats.append({
                "id": f.get("format_id"),
                "res": height,
                "ext": f.get("ext"),
                "size": f.get("filesize_approx") or f.get("filesize") or 0
            })

    # remove duplicates safely
    seen = set()
    clean = []

    for f in sorted(formats, key=lambda x: x["res"], reverse=True):
        if f["res"] not in seen:
            seen.add(f["res"])
            clean.append(f)

    return clean


# ----------------------------
# UNIVERSAL UI BUILDER
# ----------------------------
def build_quality_ui(url: str):
    platform = detect_platform(url)

    # Spotify → audio only
    if platform == "spotify":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Download Audio", callback_data=f"audio|{url}")]
        ])

    try:
        info = fetch_info(url)
        formats = extract_formats(info)
    except:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Best Quality", callback_data=f"fast|{url}")]
        ])

    buttons = []

    # ---------------- YOUTUBE ----------------
    if platform == "youtube":
        for f in formats[:10]:
            label = f"📹 {f['res']}p" if f["res"] else "📹 Unknown"
            buttons.append([
                InlineKeyboardButton(label, callback_data=f"vid|{url}|{f['id']}")
            ])

        buttons.append([
            InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"audio|{url}")
        ])

    # ---------------- OTHER PLATFORMS ----------------
    else:
        if formats:
            for f in formats[:6]:
                label = f"📹 {f['res']}p" if f["res"] else "📥 Best Quality"
                buttons.append([
                    InlineKeyboardButton(label, callback_data=f"vid|{url}|{f['id']}")
                ])
        else:
            buttons.append([
                InlineKeyboardButton("📥 Best Quality", callback_data=f"fast|{url}")
            ])

    return InlineKeyboardMarkup(buttons)


# ----------------------------
# HELPER
# ----------------------------
def get_platform(url: str):
    return detect_platform(url)
