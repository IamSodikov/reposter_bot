import os
import json
from bot.logger import logger
from telethon.tl.types import DocumentAttributeVideo
import asyncio
from config import INLINE_JSON_PATH, INLINE_MEDIA_FOLDER


async def wait_for_complete_file(file_path, max_wait=3, check_interval=0.1):
    """
    Fayl to‘liq yozilishini kutadi. Fayl hajmi o‘zgarmay qolgunga qadar kutadi.
    max_wait: maksimal kutish vaqti (sekund)
    check_interval: tekshirish oralig‘i (sekund)
    """
    waited = 0
    last_size = -1
    while waited < max_wait:
        if not os.path.exists(file_path):
            await asyncio.sleep(check_interval)
            waited += check_interval
            continue
        current_size = os.path.getsize(file_path)
        if current_size > 0 and current_size == last_size:
            return True  # Fayl to‘liq
        last_size = current_size
        await asyncio.sleep(check_interval)
        waited += check_interval
    return False

async def save_inline_keyboard_post(msg, client):
    """
    Keyboardli postni json faylga (har doim update!), media bo‘lsa - faylga saqlaydi.
    """

    try:
        msg = await client.get_messages(msg.chat_id, ids=msg.id)
    except Exception as e:
        logger.error(f"msg qayta olishda xatolik: {e}", exc_info=True)
        return

    if not getattr(msg, "reply_markup", None):
        return

    # Papka borligini tekshir
    if not os.path.exists(INLINE_MEDIA_FOLDER):
        try:
            os.makedirs(INLINE_MEDIA_FOLDER)
            logger.info(f"INLINE_MEDIA_FOLDER created: {INLINE_MEDIA_FOLDER}")
        except Exception as e:
            logger.error(f"Cannot create INLINE_MEDIA_FOLDER: {e}", exc_info=True)
            return

    # Eski json'ni o‘qib olamiz
    if os.path.exists(INLINE_JSON_PATH):
        try:
            with open(INLINE_JSON_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                data = json.loads(content) if content else []
        except Exception as e:
            logger.error(f"Error reading {INLINE_JSON_PATH}: {e}", exc_info=True)
            data = []
    else:
        data = []

    # Default post_data
    post_data = {
        "id": msg.id,
        "date": msg.date.isoformat(),
        "text": msg.raw_text or msg.message or "",
        "media_type": str(type(msg.media)).split("'")[1] if msg.media else None,
        "media_path": None,
        "reply_markup": msg.reply_markup.to_dict() if hasattr(msg.reply_markup, "to_dict") else str(msg.reply_markup),
        "is_round_video": False  # ✅ Default False
    }

    # MEDIA bo‘lsa yuklab olamiz
    if msg.media:
        extension = None
        filename = None
        try:
            if hasattr(msg.media, "photo") and msg.media.photo:
                try:
                    # Faylni papkaga, avtomatik nom bilan saqlaymiz
                    downloaded_path = await client.download_media(msg, file=INLINE_MEDIA_FOLDER)
                    complete = await wait_for_complete_file(downloaded_path)
                    if not complete:
                        logger.error(f"Photo fayl to‘liq emas yoki hali yozilmoqda: {downloaded_path}")
                        return
                    else:
                        logger.info(f"Photo downloaded: {downloaded_path}")
                        post_data["media_path"] = downloaded_path
                except Exception as e:
                    logger.error(f"Photo download error: {e}", exc_info=True)
                    return

            elif hasattr(msg.media, "document") and msg.media.document:
                mime = getattr(msg.media.document, "mime_type", "")
                if not mime:
                    logger.warning(f"mime_type yo‘q, media SKIP qilindi: msg_id={msg.id}")
                    return
                if "video" in mime:
                    extension = "mp4"
                elif "image" in mime:
                    extension = "jpg"
                elif "pdf" in mime:
                    extension = "pdf"
                elif "gif" in mime:
                    extension = "gif"
                else:
                    logger.warning(f"Noma’lum mime_type ({mime}), media SKIP qilindi: msg_id={msg.id}")
                    return
                try:
                    for attr in msg.media.document.attributes:
                        if isinstance(attr, DocumentAttributeVideo) and getattr(attr, "round_message", False):
                            post_data["is_round_video"] = True
                except Exception as e:
                    logger.error(f"Round video aniqlashda xatolik: {e}")
                if extension:
                    filename = f"{msg.id}.{extension}"
                    file_path = os.path.join(INLINE_MEDIA_FOLDER, filename)
                    if not os.path.exists(file_path):
                        await client.download_media(msg, file_path)
                        logger.info(f"Media downloaded: {file_path}")
                    post_data["media_path"] = file_path

        except Exception as e:
            logger.error(f"Media yuklashda xatolik: {e}", exc_info=True)
            post_data["media_path"] = None


    # Ma'lumotlarni update qilamiz: id bo‘yicha eski postni yangilaymiz yoki yangi post qo‘shamiz
    updated = False
    for idx, x in enumerate(data):
        if x["id"] == post_data["id"]:
            data[idx] = post_data  # eski postni yangilaymiz
            updated = True
            logger.info(f"Inline post updated: {post_data['id']}")
            break
    if not updated:
        data.append(post_data)  # yangi post
        logger.info(f"Inline post added: {post_data['id']}")

    # Faylga yozamiz
    try:
        with open(INLINE_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"INLINE_JSON_PATH updated ({INLINE_JSON_PATH})")
    except Exception as e:
        logger.error(f"INLINE_JSON_PATH write error: {e}", exc_info=True)

def get_post_data_by_id(post_id):
    if os.path.exists(INLINE_JSON_PATH):
        try:
            with open(INLINE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for post in data:
                if post.get("id") == post_id:
                    return post
        except Exception as e:
            logger.error(f"get_post_data_by_id error: {e}", exc_info=True)
    return None


def cleanup_inline_posts_and_media():
    # Inline post JSON va media papkasini tozalaydi
    # JSON faylini tozalash
    if os.path.exists(INLINE_JSON_PATH):
        try:
            with open(INLINE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Medialarni o‘chirish
            for post in data:
                media_path = post.get("media_path")
                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                        logger.info(f"Cleanup: media file removed: {media_path}")
                    except Exception as e:
                        logger.error(f"Cleanup: could not remove media {media_path}: {e}", exc_info=True)
            # JSON faylni bo‘sh qilib yozish
            with open(INLINE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)
            logger.info("Cleanup: INLINE_JSON_PATH cleared")
        except Exception as e:
            logger.error(f"Cleanup error in JSON: {e}", exc_info=True)
    # Media papkasida eski media qolgan bo‘lsa (sug‘urib olingan), hammasini tozalash
    if os.path.exists(INLINE_MEDIA_FOLDER):
        for fname in os.listdir(INLINE_MEDIA_FOLDER):
            fpath = os.path.join(INLINE_MEDIA_FOLDER, fname)
            try:
                os.remove(fpath)
                logger.info(f"Cleanup: orphan media removed: {fpath}")
            except Exception as e:
                logger.error(f"Cleanup: could not remove orphan media {fpath}: {e}", exc_info=True)