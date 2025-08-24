import asyncio
from datetime import datetime, timedelta, timezone, time
from collections import defaultdict
from telethon_client.repost_utils import send_post_to_targets
from telethon_client.session_manager import get_client
from telethon_client.repost_utils import invite_link_to_chat_id
from telethon_client.channel_store import get_channels
from bot.logger import logger

async def scheduled_repost_by_days(
    user_id,
    source,
    targets,
    time_range,
    context=None,
):
    """
    Har kuni faqat bitta arxiv kun postlarini yig‘adi va real kunda, to‘g‘ri vaqt bilan targetlarga forward qiladi.
    Media group (albom), oddiy post, inline, sortirovka va bekor qilish nazorati bor!
    """
    user_data = get_channels(user_id)
    utc_offset = int(time_range.get("utc_offset", 0)) or int(user_data.get("time", {}).get("utc_offset", 0))
    offset_delta = timedelta(hours=utc_offset)

    client = await get_client(user_id)
    await client.start()

    source_id = await invite_link_to_chat_id(client, source)
    target_ids = [await invite_link_to_chat_id(client, t) for t in targets]

    # Sana oraliqlari
    start_date = datetime.strptime(time_range["start"], "%Y-%m-%d %H:%M").date()
    end_date = datetime.strptime(time_range["end"], "%Y-%m-%d %H:%M").date()

    logger.info(f"User({user_id}) optimized daily repost started: {source} → {targets}, {start_date}–{end_date}, UTC+{utc_offset}")

    today = datetime.now(timezone.utc).date()
    start_repost_date = today + timedelta(days=1)

    current_day = start_date
    idx = 0

    try:
        while current_day <= end_date:
            planned_date = start_repost_date + timedelta(days=idx)
            day_start = datetime.combine(current_day, time(0, 0), tzinfo=timezone.utc)
            day_end = datetime.combine(current_day, time(23, 59), tzinfo=timezone.utc)
            media_groups = defaultdict(list)
            single_msgs = []

            logger.info(f"User({user_id}) checking posts for {current_day}")

            # Faqat shu kun uchun postlarni Telegramdan so‘raymiz (offset_date=day_end, reverse=False)
            async for m in client.iter_messages(source_id, reverse=False, offset_date=day_end):
                if not hasattr(m, "id"): continue
                if getattr(m, "empty", False): continue
                if not (getattr(m, "text", None) or getattr(m, "message", None) or getattr(m, "raw_text", None) or getattr(m, "media", None)): continue

                msg_dt = m.date.astimezone(timezone.utc)
                logger.info(f"[DEBUG] id={m.id} | msg_dt={msg_dt.isoformat()} | day_start={day_start} | day_end={day_end}")

                if msg_dt < day_start:
                    break  # Endi shu kundan oldingi post - bu kun tugadi

                group_id = getattr(m, "grouped_id", None)
                if group_id:
                    media_groups[group_id].append(m)
                else:
                    single_msgs.append(m)

            # Yig‘ilgan postlarni to‘g‘ri ketma-ketlikda tuzamiz
            posts_to_send = []

            for group_msgs in media_groups.values():
                group_msgs = sorted(group_msgs, key=lambda m: m.id)
                first_msg = group_msgs[0]
                msg_time_utc = first_msg.date.replace(tzinfo=timezone.utc)
                posts_to_send.append({
                    "msg": first_msg,
                    "group_msgs": group_msgs,
                    "msg_time_utc": msg_time_utc,
                })

            for m in single_msgs:
                msg_time_utc = m.date.replace(tzinfo=timezone.utc)
                posts_to_send.append({
                    "msg": m,
                    "msg_time_utc": msg_time_utc,
                })

            posts_to_send = sorted(posts_to_send, key=lambda x: x["msg_time_utc"])

            if not posts_to_send:
                logger.info(f"User({user_id}) no posts found for {current_day}")
                current_day += timedelta(days=1)
                continue

            # --- HAR KUN BOSHI: POSTLAR RO‘YXATI YUBORILADI ---
            user_offset = timezone(offset_delta)
            planned_date_str = planned_date.strftime("%Y-%m-%d")
            post_list_text = [
                f"- ID: {post['msg'].id}  |  Время: {datetime.combine(planned_date, post['msg_time_utc'].time(), tzinfo=timezone.utc).astimezone(user_offset).strftime('%Y-%m-%d %H:%M')}"
                for post in posts_to_send
            ]
            txt = f"Список постов ({planned_date_str}, UTC{utc_offset:+}):\n" + "\n".join(post_list_text)
            if context and hasattr(context, "bot"):
                await context.bot.send_message(
                    chat_id=user_id,
                    text=txt
                )

            # --- HAR BIR POST YUBORILADI ---

            for post in posts_to_send:
                post_time = post["msg_time_utc"].time()
                target_datetime = datetime.combine(planned_date, post_time, tzinfo=timezone.utc) + offset_delta
                now_dt = datetime.now(timezone.utc) + offset_delta
                sleep_seconds = (target_datetime - now_dt).total_seconds()
                if sleep_seconds > 0:
                    logger.info(f"User({user_id}) sleeping {int(sleep_seconds)}s for post {post['msg'].id} at {target_datetime}")
                    await asyncio.sleep(sleep_seconds)

                # Uyg'ongan zahoti Telethon clientni jonlantiramiz
                try:
                    from telethon_client.repost_utils import _ensure_connected
                    await _ensure_connected(client)
                except Exception:
                    if not client.is_connected():
                        await client.connect()
                        try:
                            await client.start()
                        except Exception:
                            pass

                ok = await send_post_to_targets(client, target_ids, post, source_id)
                if ok:
                    logger.info(f"User({user_id}) post {post['msg'].id} sent to targets.")
                    if context and hasattr(context, "bot"):
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"Пост id {post['msg'].id} отправлено ✅"
                        )
                else:
                    logger.warning(f"User({user_id}) post {post['msg'].id} FAILED to send.")
                    if context and hasattr(context, "bot"):
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ Пост id {post['msg'].id} не отправлен. Попробую дальше."
                        )

                await asyncio.sleep(2)

            if context and hasattr(context, "bot"):
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ {planned_date_str} все посты отправлены!"
                )

            current_day += timedelta(days=1)
            idx += 1

        # Hammasi tugadi
        if context and hasattr(context, "bot"):
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Репосты за все дни завершены!"
            )

    except asyncio.CancelledError:
        logger.warning(f"User({user_id}) repost bekor qilindi.")
        if context and hasattr(context, "bot"):
            await context.bot.send_message(chat_id=user_id, text="⏹️ Репост отменён.")
        raise
    except Exception as e:
        logger.error(f"User({user_id}) repostda xatolik: {e}", exc_info=True)
        if context and hasattr(context, "bot"):
            await context.bot.send_message(chat_id=user_id, text="❌ Ошибка в репосте!")
    finally:
        await client.disconnect()
        if context and hasattr(context, "bot"):
            try:
                await context.bot.send_message(chat_id=user_id, text="✅ Репост завершён!")
            except Exception as e:
                logger.error(f"User({user_id}) notify error: {e}", exc_info=True)
