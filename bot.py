import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
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
# 🌐 WEB SERVER (Render alive — bot-এর জন্য আলাদা port)
# ============================================================
async def start_web_server():
    async def handle(request):
        return web.Response(text="Bot is alive!")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("BOT_PORT", 8081))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Bot web server started on port {port}")


# ============================================================
# /start — Download Handler
# ============================================================
@dp.message(CommandStart())
async def start_handler(message: Message):
    args = message.text.split(maxsplit=1)

    # ── /start dl_12345 → APK download
    if len(args) > 1 and args[1].startswith("dl_"):
        param = args[1]  # e.g. "dl_9876543"
        try:
            # storage message ID বের করো
            storage_msg_id = int(param.replace("dl_", ""))
        except ValueError:
            await message.answer(
                "❌ Invalid download link.\n"
                "Please use the button from the channel post."
            )
            return

        # Loading message
        loading = await message.answer(
            "⏳ Please wait...\n"
            "📦 Fetching your APK file..."
        )

        try:
            # Storage channel থেকে user-এর chat-এ copy করো
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=storage_msg_id
            )
            await loading.delete()
            await message.answer(
                "✅ **Done! Your APK file is above.**\n\n"
                "📢 Join: @sahatanas\n"
                "💾 Backup: @sahatanass"
            )
            logger.info(f"✅ Delivered msg_id={storage_msg_id} to user={message.from_user.id}")

        except Exception as e:
            logger.error(f"❌ Delivery failed msg_id={storage_msg_id}: {e}")
            await loading.edit_text(
                "❌ Sorry! File not found or expired.\n\n"
                "📢 Please check the channel for the latest post:\n"
                "@sahatanas"
            )
        return

    # ── Normal /start (no param)
    await message.answer(
        "👋 **Welcome to Anas APK Bot!**\n\n"
        "📱 Get premium & modded APKs for free!\n\n"
        "📢 **Our Channels:**\n"
        "• @sahatanas\n"
        "• @sahatanass\n\n"
        "⬇️ Click the **Download APK** button from any channel post to get the file here!"
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
        f"📊 **Bot Statistics**\n\n"
        f"🤖 Bot: @{me.username}\n"
        f"💾 Storage Channel: `{STORAGE_CHANNEL_ID}`\n"
        f"✅ Bot is running!"
    )


# ============================================================
# 🚀 MAIN
# ============================================================
async def main():
    await start_web_server()
    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")
    logger.info(f"💾 Storage Channel: {STORAGE_CHANNEL_ID}")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == '__main__':
    asyncio.run(main())
