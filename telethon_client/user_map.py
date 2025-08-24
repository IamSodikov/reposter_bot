# telethon_client/user_map.py

import json
import os
from bot.logger import logger
from config import SESSION_FOLDER

MAP_FILE = os.path.join(SESSION_FOLDER, "user_map.json")

def load_user_map():
    if not os.path.exists(MAP_FILE):
        logger.warning(f"user_map.json not found: {MAP_FILE}")
        return {}
    try:
        with open(MAP_FILE, "r") as f:
            data = json.load(f)
        logger.info(f"user_map loaded: {len(data)} users")
        return data
    except Exception as e:
        logger.error(f"load_user_map error: {e}", exc_info=True)
        return {}

def save_user_map(data):
    try:
        with open(MAP_FILE, "w") as f:
            json.dump(data, f)
        logger.info(f"user_map saved: {len(data)} users")
    except Exception as e:
        logger.error(f"save_user_map error: {e}", exc_info=True)

def link_user_to_phone(user_id: int, phone: str):
    data = load_user_map()
    data[str(user_id)] = phone
    save_user_map(data)
    logger.info(f"User({user_id}) linked to phone: {phone}")

def get_phone_by_user(user_id: int) -> str | None:
    data = load_user_map()
    phone = data.get(str(user_id))
    logger.info(f"get_phone_by_user({user_id}): {phone}")
    return phone
