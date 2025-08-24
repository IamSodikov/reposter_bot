import os
import json
from asyncio import Lock
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config import API_ID, API_HASH, SESSION_FOLDER
from bot.logger import logger
from telethon_client.user_map import get_phone_by_user as map_get_phone_by_user

# Universal user-based lock manager
_user_session_locks: dict[str, Lock] = {}

async def with_session_lock(phone: str, func, *args, **kwargs):
    """Har bir telefon raqam uchun yagona lock, har qanday TelethonClient handlerni safe tarzda ishlatadi."""
    if phone not in _user_session_locks:
        _user_session_locks[phone] = Lock()
    async with _user_session_locks[phone]:
        return await func(*args, **kwargs)

def get_session_file_path(phone: str) -> str:
    return os.path.join(SESSION_FOLDER, f"{phone}")

def session_exists(phone: str) -> bool:
    session_path = get_session_file_path(phone)
    exists = os.path.exists(f"{session_path}.session")
    logger.info(f"session_exists({phone}): {exists}")
    return exists

def save_user_session(user_id: int, phone: str):
    path = os.path.join(SESSION_FOLDER, "session_store.json")
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = {}
        data[str(user_id)] = phone
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"User({user_id}) session mapping saved: {phone}")
    except Exception as e:
        logger.error(f"save_user_session error: {e}", exc_info=True)

def get_phone_by_user(user_id: int) -> str | None:
    logger.info(f"[session_manager] get_phone_by_user called for user_id={user_id}")
    phone = map_get_phone_by_user(user_id)  # user_map ichida ham tekshiruv+log bor
    logger.info(f"[session_manager] get_phone_by_user result: {phone}")
    return phone

# === TELETHON ASOSHIY HANDLERLARINI UNIVERSAL LOCK ICHIDA QILING! ===

async def start_login(phone: str) -> tuple[TelegramClient, str]:
    """Raqam kirgandan keyin: kod yuboriladi. Lock bilan faqat bitta client ishlaydi."""
    session_name = get_session_file_path(phone)
    async def do_login():
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        logger.info(f"[DEBUG] Trying to send_code_request to: {phone}")
        sent_code = await client.send_code_request(phone)
        logger.info(f"[DEBUG] send_code_request response: {sent_code}")
        phone_code_hash = sent_code.phone_code_hash
        logger.info(f"start_login: code sent to {phone}")
        return client, phone_code_hash
    return await with_session_lock(phone, do_login)

async def complete_login(client: TelegramClient, phone: str, code: str, phone_code_hash: str, password: str = None):
    try:
        if password:
            await client.sign_in(password=password)
            logger.info(f"complete_login: user logged in (2FA) with {phone}")
        else:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            logger.info(f"complete_login: user logged in with {phone}")
    except SessionPasswordNeededError:
        logger.error("Требуется облачный пароль (2FA), но не предоставлен.")
        # Bu yerda disconnect QILMAYMIZ! RAMda ochiq qoladi!
        raise Exception("🔑 Для входа требуется облачный пароль (2FA). Пожалуйста, введите пароль:")
    except Exception as e:
        logger.error(f"complete_login error: {e}", exc_info=True)
        await client.disconnect()   # faqat haqiqiy xatoda disconnect qilamiz
        raise
    else:
        await client.disconnect()   # successda disconnect qilamiz

async def get_client(user_id: int) -> TelegramClient:
    """Istalgan vaqtda userning to‘liq connect bo‘lgan TelegramClient obyektini beradi. Doim lock ichida!"""
    phone = get_phone_by_user(user_id)
    if not phone:
        logger.error(f"get_client: No phone for user_id {user_id}")
        raise Exception("📛 Telefon raqam topilmadi (session bog‘lamasi yo‘q)")

    session_name = get_session_file_path(phone)
    if not os.path.exists(f"{session_name}.session"):
        logger.error(f"get_client: Session file not found: {session_name}")
        raise FileNotFoundError(f"❌ Session file topilmadi: {session_name}")

    async def _connect():
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        logger.info(f"get_client: connected for user_id {user_id}")
        return client
    return await with_session_lock(phone, _connect)

async def logout(phone: str):
    """Foydalanuvchini Telegramdan logout qilish va sessionni tozalash."""
    session_name = get_session_file_path(phone)
    async def _logout():
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        await client.log_out()
        await client.disconnect()
        logger.info(f"logout: logged out and disconnected for {phone}")

        if os.path.exists(f"{session_name}.session"):
            os.remove(f"{session_name}.session")
            logger.info(f"logout: session file removed for {phone}")

        path = os.path.join(SESSION_FOLDER, "session_store.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            data = {k: v for k, v in data.items() if v != phone}
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"logout: user removed from session_store.json ({phone})")
    await with_session_lock(phone, _logout)
