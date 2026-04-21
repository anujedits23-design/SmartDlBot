import os
API_ID = os.environ.get("API_ID", "34446649")
API_HASH = os.environ.get("API_HASH", "8dc570c08d8e35e88fb9bfc73c65d7fa")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8730656807:AAEb61aU6vTWCTkdpy6SLQ36T4m573fIoWQ")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "7892805795")
try:
    ADMIN_IDS = list(map(int, ADMIN_IDS_RAW.split(",")))
except ValueError:
    raise ValueError("Invalid ADMIN_IDS. Must be comma-separated integers.")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://Anujedit:Anujedit@cluster0.7cs2nhd.mongodb.net/?appName=Cluster0")
# Command Prefix Support
COMMAND_PREFIX_RAW = os.getenv("COMMAND_PREFIX", "!|.|#|,|/")
COMMAND_PREFIX = [prefix.strip() for prefix in COMMAND_PREFIX_RAW.split("|") if prefix.strip()]

print("Loaded COMMAND_PREFIX:", COMMAND_PREFIX)

if not COMMAND_PREFIX:
    raise ValueError("Sorry Bro No Command Prefix Found. First Fix It!")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "5941bb8af55d4345rf97f616e325")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "408f04b237add2ba1b8bfc5da9eff8")

# YouTube cookies file path (if required for yt-dlp or similar)
YT_COOKIES_PATH = "./cookies/ItsSmartToolBot.txt"
