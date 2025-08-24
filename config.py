# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FOLDER = os.path.join(BASE_DIR, "data")

INLINE_JSON_PATH = os.path.join(SESSION_FOLDER, "inline_keyboard_posts.json")
INLINE_MEDIA_FOLDER = os.path.join(SESSION_FOLDER, "inline_media")

API_ID = "your api id"  # <-- Telegram API ID (https://my.telegram.org)
API_HASH = "your api hash"  # <-- Telegram API Hash
BOT_TOKEN = "your bot token"  # <-- Bot token from @BotFather
