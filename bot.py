import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

# ============================================================
# ⚙️ কনফিগারেশন
# ============================================================
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "8987491170:AAGSvsXrkOJi3YMNhVIlIK4OEiikbj8UdUw")
STORAGE_CHANNEL_ID = int(os.environ.get("STORAGE_CHANNEL_ID", "-1003564232245"))
OWNER_ID           = int(os.environ.get("OWNER_ID", "7701549179"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()


# ============================================================
# /start — Download Handler
# ============================================================
@dp.message(CommandStart())
async def start_handler(message: Message):
    args = message.text.split(maxsplit=1)

    # /start dl_12345 → APK download
    if len(args) > 1 and args[1].startswith("dl_"):
        param = args[1]
        try:
            storage_msg_id = int(param.replace("dl_", ""))
        except ValueError:
            await message.answer("❌ Invalid download link.")
            return

        loading = await message.answer("⏳ Please wait...\n📦 Fetching your APK file...")

        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=storage_msg_id
            )
            await loading.delete()
            await message.answer(
                "✅ Done! Your APK file is above.\n\n"
                "📢 Join: @sahatanas\n"
                "💾 Backup: @sahatanass"
            )
            logger.info(f"✅ Delivered msg_id={storage_msg_id} to user={message.from_user.id}")

        except Exception as e:
            logger.error(f"❌ Delivery failed msg_id={storage_msg_id}: {e}")
            await loading.edit_text(
                "❌ File not found or expired.\n\n"
                "📢 Check channel for latest post:\n"
                "@sahatanas"
            )
        return

    # Normal /start
    await message.answer(
        "👋 Welcome to Anas APK Bot!\n\n"
        "📱 Get premium & modded APKs for free!\n\n"
        "📢 Our Channels:\n"
        "• @sahatanas\n"
        "• @sahatanass\n\n"
        "⬇️ Click Download APK from any channel post to get the file here!"
    )


# ============================================================
# /stats — Owner only
# ============================================================
@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    me = await bot.get_me()
    await message.answer(
        f"📊 Bot Statistics\n\n"
        f"🤖 Bot: @{me.username}\n"
        f"💾 Storage: {STORAGE_CHANNEL_ID}\n"
        f"✅ Running!"
    )


# ============================================================
# 🚀 MAIN
# ============================================================
async def main():
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"💾 Storage Channel: {STORAGE_CHANNEL_ID}")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == '__main__':
    asyncio.run(main())
