from telegram import Update
from telegram.ext import ContextTypes
from telethon_client.channel_store import get_channels
from telethon_client.repost_utils import test_forward_posts
from bot.logger import logger
import asyncio
from bot.handlers.repost_handler import user_tasks, is_repost_running  # user_tasks lug'atidan foydalanamiz


async def test_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_channels(user_id)
    source = user_data.get("source")
    targets = user_data.get("targets", [])

    if is_repost_running(user_id):
        await update.message.reply_text("♻️ Процесс репоста уже запущен. Вы можете остановить его и затем запустить новый.")
        return

    if not source or not targets:
        logger.warning(f"User({user_id}) tried test forward without source/targets: {user_data}")
        await update.message.reply_text("❗ Сначала выберите источник и целевые каналы!")
        return

    logger.info(f"User({user_id}) initiated test forward: source={source}, targets={targets}")
    await update.message.reply_text("⏳ Тест отправляется...")

    # Agar avvalgi vazifa mavjud boʻlsa, bekor qilamiz
    old_task = user_tasks.get(user_id)
    if old_task and not old_task.done():
        old_task.cancel()
        await asyncio.sleep(1)

    # TASK yaratib, user_tasks ga yozamiz
    task = context.application.create_task(
        test_forward_posts(user_id, source, targets)
    )
    user_tasks[user_id] = task  # Bu yerda yozish toʻgʻri amalga oshirilmoqda!

    try:
        posts_sent = await task
        if posts_sent == 0:
            logger.info(f"User({user_id}) test forward: no suitable posts found")
            await update.message.reply_text("❗ Среди последних 5 постов нет подходящих для пересылки.")
        else:
            logger.info(f"User({user_id}) test forward: {posts_sent} posts sent")
            await update.message.reply_text(f"✅ {posts_sent} пост(ов) отправлено в целевые каналы.")
        await update.message.reply_text("✅ Тестовая пересылка завершена!")
    except asyncio.CancelledError:
        logger.warning(f"User({user_id}) test forward CANCELLED by user!")
        await update.message.reply_text("⏹️ Тестовая пересылка остановлена пользователем.")
    except Exception as e:
        logger.error(f"User({user_id}) test forward error: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при тестовой отправке постов!")
    finally:
        user_tasks.pop(user_id, None)
