# repost_utils.py

import asyncio
from telethon.errors import ConnectionError as TLConnectionError
from telethon_client.repost_utils_inline import save_inline_keyboard_post, get_post_data_by_id
from telethon_client.session_manager import get_client
from bot.ptb_post_utils import ptb_send_and_cleanup
from telethon.tl.types import MessageService
from bot.logger import logger

def is_forwardable(msg):
    if isinstance(msg, MessageService):
        return False
    if getattr(msg, "empty", False):
        return False
    if not (msg.text or msg.message or msg.raw_text or msg.media):
        return False
    if not getattr(msg, "id", None):
        return False
    return True

async def _ensure_connected(client):
    """Telethon client ulanishini tekshirib, kerak bo'lsa qayta ulaydi."""
    if not client.is_connected():
        await client.connect()
    try:
        # Sessiyani “uyg'otish” uchun engil chaqiriq
        await client.get_me()
    except Exception:
        # Agar sign-in holati buzilgan bo'lsa
        await client.start()

async def _with_reconnect(fn, retries=2, delay=2):
    """Telethon chaqirig'ini bir necha marta retry qiladi (disconnect holati uchun)."""
    last_err = None
    for _ in range(retries + 1):
        try:
            return await fn()
        except (TLConnectionError, ConnectionError) as e:
            last_err = e
            logger.warning(f"[RETRY] reconnect after error: {e}")
            await asyncio.sleep(delay)
    raise last_err

async def invite_link_to_chat_id(client, link: str):
    if "t.me/+" in link or link.startswith("https://t.me/+") or link.startswith("t.me/+"):
        entity = await client.get_entity(link)
        if hasattr(entity, 'username') and entity.username:
            return '@' + entity.username
        return int('-100' + str(entity.id))
    if "t.me/" in link:
        username = link.split("/")[-1]
        if username.startswith("+"):
            entity = await client.get_entity(link)
            if hasattr(entity, 'username') and entity.username:
                return '@' + entity.username
            return int('-100' + str(entity.id))
        if username.startswith("@"):
            return username
        return "@" + username
    if link.startswith("@"):
        return link
    if link.startswith("-100") and link[1:].isdigit():
        return int(link)
    if link.isdigit():
        return int(link)
    return link


async def send_media_group(client, target_chat, messages, source_chat):
    if not messages:
        logger.warning(f"[MEDIA GROUP] No messages to send to {target_chat}")
        return
    try:
        await _ensure_connected(client)
        messages = sorted(messages, key=lambda m: m.id)
        logger.info(f"[MEDIA GROUP] Sending to {target_chat} → {[m.id for m in messages]}")
        for m in messages:
            logger.info(f"[MEDIA GROUP MSG] id={m.id} | date={m.date.isoformat()} | text={getattr(m, 'message', '')[:30]}")
        await _with_reconnect(lambda: client.forward_messages(
            entity=target_chat,
            messages=[m.id for m in messages],
            from_peer=source_chat,
            drop_author=True
        ))
        logger.info(f"[MEDIA GROUP] ✅ Forwarded to {target_chat}")
    except Exception as e:
        logger.error(f"send_media_group error (target={target_chat}): {e}", exc_info=True)
        raise  # muvofaqqiyatsizlikni yuqoriga ko'taramiz

async def send_post_to_targets(client, target_ids, post, source_id):
    msg = post.get("msg")
    group_msgs = post.get("group_msgs", None)

    try:
        await _ensure_connected(client)

        if group_msgs:
            logger.info(f"[SEND POST] Media group: msg_ids={[m.id for m in group_msgs]} → targets={target_ids}")
            for target_id in target_ids:
                await _ensure_connected(client)
                await send_media_group(client, target_id, group_msgs, source_id)

        elif getattr(msg, "reply_markup", None):
            logger.info(f"[SEND POST] Inline msg_id={msg.id} → targets={target_ids}")
            await save_inline_keyboard_post(msg, client)
            post_data = get_post_data_by_id(msg.id)
            if post_data:
                for target_id in target_ids:
                    await ptb_send_and_cleanup(post_data, target_id)

        else:
            logger.info(f"[SEND POST] Single msg_id={msg.id} | date={msg.date.isoformat()} → targets={target_ids}")
            for target_id in target_ids:
                await _ensure_connected(client)
                await _with_reconnect(lambda: client.forward_messages(
                    entity=target_id,
                    messages=msg.id,
                    from_peer=source_id,
                    drop_author=True
                ))

        return True
    except Exception as e:
        logger.error(f"send_post_to_targets error: {e}", exc_info=True)
        return False

async def test_forward_posts(user_id: int, source: str, targets: list[str]):
    client = await get_client(user_id)
    await client.start()
    posts_sent = 0
    try:
        source_id = await invite_link_to_chat_id(client, source)
        target_ids = [await invite_link_to_chat_id(client, t) for t in targets]

        logger.info(f"[TEST INIT] source_id={source_id}, targets={target_ids}")

        grouped_map = {}
        seen_group_ids = set()
        selected_items = []

        async for message in client.iter_messages(source_id, limit=100):
            if getattr(message, "reply_markup", None):
                selected_items.append(("inline", message))
            elif message.grouped_id:
                gid = message.grouped_id
                grouped_map.setdefault(gid, []).append(message)
                if gid not in seen_group_ids:
                    seen_group_ids.add(gid)
                    selected_items.append(("media", gid))
            elif is_forwardable(message):
                selected_items.append(("single", message))
            
            logger.info(f"[TEST SELECT] msg_id={message.id} | date={message.date.isoformat()} | type={'group' if message.grouped_id else 'single'}")

            if len(selected_items) >= 5:
                break

        for item_type, data in selected_items:
            if posts_sent >= 5:
                break

            for target_id in target_ids:
                try:

                    if item_type == "inline":
                        logger.info(f"[TEST SEND] inline msg_id={data.id} → targets={target_ids}")
                    elif item_type == "media":
                        group_messages = grouped_map.get(data, [])
                        logger.info(f"[TEST SEND] media group → targets={target_ids} | group_ids={[m.id for m in group_messages]}")
                    elif item_type == "single":
                        logger.info(f"[TEST SEND] single msg_id={data.id} | date={data.date.isoformat()} → targets={target_ids}")

                    if item_type == "inline":
                        await save_inline_keyboard_post(data, client)
                        post_data = get_post_data_by_id(data.id)
                        if post_data:
                            await ptb_send_and_cleanup(post_data, target_id)
                    elif item_type == "media":
                        group_messages = grouped_map.get(data, [])
                        if group_messages:
                            await client.forward_messages(
                                entity=target_id,
                                messages=[m.id for m in sorted(group_messages, key=lambda x: x.id)],
                                from_peer=source_id,
                                drop_author=True
                            )
                    elif item_type == "single":
                        await client.forward_messages(
                            entity=target_id,
                            messages=data.id,
                            from_peer=source_id,
                            drop_author=True
                        )
                    posts_sent += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"test_forward post error ({item_type}, target={target_id}): {e}", exc_info=True)

    except Exception as e:
        logger.error(f"User({user_id}) test_forward_posts fatal error: {e}", exc_info=True)
    finally:
        await client.disconnect()
        logger.info(f"User({user_id}) test_forward_posts finished/disconnected")
    return posts_sent
