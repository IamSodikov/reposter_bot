from telethon import TelegramClient
from telethon.errors.rpcerrorlist import UserNotParticipantError, ChannelPrivateError, UsernameNotOccupiedError
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest
from config import API_ID, API_HASH
from telethon_client.session_manager import get_session_file_path, with_session_lock
from bot.logger import logger

def parse_channel_input(channel):
    channel = channel.strip()
    if channel.startswith("t.me/"):
        parts = channel.split("/")
        if "c" in parts:
            channel_id = "-100" + parts[-2]
            return channel_id
        elif "+" in parts[-1]:
            return channel  # Private invite link
        else:
            return "@" + parts[-1]
    return channel

async def validate_channel(phone: str, channel: str) -> bool:
    channel = parse_channel_input(channel)
    async def check():
        async with TelegramClient(get_session_file_path(phone), API_ID, API_HASH) as client:
            try:
                entity = await client.get_entity(channel)
                await client(GetFullChannelRequest(entity))
                logger.info(f"validate_channel: {channel} valid for phone={phone}")
                return True
            except UsernameNotOccupiedError:
                logger.warning(f"validate_channel: {channel} not found for phone={phone}")
                return False
            except ChannelPrivateError:
                logger.warning(f"validate_channel: {channel} is private or not joined for phone={phone}")
                return False
            except Exception as e:
                logger.error(f"validate_channel error: {e}", exc_info=True)
                return False
    return await with_session_lock(phone, check)

async def is_user_member(phone: str, username: str) -> bool:
    username = parse_channel_input(username)
    async def check_member():
        async with TelegramClient(get_session_file_path(phone), API_ID, API_HASH) as client:
            try:
                await client.start()
                me = await client.get_me()
                await client(GetParticipantRequest(
                    channel=username,
                    participant=me.id
                ))
                logger.info(f"{phone} is member of {username}")
                return True
            except UserNotParticipantError:
                logger.info(f"{phone} is NOT member of {username}")
                return False
            except Exception as e:
                logger.error(f"is_user_member error (phone={phone}, username={username}): {e}", exc_info=True)
                return False
    return await with_session_lock(phone, check_member)
