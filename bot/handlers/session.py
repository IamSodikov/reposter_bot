import asyncio
import os
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from telethon_client import session_manager
from telethon_client.user_map import link_user_to_phone, get_phone_by_user
from bot.keyboards.menu import main_menu
from telethon_client.channel_store import remove_user

ASK_PHONE, ASK_CODE, ASK_2FA = range(3)
user_temp_phone = {}
user_temp_code_hash = {}
user_temp_client = {}
user_pending_cleanup = {}

SESSION_EXPIRE_SECONDS = 120

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = get_phone_by_user(user_id)
    if phone and session_manager.session_exists(phone):
        await update.message.reply_text(
            "✅ Вы уже зарегистрированы.\nГлавное меню.",
            reply_markup=main_menu()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📞 Введите свой номер телефона (например: +998901234567):",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_id = update.effective_user.id
    user_temp_phone[user_id] = phone

    try:
        client, phone_code_hash = await session_manager.start_login(phone)
        user_temp_client[user_id] = client
        user_temp_code_hash[user_id] = phone_code_hash

        await update.message.reply_text(
            "✉️ Код отправлен. ⏳ Ожидание кода подтверждения...\n"
            "Если не пришёл код, используйте /logout для отмены.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Cleanup timer
        async def cleanup():
            await asyncio.sleep(SESSION_EXPIRE_SECONDS)
            session_file = session_manager.get_session_file_path(phone) + ".session"
            if os.path.exists(session_file):
                os.remove(session_file)
                print(f"[CLEANUP] Session for {phone} deleted after timeout.")
        # Clean pending
        if user_id in user_pending_cleanup:
            user_pending_cleanup[user_id].cancel()
        user_pending_cleanup[user_id] = asyncio.create_task(cleanup())
        return ASK_CODE
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    phone = user_temp_phone.get(user_id)
    client = user_temp_client.get(user_id)
    phone_code_hash = user_temp_code_hash.get(user_id)

    # Stop pending cleanup
    if user_id in user_pending_cleanup:
        user_pending_cleanup[user_id].cancel()
        del user_pending_cleanup[user_id]

    if not client or not phone or not phone_code_hash:
        await update.message.reply_text(
            "❗ Внутренняя ошибка: отсутствует сессия авторизации. Пожалуйста, введите номер заново.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    try:
        await session_manager.complete_login(client, phone, code, phone_code_hash)
        link_user_to_phone(user_id, phone)
        # Clean temp
        user_temp_client.pop(user_id, None)
        user_temp_code_hash.pop(user_id, None)
        user_temp_phone.pop(user_id, None)
        await update.message.reply_text(
            "✅ Вход успешно выполнен!",
            reply_markup=main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        # 2FA (cloud password) kerak bo'lsa
        if "2FA" in str(e) or "облачный пароль" in str(e):
            await update.message.reply_text(
                "🔑 Для вашего аккаунта включен облачный пароль (2FA).\nПожалуйста, введите свой пароль:",
                reply_markup=ReplyKeyboardRemove()
            )
            return ASK_2FA
        # Xatolik bo'lsa
        await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=ReplyKeyboardRemove())
        session_file = session_manager.get_session_file_path(phone) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
        # Clean temp
        user_temp_client.pop(user_id, None)
        user_temp_code_hash.pop(user_id, None)
        user_temp_phone.pop(user_id, None)
        return ConversationHandler.END

async def ask_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = update.effective_user.id
    phone = user_temp_phone.get(user_id)
    client = user_temp_client.get(user_id)
    phone_code_hash = user_temp_code_hash.get(user_id)
    code = None  # Odatda kodni ham saqlash kerak bo‘ladi

    if not client or not phone or not phone_code_hash:
        await update.message.reply_text(
            "❗ Внутренняя ошибка: отсутствует сессия авторизации. Пожалуйста, введите номер заново.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    try:
        # Faqat password bilan qayta login qilish
        await session_manager.complete_login(client, phone, None, phone_code_hash, password=password)
        link_user_to_phone(user_id, phone)
        # Clean temp
        user_temp_client.pop(user_id, None)
        user_temp_code_hash.pop(user_id, None)
        user_temp_phone.pop(user_id, None)
        await update.message.reply_text(
            "✅ Вход успешно выполнен! (2FA)",
            reply_markup=main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка 2FA: {str(e)}", reply_markup=ReplyKeyboardRemove())
        session_file = session_manager.get_session_file_path(phone) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
        # Clean temp
        user_temp_client.pop(user_id, None)
        user_temp_code_hash.pop(user_id, None)
        user_temp_phone.pop(user_id, None)
        return ConversationHandler.END

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Stop pending cleanup
    if user_id in user_pending_cleanup:
        user_pending_cleanup[user_id].cancel()
        del user_pending_cleanup[user_id]

    phone = user_temp_phone.get(user_id) or get_phone_by_user(user_id)
    if phone:
        session_file = session_manager.get_session_file_path(phone) + ".session"
        if os.path.exists(session_file):
            os.remove(session_file)
    remove_user(user_id)
    await update.message.reply_text(
        "❌ Вы вышли из бота. Все ваши данные удалены.\n\nЧтобы начать заново, нажмите /start",
        reply_markup=ReplyKeyboardRemove()
    )

def get_session_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code)],
            ASK_2FA:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_2fa)],
        },
        fallbacks=[
            CommandHandler("logout", logout_command),
            CommandHandler("start", start_command),
        ],
    )
