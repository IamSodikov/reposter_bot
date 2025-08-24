# telethon_client/channel_store.py

import json
import os
from config import SESSION_FOLDER
from bot.logger import logger

CHANNEL_FILE = os.path.join(SESSION_FOLDER, "channels.json")

def _load_data():
    if not os.path.exists(CHANNEL_FILE):
        logger.warning(f"CHANNEL_FILE yo'q: {CHANNEL_FILE}")
        return {}
    try:
        with open(CHANNEL_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"CHANNEL_FILE JSONDecodeError: {e}", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"CHANNEL_FILE open/read error: {e}", exc_info=True)
        return {}

def _save_data(data):
    try:
        with open(CHANNEL_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"CHANNEL_FILE saved: {CHANNEL_FILE}")
    except Exception as e:
        logger.error(f"CHANNEL_FILE save error: {e}", exc_info=True)

def get_channels(user_id: int) -> dict:
    if not os.path.exists(CHANNEL_FILE):
        logger.warning(f"channels.json not found for user {user_id}, returning empty")
        return {"channels": [], "source": None, "targets": []}
    try:
        with open(CHANNEL_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(user_id), {"channels": [], "source": None, "targets": []})
    except Exception as e:
        logger.error(f"get_channels error for user {user_id}: {e}", exc_info=True)
        return {"channels": [], "source": None, "targets": []}


def add_channel(user_id: int, username: str):
    data = _load_data()
    str_id = str(user_id)
    if str_id not in data or not isinstance(data[str_id], dict):
        data[str_id] = {
            "channels": [],
            "source": None,
            "targets": []
        }
    if username not in data[str_id]["channels"]:
        data[str_id]["channels"].append(username)
        logger.info(f"User({user_id}) channel added: {username}")
    _save_data(data)

def remove_user(user_id: int):
    data = _load_data()
    key = str(user_id)
    if key in data:
        del data[key]
        logger.info(f"User({user_id}) removed from channels.json")
    _save_data(data)

def remove_channel(user_id: int, username: str):
    data = _load_data()
    str_id = str(user_id)
    if str_id not in data:
        logger.warning(f"remove_channel: user {user_id} not found")
        return

    changed = False
    if "channels" in data[str_id] and username in data[str_id]["channels"]:
        data[str_id]["channels"].remove(username)
        changed = True
        logger.info(f"User({user_id}) channel removed: {username}")

    if data[str_id].get("source") == username:
        data[str_id]["source"] = None
        changed = True

    if "targets" in data[str_id] and username in data[str_id]["targets"]:
        data[str_id]["targets"].remove(username)
        changed = True

    if changed:
        _save_data(data)

def toggle_source(user_id: int, username: str):
    data = _load_data()
    str_id = str(user_id)

    if str_id not in data:
        logger.warning(f"toggle_source: user {user_id} not found")
        return

    if data[str_id].get("source") == username:
        data[str_id]["source"] = None
        logger.info(f"User({user_id}) unset source channel: {username}")
    else:
        data[str_id]["source"] = username
        logger.info(f"User({user_id}) set source channel: {username}")

    _save_data(data)

def toggle_target(user_id: int, username: str):
    data = _load_data()
    str_id = str(user_id)

    if str_id not in data:
        logger.warning(f"toggle_target: user {user_id} not found")
        return

    targets = data[str_id].get("targets", [])

    if username in targets:
        targets.remove(username)
        logger.info(f"User({user_id}) removed target: {username}")
    else:
        targets.append(username)
        logger.info(f"User({user_id}) added target: {username}")

    data[str_id]["targets"] = targets
    _save_data(data)

def set_time(user_id: int, start: str, end: str, utc_offset: int = None):
    data = _load_data()
    str_id = str(user_id)

    if str_id not in data:
        data[str_id] = {}

    # UTC offsetni ham saqlaymiz
    data[str_id]["time"] = {"start": start, "end": end, "utc_offset": utc_offset}
    logger.info(f"User({user_id}) set time: {start} - {end}, utc_offset: {utc_offset}")
    _save_data(data)

