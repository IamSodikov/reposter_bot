# bot/handlers/channel.py

from inspect import getsource
from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards.menu import kanallar_inline_menu
from telethon_client.channel_utils import validate_channel, is_user_member
from telethon_client.user_map import get_phone_by_user
from telethon_client.channel_store import get_channels, add_channel, remove_channel, toggle_source, toggle_target
from telethon_client.session_manager import get_client
from bot.logger import logger
from bot.handlers.repost_handler import is_repost_running

async def channels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = get_phone_by_user(user_id)

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return
    
    if not phone:
        logger.warning(f"User({user_id}) tried /channels without registration")
        await update.message.reply_text("❌ Сначала пройдите регистрацию.")
        return

    channels = get_channels(user_id)
    keyboard = kanallar_inline_menu(channels)
    logger.info(f"User({user_id}) opened channels menu")
    await update.message.reply_text("📢 Список каналов:", reply_markup=keyboard)

async def channel_username_handler(update, context):
    # Faqat private chat dan kelgan xabarlar bilan ishlaymiz
    if not update.message or update.message.chat.type != "private":
        logger.warning(f"[channel_username_handler] Kanal post yoki no-private chatdan kelgan: {update}")
        return

    user_data = getattr(context, "user_data", None)
    user_id = update.effective_user.id

    # ♻️ Repost jarayoni bo‘layotgan bo‘lsa — bloklaymiz
    if is_repost_running(user_id):
        await update.message.reply_text(
            "♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый."
        )
        return

    # Kanal qo‘shish rejimida bo‘lmasa — hech narsa qilmaymiz
    if not user_data or not user_data.get("adding_channel"):
        return

    username = update.message.text.strip()
    phone = get_phone_by_user(user_id)
    logger.info(f"User({user_id}) attempts to add channel: {username}, phone: {phone}")

    if not phone:
        logger.warning(f"User({user_id}) session not found for adding channel")
        await update.message.reply_text("❌ Сессия не найдена.")
        return

    # Kanal mavjudligini tekshiramiz
    try:
        is_valid = await validate_channel(phone, username)
    except Exception as e:
        logger.error(f"User({user_id}) validate_channel error: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка проверки канала!")
        context.user_data["adding_channel"] = False
        return

    if not is_valid:
        logger.info(f"User({user_id}) tried to add invalid/closed channel: {username}")
        await update.message.reply_text("❌ Канал не найден или он закрыт.")
        context.user_data["adding_channel"] = False
        return

    # A'zolikni tekshiramiz
    try:
        is_member = await is_user_member(phone, username)
    except Exception as e:
        logger.error(f"User({user_id}) is_user_member error: {e}", exc_info=True)
        is_member = False

    if not is_member:
        await update.message.reply_text("❗ Сначала подпишитесь на канал этим аккаунтом!")
        context.user_data["adding_channel"] = False
        return

    # ✅ Kanalni ro‘yxatga qo‘shamiz
    add_channel(user_id, username)
    channels = get_channels(user_id)
    keyboard = kanallar_inline_menu(channels)

    await update.message.reply_text(
        f"✅ Канал успешно добавлен!\n\n📢 Ваш список каналов:",
        reply_markup=keyboard
    )

    context.user_data["adding_channel"] = False


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    phone = get_phone_by_user(user_id)
    data = query.data

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return
    
    logger.info(f"User({user_id}) callback: {data}")

    try:
        if data == "add_channel":
            await query.message.reply_text("🆕 Введите username канала (например: @yourchannel):")
            if hasattr(context, "user_data") and context.user_data is not None:
                context.user_data["adding_channel"] = True
            return

        if data == "ignore":
            await query.message.delete()
            logger.info(f"User({user_id}) ignored message")
            return

        if data.startswith("delete:"):
            username = data.split(":", 1)[1]
            remove_channel(user_id, username)
            user_data = get_channels(user_id)
            keyboard = kanallar_inline_menu(user_data)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            logger.info(f"User({user_id}) deleted channel: {username}")
            return

        if data.startswith("source:"):
            username = data.split(":", 1)[1]
            toggle_source(user_id, username)
            user_data = get_channels(user_id)
            keyboard = kanallar_inline_menu(user_data)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            logger.info(f"User({user_id}) toggled source: {username}")
            return

        if data.startswith("target:"):
            username = data.split(":", 1)[1]
            toggle_target(user_id, username)
            user_data = get_channels(user_id)
            keyboard = kanallar_inline_menu(user_data)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            logger.info(f"User({user_id}) toggled target: {username}")
            return

        elif data.startswith("set_source_"):
            username = data.split("set_source_")[1]
            getsource(user_id, username)
            await query.answer("✅ Источник выбран")
            await query.edit_message_text("♻️ Источник выбран. Тестовые посты отправляются...")

            channels_data = get_channels(user_id)
            targets = channels_data.get("targets", [])

            if not targets:
                logger.warning(f"User({user_id}) tried to send test posts without targets")
                await query.edit_message_text("⚠️ Целевые каналы не выбраны!")
                return

            client = await get_client(user_id)
            async with client:
                async for message in client.iter_messages(username, limit=5, reverse=True):
                    for target in targets:
                        try:
                            await client.forward_messages(target, message.id, from_peer=username)
                        except Exception as e:
                            logger.error(f"User({user_id}) test forward error → {target}: {e}", exc_info=True)

            await query.edit_message_text("✅ Тестовые посты были отправлены в целевые каналы.")
    except Exception as e:
        logger.error(f"User({user_id}) callback_handler error: {e}", exc_info=True)
        await query.message.reply_text("❌ Внутренняя ошибка в обработке действия!")

