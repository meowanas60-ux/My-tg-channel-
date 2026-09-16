
import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

STORAGE_CHANNEL_ID = int(
    os.environ.get("STORAGE_CHANNEL_ID", "-1003564232245")
)

OWNER_ID = int(
    os.environ.get("OWNER_ID", "7701549179")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("download_bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# /start — DOWNLOAD HANDLER
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    if not message.text:
        return

    args = message.text.split(maxsplit=1)

    # Normal /start
    if len(args) == 1:
        await message.answer(
            "👋 Welcome to Anas APK Bot!\n\n"
            "📱 Get APK files from our channel.\n\n"
            "📢 Our Channels:\n"
            "• @sahatanas\n"
            "• @sahatanass\n\n"
            "⬇️ Click Download APK from a channel post "
            "to receive the file here!"
        )
        return

    payload = args[1].strip()

    # Only accept /start dl_123
    if not payload.startswith("dl_"):
        await message.answer(
            "❌ Invalid download link.\n"
            "Please use the Download APK button from our channel."
        )
        return

    try:
        storage_msg_id = int(payload[3:])

        if storage_msg_id <= 0:
            raise ValueError

    except (ValueError, TypeError):
        logger.warning(
            "Invalid download payload | payload=%r | user_id=%s",
            payload,
            message.from_user.id if message.from_user else "unknown"
        )
        await message.answer("❌ Invalid download link.")
        return

    user_id = message.from_user.id if message.from_user else None

    logger.info(
        "Download request received | user_id=%s | username=%s | "
        "storage_msg_id=%s",
        user_id,
        message.from_user.username if message.from_user else None,
        storage_msg_id
    )

    loading = await message.answer(
        "⏳ Please wait...\n"
        "📦 Fetching your APK file..."
    )

    try:
        # Copy the original APK/document from storage channel
        copied_message = await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=storage_msg_id
        )

        logger.info(
            "APK delivered successfully | user_id=%s | "
            "storage_msg_id=%s | copied_message_id=%s",
            user_id,
            storage_msg_id,
            copied_message.message_id
        )

        await loading.delete()

        await message.answer(
            "✅ Download ready! Your APK file is above.\n\n"
            "📢 Main Channel: @sahatanas\n"
            "💾 Backup Channel: @sahatanass"
        )

    except TelegramAPIError as e:
        logger.exception(
            "Telegram API error during delivery | user_id=%s | "
            "storage_msg_id=%s | error=%s",
            user_id,
            storage_msg_id,
            e
        )

        await loading.edit_text(
            "❌ Download failed.\n\n"
            "The file may be unavailable, or the bot "
            "may not have access to the storage channel.\n\n"
            "Please try again later."
        )

    except Exception as e:
        logger.exception(
            "Unexpected delivery error | user_id=%s | "
            "storage_msg_id=%s | error=%s",
            user_id,
            storage_msg_id,
            e
        )

        await loading.edit_text(
            "❌ An unexpected error occurred.\n"
            "Please try again later."
        )


# ============================================================
# /stats — OWNER ONLY
# ============================================================

@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if not message.from_user:
        return

    if message.from_user.id != OWNER_ID:
        return

    try:
        me = await bot.get_me()

        await message.answer(
            "📊 Bot Statistics\n\n"
            f"🤖 Bot: @{me.username}\n"
            f"🆔 Bot ID: {me.id}\n"
            f"💾 Storage: {STORAGE_CHANNEL_ID}\n"
            f"👤 Owner ID: {OWNER_ID}\n"
            "✅ Running!"
        )

    except Exception:
        logger.exception("Stats command failed")


# ============================================================
# MAIN
# ============================================================

async def main():
    try:
        me = await bot.get_me()

        logger.info("========================================")
        logger.info("✅ Download Bot Started")
        logger.info("🤖 Username: @%s", me.username)
        logger.info("🆔 Bot ID: %s", me.id)
        logger.info("💾 Storage Channel: %s", STORAGE_CHANNEL_ID)
        logger.info("👤 Owner ID: %s", OWNER_ID)
        logger.info("========================================")

        await dp.start_polling(bot)

    except Exception:
        logger.exception("Bot stopped due to fatal error")
        raise

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
