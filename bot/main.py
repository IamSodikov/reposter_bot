from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler,
    filters, CommandHandler
)
from telegram import BotCommand
from bot.handlers.time_handlers import get_time_conversation_handler, time_callback_handler
from bot.handlers.session import get_session_conversation_handler, start_command, logout_command
from bot.handlers.channel import channels_handler, callback_handler, channel_username_handler
from bot.handlers.repost_handler import start_repost, stop_repost
from bot.handlers.test_handler import test_forward
from bot.keyboards.menu import menu_commands_keyboard  # Agar kerak bo‘lsa
from config import BOT_TOKEN
from bot.logger import logger

# --- YANGI: Bot komandalar menyusini (ko‘k Menu) o‘rnatish funksiyasi ---
async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Главное меню / Запуск"),
        BotCommand("logout", "Выйти из бота / Удалить все данные"),
        # Yana komanda qo‘shmoqchi bo‘lsangiz, shu yerga:
        # BotCommand("settings", "Настройки / Sozlamalar"),
    ])

# --- Pastki oq menyu (ReplyKeyboard) uchun handler, lekin bu majburiy emas ---
async def show_menu_commands(update, context):
    await update.message.reply_text(
        "Команды:\n/start — Главное меню\n/logout — Выйти из бота",
        reply_markup=menu_commands_keyboard()
    )

def main():
    logger.info("Bot application is starting...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- Eng muhim: Bot komandalar menyusini o‘rnatamiz (PTB 20+ uchun) ---
    async def post_init(application):
        await set_bot_commands(application)
    app.post_init = post_init

    # Agar pastki oq "Menu" ham bo‘lishini istasangiz (kerak bo‘lmasa, bu ikki qatorni o‘chirib yuboring)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(Menu)$"), show_menu_commands))

    # Asosiy handlerlar (eski holatda)
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(get_session_conversation_handler())
    app.add_handler(get_time_conversation_handler())
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(📢 Каналы)$"), channels_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(♻️ Начать репост)$"), start_repost))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(⏹ Остановить)$"), stop_repost))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🧪 Тест$"), test_forward))
    app.add_handler(CallbackQueryHandler(time_callback_handler, pattern="^(delete_time)$"))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
    channel_username_handler
))

    logger.info("All handlers are added. Bot is polling now...")

    try:
        app.run_polling()
    except Exception as e:
        logger.critical(f"Bot crashed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
