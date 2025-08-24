from telegram import Update
from telegram.ext import ContextTypes
from telethon_client.channel_store import get_channels
from telethon_client.repost_utils_inline import cleanup_inline_posts_and_media
from bot.logger import logger
from telethon_client.scheduling import scheduled_repost_by_days  # <-- YANGI IMPORT!
import asyncio

user_tasks = {}

def is_repost_running(user_id):
    task = user_tasks.get(user_id)
    return task is not None and not task.done()


async def start_repost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_channels(user_id)

    source = user_data.get("source")
    targets = user_data.get("targets", [])
    time = user_data.get("time")

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return


    if not source or not targets or not time or not time.get("start") or not time.get("end"):
        logger.warning(f"User({user_id}) tried to start repost without all parameters: {user_data}")
        await update.message.reply_text("❌ Для начала репоста выберите канал, цель и время!")
        return

    await update.message.reply_text("♻️ Процесс репоста начался...")
    logger.info(f"User({user_id}) started repost: source={source}, targets={targets}, time={time}")

    # Agar eski task mavjud bo'lsa, bekor qilamiz
    old_task = user_tasks.get(user_id)
    if old_task and not old_task.done():
        logger.info(f"User({user_id}) cancelling old repost task...")
        old_task.cancel()
        await asyncio.sleep(1)  # eski vazifa to'xtashi uchun vaqt berish

    try:
        # YANGI: scheduling.py dan funksiya chaqiramiz!
        repost_task = context.application.create_task(
            scheduled_repost_by_days(user_id, source, targets, time, context)
        )
        user_tasks[user_id] = repost_task
        logger.info(f"User({user_id}) repost task started")
    except Exception as e:
        logger.error(f"User({user_id}) failed to start repost: {e}", exc_info=True)
        await update.message.reply_text("❌ Процесс репоста не запущен из-за ошибки!")

async def stop_repost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task = user_tasks.get(user_id)

    if task and not task.done():
        task.cancel()
        await update.message.reply_text("⏹️ Репост/тестовая пересылка остановлена.")
        logger.info(f"User({user_id}) repost/test forward stopped by user.")
    else:
        await update.message.reply_text("❗ Сейчас репост или тестовая пересылка не запущены или уже остановлены.")
