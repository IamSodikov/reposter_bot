# bot/keyboards/menu.py

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from bot.logger import logger

def main_menu():
    # Asosiy menu
    return ReplyKeyboardMarkup(
        [
            ["📢 Каналы", "⏰ Настроить время"],
            ["♻️ Начать репост", "⏹ Остановить"],
            ["🧪 Тест"]
        ],
        resize_keyboard=True
    )

def kanallar_inline_menu(user_data: dict):
    channels = user_data.get("channels", [])
    source = user_data.get("source")
    targets = user_data.get("targets", [])

    buttons = []
    for ch in channels:
        try:
            channel_url = f"https://t.me/{ch.lstrip('@')}"
            buttons.append([InlineKeyboardButton(text=f"📣 {ch}", url=channel_url)])

            source_text = "📥 Источник ✅" if ch == source else "📥 Источник"
            target_text = "🎯 Цель ✅" if ch in targets else "🎯 Цель"

            buttons.append([
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{ch}"),
                InlineKeyboardButton(text=source_text, callback_data=f"source:{ch}"),
                InlineKeyboardButton(text=target_text, callback_data=f"target:{ch}")
            ])
        except Exception as e:
            logger.error(f"Error generating inline menu for channel {ch}: {e}", exc_info=True)

    buttons.append([InlineKeyboardButton(text="➕ Новый канал", callback_data="add_channel")])
    return InlineKeyboardMarkup(buttons)

def obuna_tugmalari(username: str, is_member: bool):
    url = f"https://t.me/{username.strip('@')}"
    try:
        if is_member:
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(text=f"🔗 {username}", url=url),
                    InlineKeyboardButton(text="❌ Выйти", callback_data=f"leave:{username}")
                ]
            ])
        else:
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(text=f"🔗 {username}", url=url),
                    InlineKeyboardButton(text="✅ Подписаться", callback_data=f"join:{username}")
                ]
            ])
    except Exception as e:
        logger.error(f"Error generating obuna_tugmalari for {username}: {e}", exc_info=True)
        # Fallback
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text=f"🔗 {username}", url=url)]
        ])

def vaqt_sozlangan_tugmalar():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Удалить время", callback_data="delete_time")]
    ])

def menu_commands_keyboard():
    return ReplyKeyboardMarkup(
        [["/start", "/logout"]], resize_keyboard=True, one_time_keyboard=True
    )