import threading
import subprocess
import sys
from app import app


def run_bot():
    # Run your Telegram bot (main.py)
    subprocess.run([sys.executable, "main.py"])


# Start bot in background thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()


if __name__ == "__main__":
    # Run Flask web server (for uptime / health check)
    app.run(host="0.0.0.0", port=5000)
