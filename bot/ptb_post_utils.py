import os
import json
from telegram import Bot, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.constants import ParseMode
from config import BOT_TOKEN, INLINE_JSON_PATH
from bot.logger import logger

def parse_reply_markup(reply_markup):
    """
    Har qanday Telethon yoki .to_dict() dan kelgan reply_markupni PTB uchun standartga o'tkazadi.
    """
    try:
        if isinstance(reply_markup, dict):
            if "inline_keyboard" in reply_markup:
                return InlineKeyboardMarkup(reply_markup["inline_keyboard"])
            if "_" in reply_markup and reply_markup["_"] == "ReplyInlineMarkup" and "rows" in reply_markup:
                keyboard = []
                for row in reply_markup["rows"]:
                    buttons = []
                    for btn in row.get("buttons", []):
                        btn = btn.get("button", btn)
                        btn_type = btn.get("_")
                        if btn_type == "KeyboardButtonUrl":
                            buttons.append({
                                "text": btn.get("text"),
                                "url": btn.get("url")
                            })
                        elif btn_type == "KeyboardButtonCallback":
                            buttons.append({
                                "text": btn.get("text"),
                                "callback_data": btn.get("data", "cb")
                            })
                        elif btn_type == "KeyboardButtonSwitchInline":
                            buttons.append({
                                "text": btn.get("text"),
                                "switch_inline_query": btn.get("query", "")
                            })
                    keyboard.append(buttons)
                return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        logger.error(f"parse_reply_markup error: {e}", exc_info=True)
    return None



async def ptb_send_and_cleanup(post_data, target_channel):
    text = post_data.get("text") or ""
    reply_markup = post_data.get("reply_markup")
    media_path = post_data.get("media_path")
    is_round_video = post_data.get("is_round_video", False)  # ✅ Dumaloq video flag
    keyboard = parse_reply_markup(reply_markup)

    try:
        if media_path and os.path.exists(media_path):
            # 📏 Dinamik timeoutlarni alohida hisoblaymiz
            file_size = os.path.getsize(media_path)
            size_in_mb = file_size / (1024 * 1024)
            write_timeout = min(300, max(10, int(size_in_mb * 2)))  # Yuborish vaqti
            read_timeout = max(60, write_timeout * 2)               # Javob kutish vaqti

            request = HTTPXRequest(
                connect_timeout=10.0,
                read_timeout=read_timeout,
                write_timeout=write_timeout
            )
            bot = Bot(token=BOT_TOKEN, request=request)


            with open(media_path, "rb") as file:
                if is_round_video:
                    await bot.send_video_note(
                        chat_id=target_channel,
                        video_note=file,
                        reply_markup=keyboard
                    )
                elif media_path.endswith((".jpg", ".jpeg", ".png")):
                    await bot.send_photo(
                        chat_id=target_channel,
                        photo=file,
                        caption=text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                elif media_path.endswith(".mp4"):
                    await bot.send_video(
                        chat_id=target_channel,
                        video=file,
                        caption=text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML,
                        supports_streaming=True  # ✅ original formatni saqlashga yordam beradi
                    )
                else:
                    await bot.send_document(
                        chat_id=target_channel,
                        document=file,
                        caption=text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
            logger.info(f"Media sent and file will be removed: {media_path}")
            os.remove(media_path)

        else:
            bot = Bot(token=BOT_TOKEN)  # text-only uchun default bot
            if text.strip():
                await bot.send_message(
                    chat_id=target_channel,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Text sent to {target_channel}")
            else:
                logger.warning(f"Text bo‘sh: post {post_data.get('id')} yuborilmadi")

        # JSONdan postni o‘chiramiz
        if os.path.exists(INLINE_JSON_PATH):
            with open(INLINE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            target_id = str(post_data["id"])
            data = [x for x in data if str(x.get("id")) != target_id]
            with open(INLINE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Post {target_id} removed from {INLINE_JSON_PATH}")

    except Exception as e:
        logger.error(f"ptb_send_and_cleanup error (target={target_channel}): {e}", exc_info=True)

