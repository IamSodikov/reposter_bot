# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FOLDER = os.path.join(BASE_DIR, "data")

INLINE_JSON_PATH = os.path.join(SESSION_FOLDER, "inline_keyboard_posts.json")
INLINE_MEDIA_FOLDER = os.path.join(SESSION_FOLDER, "inline_media")

API_ID = 13560279  # <-- Telegram API ID (https://my.telegram.org)
API_HASH = "c61de11ee09f1a6b6b8e6d3ef7ab11e6"  # <-- Telegram API Hash
BOT_TOKEN = "8167637162:AAGS5pWMxRSc3PJpl23RqoTme4kNlfSUsD0"  # <-- Bot token from @BotFather
