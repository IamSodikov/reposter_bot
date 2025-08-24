from telegram import Update
from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, ContextTypes, filters, CallbackQueryHandler
from bot.handlers.session import start_command
from telethon_client.channel_store import set_time, get_channels
from datetime import datetime
from bot.keyboards.menu import vaqt_sozlangan_tugmalar
from bot.logger import logger
from bot.keyboards.menu import main_menu
from bot.handlers.repost_handler import is_repost_running

AWAIT_START_TIME, AWAIT_END_TIME, AWAIT_UTC_OFFSET = range(3)

async def start_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_channels(user_id)

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return

    has_time = (
        "time" in user_data and
        user_data["time"].get("start") and
        user_data["time"].get("end")
    )

    if has_time:
        start = user_data["time"]["start"][:10]
        end = user_data["time"]["end"][:10]
        logger.info(f"User({user_id}) already has time set: {start} - {end}")

        await update.message.reply_text(
            f"📅 Установленный период:\nНачало: {start}\nКонец: {end}"
        )
        # Inline keyboard: vaqt o‘chirish uchun
        await update.message.reply_text(
            "Для удаления периода нажмите кнопку ниже 👇",
            reply_markup=vaqt_sozlangan_tugmalar()
        )
        return ConversationHandler.END

    logger.info(f"User({user_id}) started to input time period")
    await update.message.reply_text(
        "🗓 Введите дату начала (ГГГГ-ММ-ДД):"
    )
    return AWAIT_START_TIME


async def receive_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_date = update.message.text.strip()
    user_id = update.effective_user.id

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return
    
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"User({user_id}) entered invalid start date: {start_date}")
        await update.message.reply_text("❌ Неверный формат. Пожалуйста, введите в формате ГГГГ-ММ-ДД.")
        return AWAIT_START_TIME

    context.user_data["start_time"] = start_date
    logger.info(f"User({user_id}) set start date: {start_date}")
    await update.message.reply_text("⏳ Введите дату окончания (ГГГГ-ММ-ДД):")
    return AWAIT_END_TIME

async def receive_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    end_date = update.message.text.strip()

    start_date = context.user_data["start_time"]

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return
    
    try:
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"User({user_id}) entered invalid end date: {end_date}")
        await update.message.reply_text("❌ Неверный формат. Пожалуйста, введите в формате ГГГГ-ММ-ДД.")
        return AWAIT_END_TIME

    # Vaqtlar kontekstda saqlanadi
    context.user_data["end_time"] = end_date
    await update.message.reply_text("⏰ Пожалуйста, введите Ваш часовой пояс (UTC offset, например: +5 или -3):")
    return AWAIT_UTC_OFFSET

async def receive_utc_offset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    utc_offset_str = update.message.text.strip()

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return

    try:
        # Faqat +5, -3, 0 kabi formatlar qabul qilamiz
        if utc_offset_str.startswith('+'):
            offset = int(utc_offset_str)
        elif utc_offset_str.startswith('-'):
            offset = int(utc_offset_str)
        else:
            offset = int(utc_offset_str)
    except Exception:
        await update.message.reply_text("❌ Формат неверный. Например: +5 или -3")
        return AWAIT_UTC_OFFSET

    # Endi barcha vaqtlarni bazaga saqlaymiz
    start_time = f"{context.user_data['start_time']} 00:00"
    end_time = f"{context.user_data['end_time']} 23:59"
    utc_offset = offset

    try:
        set_time(user_id, start_time, end_time, utc_offset)
        logger.info(f"User({user_id}) set time: {start_time} - {end_time}, UTC offset: {utc_offset}")
    except Exception as e:
        logger.error(f"User({user_id}) set_time error: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка сохранения периода времени.")
        return ConversationHandler.END

    await update.message.reply_text("✅ Период и часовой пояс успешно сохранены!", reply_markup=main_menu())
    return ConversationHandler.END

async def cancel_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return
    
    logger.info(f"User({user_id}) cancelled time setup")
    await update.message.reply_text("❌ Отменено.", reply_markup=main_menu())
    return ConversationHandler.END


def get_time_conversation_handler():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex("^(⏰ Настроить время)$"), start_time_input),
            CallbackQueryHandler(time_callback_handler, pattern="^delete_time$")
        ],
        states={
            AWAIT_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_time)],
            AWAIT_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_end_time)],
            AWAIT_UTC_OFFSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_utc_offset)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_time),
            CommandHandler("start", start_command),
        ],
    )


async def time_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "delete_time":
        logger.info(f"User({user_id}) deleted time period")
        try:
            set_time(user_id, None, None)
            await query.edit_message_text(
                "🗑 Время удалено.\n\n🕒 Введите дату начала (ГГГГ-ММ-ДД):"
            )
        except Exception as e:
            logger.error(f"User({user_id}) error deleting time: {e}", exc_info=True)
            await query.edit_message_text("❌ Ошибка при удалении времени.")
        return AWAIT_START_TIME
