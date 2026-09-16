
import os
import re
import io
import asyncio
import logging
from html import escape as html_escape

from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# ============================================================
# CONFIGURATION
# ============================================================

API_ID = int(os.environ.get("API_ID", "34588898"))
API_HASH = os.environ.get(
    "API_HASH",
    "4f68786337a85a232c6b18afb91fb5f6"
)

SESSION_STRING = os.environ.get("SESSION_STRING")

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING environment variable is missing"
    )

# Remove @, t.me/ and whitespace from bot username
DOWNLOAD_BOT_USERNAME = os.environ.get(
    "DOWNLOAD_BOT_USERNAME",
    "GetsMods_bot"
).strip()

DOWNLOAD_BOT_USERNAME = re.sub(
    r"^(https?://)?(t\.me/)?@?",
    "",
    DOWNLOAD_BOT_USERNAME,
    flags=re.IGNORECASE
).strip("/ ")

STORAGE_CHANNEL_ID = int(
    os.environ.get("STORAGE_CHANNEL_ID", "-1003564232245")
)

DEST_CHANNELS = [
    "sahatanas",
    "sahatanass",
    "sahatanasss",
    "sahatanassss",
    "sahatanasssss",
    "sahatanassssss",
]

IGNORE_CHANNELS = set(DEST_CHANNELS)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("main_monitor")

# ============================================================
# STATE
# ============================================================

APP_QUEUE = []
SENT_CACHE = []
ME_ID = None

STATS = {
    "total_sent": 0,
    "total_queued": 0,
    "duplicates_blocked": 0,
    "logo_generated": 0,
    "storage_saved": 0,
    "storage_failed": 0,
    "send_failed": 0,
}

# Use a combined identity so different versions are allowed.
# This is in-memory; use a database for permanent persistence.
SENT_APK_KEYS = set()

# ============================================================
# FOOTER / FILTERS
# ============================================================

MY_FOOTER = (
    "\n\n👤 <b>Modder:</b> Dev by anas\n"
    "🔰 <b>Downloaded from:</b> @sahatanas\n"
    "📢 <b>Join our backup:</b> @sahatanass\n"
    "✅ <b>Safe &amp; Tested Mod Apps!</b>"
)

GAMBLING_KEYWORDS = [
    "1xbet", "aviator", "casino", "gambling",
    "melbet", "baji", "jeet", "cricket365", "betting"
]

BAD_WORDS = [
    "@Getmodpcs", "Join now", "t.me/",
    "Subscribe", "Contact admin", "Download",
    "Install", "Follow on"
]

# ============================================================
# TELETHON CLIENT
# ============================================================

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

# ============================================================
# WEB SERVER FOR RENDER
# ============================================================

async def start_web_server():
    async def handle(request):
        return web.Response(
            text="Anas APK System is alive ✅",
            content_type="text/plain"
        )

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("🌐 Web server started on port %s", port)

# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text_content(text):
    if not text:
        return ""

    for word in BAD_WORDS:
        text = text.replace(word, "")

    text = re.sub(r"\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"t\.me/\S+", "", text)
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"[\(\)\[\]]", "", text)

    return text.strip()

# ============================================================
# APK NAME PARSER
# ============================================================

def parse_apk_name(filename: str) -> dict:
    name = filename

    for ext in (".apk", ".xapk", ".apks"):
        name = name.replace(ext, "")
        name = name.replace(ext.upper(), "")

    name = re.sub(
        r"^[a-z]{2,3}\.[a-z0-9]+\.",
        "",
        name,
        flags=re.IGNORECASE
    )

    version_match = re.search(
        r"[_\-\s]*(v?\d+(?:\.\d+)+)",
        name,
        re.IGNORECASE
    )

    version = version_match.group(1) if version_match else ""

    if version and not version.lower().startswith("v"):
        version = "v" + version

    clean = re.sub(
        r"[_\-\s]*(v?\d+(?:\.\d+)+)",
        "",
        name,
        flags=re.IGNORECASE
    )

    clean = re.sub(
        r"[_\-]?(mod|premium|pro|plus|unlocked|cracked|patched|hack|gold|vip)",
        "",
        clean,
        flags=re.IGNORECASE
    )

    clean = re.sub(r"[_\-]+", " ", clean).strip()
    clean = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean).strip()

    if not clean:
        clean = filename.split(".")[0][:30]

    display = clean
    if version:
        display += f" {version}"

    display += " | Anas APK"

    return {
        "clean_name": clean,
        "version": version,
        "full_display": display,
    }

# ============================================================
# AUTO LOGO GENERATOR
# ============================================================

LOGO_BG_COLORS = [
    ("#1a1a2e", "#e94560"),
    ("#0f3460", "#16213e"),
    ("#1b1b2f", "#f5a623"),
    ("#0d0d0d", "#00d4aa"),
    ("#2d132c", "#c72c41"),
    ("#1a1a2e", "#4ecca3"),
]

def generate_apk_logo(app_name: str) -> bytes:
    import random

    W, H = 512, 512
    bg1, accent = random.choice(LOGO_BG_COLORS)

    img = Image.new("RGB", (W, H), bg1)
    draw = ImageDraw.Draw(img)

    r1 = int(bg1[1:3], 16)
    g1 = int(bg1[3:5], 16)
    b1 = int(bg1[5:7], 16)

    r2 = max(r1 - 30, 0)
    g2 = max(g1 - 30, 0)
    b2 = max(b1 - 30, 0)

    for y in range(H):
        ratio = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=(
                int(r1 + (r2 - r1) * ratio),
                int(g1 + (g2 - g1) * ratio),
                int(b1 + (b2 - b1) * ratio),
            )
        )

    ar = int(accent[1:3], 16)
    ag = int(accent[3:5], 16)
    ab = int(accent[5:7], 16)

    for i in range(3):
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(overlay)

        radius = 180 + i * 30
        cx, cy = W // 2, H // 2 - 30

        d2.ellipse(
            [
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
            ],
            fill=(ar, ag, ab, 30 - i * 10)
        )

        img = Image.alpha_composite(
            img.convert("RGBA"),
            overlay
        ).convert("RGB")

    draw = ImageDraw.Draw(img)

    words = app_name.split()
    initials = "".join(
        word[0].upper() for word in words[:2]
    ) or app_name[:2].upper()

    try:
        font_big = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            160
        )
        font_sm = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            36
        )
        font_tag = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            28
        )
    except Exception:
        font_big = ImageFont.load_default()
        font_sm = font_big
        font_tag = font_big

    bbox = draw.textbbox((0, 0), initials, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    tx = (W - tw) // 2
    ty = (H - th) // 2 - 50

    draw.text(
        (tx + 4, ty + 4),
        initials,
        font=font_big,
        fill=(0, 0, 0, 120)
    )
    draw.text(
        (tx, ty),
        initials,
        font=font_big,
        fill="white"
    )

    app_label = app_name[:18]
    bbox2 = draw.textbbox((0, 0), app_label, font=font_sm)

    draw.text(
        ((W - (bbox2[2] - bbox2[0])) // 2, ty + th + 20),
        app_label,
        font=font_sm,
        fill=(ar, ag, ab)
    )

    tag = "★ Anas APK ★"
    bbox3 = draw.textbbox((0, 0), tag, font=font_tag)

    draw.text(
        ((W - (bbox3[2] - bbox3[0])) // 2, H - 60),
        tag,
        font=font_tag,
        fill="white"
    )

    draw.rectangle(
        [0, H - 8, W, H],
        fill=(ar, ag, ab)
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ============================================================
# PHOTO FINDER
# ============================================================

async def get_photo(event):
    try:
        if event.photo:
            return event.photo

        messages = await client.get_messages(
            event.chat_id,
            limit=5,
            max_id=event.id + 3,
            min_id=max(event.id - 3, 0)
        )

        for msg in messages:
            if msg.photo and msg.id != event.id:
                return msg.photo

    except Exception:
        logger.exception(
            "Photo search failed | chat_id=%s | message_id=%s",
            event.chat_id,
            event.id
        )

    return None

# ============================================================
# DUPLICATE CHECK
# ============================================================

def get_apk_key(filename: str, file_id=None) -> str:
    info = parse_apk_name(filename)
    name_key = re.sub(
        r"\s+",
        " ",
        info["clean_name"].lower().strip()
    )

    # Version is part of the identity.
    version_key = info["version"].lower().strip()

    if file_id:
        return f"file:{file_id}"

    return f"name:{name_key}|version:{version_key}"

def is_duplicate(filename: str, file_id=None) -> bool:
    key = get_apk_key(filename, file_id)

    if key in SENT_APK_KEYS:
        STATS["duplicates_blocked"] += 1
        return True

    return False

def mark_sent(filename: str, file_id=None):
    key = get_apk_key(filename, file_id)
    SENT_APK_KEYS.add(key)

    if len(SENT_APK_KEYS) > 2000:
        SENT_APK_KEYS.pop()

# ============================================================
# CAPTION BUILDER
# ============================================================

def build_caption(
    filename: str,
    desc: str,
    storage_msg_id: int = None
) -> str:
    info = parse_apk_name(filename)

    lines = [
        f"📱 <b>{html_escape(info['full_display'])}</b>"
    ]

    if info["version"]:
        lines.append(
            f"🔖 <b>Version:</b> "
            f"{html_escape(info['version'])}"
        )

    lines.append(
        f"📦 <b>File:</b> "
        f"<code>{html_escape(filename)}</code>"
    )

    if desc:
        lines.append(
            f"\n📝 {html_escape(desc)}"
        )

    # Never publish a broken or empty download link.
    if storage_msg_id and storage_msg_id > 0:
        download_url = (
            f"https://t.me/{DOWNLOAD_BOT_USERNAME}"
            f"?start=dl_{storage_msg_id}"
        )

        lines.append(
            f"\n⬇️ <b><a href=\"{download_url}\">"
            f"Download APK</a></b>"
        )
    else:
        lines.append(
            "\n⚠️ Download link is temporarily unavailable."
        )

    lines.append(MY_FOOTER)

    return "\n".join(lines)

# ============================================================
# STORAGE CHANNEL
# ============================================================

async def save_to_storage(apk_msg):
    try:
        saved = await client.forward_messages(
            STORAGE_CHANNEL_ID,
            apk_msg
        )

        if isinstance(saved, list):
            if not saved:
                raise RuntimeError("Storage returned an empty list")
            storage_msg_id = saved[0].id
        else:
            storage_msg_id = saved.id

        if not storage_msg_id:
            raise RuntimeError("Storage message ID is empty")

        STATS["storage_saved"] += 1

        logger.info(
            "💾 APK saved to storage | msg_id=%s",
            storage_msg_id
        )

        return storage_msg_id

    except Exception:
        STATS["storage_failed"] += 1

        logger.exception(
            "❌ Storage save failed | channel_id=%s",
            STORAGE_CHANNEL_ID
        )

        return None

# ============================================================
# SEND TO DESTINATION CHANNEL
# ============================================================

async def send_to_channel(dest, caption, photo):
    try:
        if photo and isinstance(photo, bytes):
            buf = io.BytesIO(photo)
            buf.name = "logo.png"

            await client.send_file(
                dest,
                file=buf,
                caption=caption,
                parse_mode="html",
                link_preview=False
            )

        elif photo:
            await client.send_file(
                dest,
                file=photo,
                caption=caption,
                parse_mode="html",
                link_preview=False
            )

        else:
            await client.send_message(
                dest,
                message=caption,
                parse_mode="html",
                link_preview=False
            )

        logger.info("📤 Sent to destination: %s", dest)
        return True

    except FloodWaitError as e:
        logger.warning(
            "⏳ FloodWait | destination=%s | seconds=%s",
            dest,
            e.seconds
        )
        await asyncio.sleep(e.seconds + 5)
        return False

    except Exception:
        STATS["send_failed"] += 1

        logger.exception(
            "❌ Send failed | destination=%s",
            dest
        )

        return False

# ============================================================
# EVENT HANDLER
# ============================================================

@client.on(events.NewMessage())
async def handler(event):
    global ME_ID

    try:
        # Commands from Saved Messages / own account
        if event.is_private:
            sender = await event.get_sender()

            if sender and sender.id == ME_ID:
                command = (event.text or "").strip().lower()

                if command == "/alive":
                    await event.reply(
                        f"✅ <b>Bot is Online!</b>\n"
                        f"📊 Queue: {len(APP_QUEUE)} files\n"
                        f"📤 Total Sent: {STATS['total_sent']}\n"
                        f"📥 Total Queued: {STATS['total_queued']}\n"
                        f"🚫 Duplicates: {STATS['duplicates_blocked']}\n"
                        f"💾 Storage Saved: {STATS['storage_saved']}\n"
                        f"❌ Storage Failed: {STATS['storage_failed']}",
                        parse_mode="html"
                    )
                    return

                if command == "/stats":
                    await event.reply(
                        f"📊 <b>Bot Statistics</b>\n\n"
                        f"✅ Total Sent: <code>{STATS['total_sent']}</code>\n"
                        f"📥 Total Queued: <code>{STATS['total_queued']}</code>\n"
                        f"🚫 Duplicates: <code>{STATS['duplicates_blocked']}</code>\n"
                        f"🎨 Logos: <code>{STATS['logo_generated']}</code>\n"
                        f"💾 Storage Saved: <code>{STATS['storage_saved']}</code>\n"
                        f"❌ Storage Failed: <code>{STATS['storage_failed']}</code>\n"
                        f"📤 Send Failed: <code>{STATS['send_failed']}</code>\n"
                        f"🗃️ Queue: <code>{len(APP_QUEUE)}</code>\n"
                        f"💾 Known APKs: <code>{len(SENT_APK_KEYS)}</code>",
                        parse_mode="html"
                    )
                    return

        # Only process document files
        if not event.document:
            return

        chat = await event.get_chat()
        chat_username = getattr(chat, "username", None)

        if chat_username and chat_username.lower() in {
            x.lower() for x in IGNORE_CHANNELS
        }:
            return

        filename = event.file.name if event.file else None

        if not filename:
            return

        if not filename.lower().endswith(
            (".apk", ".xapk", ".apks")
        ):
            return

        text = event.message.text or ""

        if any(
            keyword in (filename + text).lower()
            for keyword in GAMBLING_KEYWORDS
        ):
            logger.info(
                "🚫 Gambling APK skipped: %s",
                filename
            )
            return

        file_id = (
            str(event.file.id)
            if event.file and event.file.id
            else None
        )

        if is_duplicate(filename, file_id):
            logger.info("⛔ Duplicate blocked: %s", filename)
            return

        unique_id = f"{event.chat_id}_{event.message.id}"

        if unique_id in SENT_CACHE:
            return

        photo = await get_photo(event)

        if photo is None:
            info = parse_apk_name(filename)

            try:
                photo = generate_apk_logo(info["clean_name"])
                STATS["logo_generated"] += 1
                logger.info(
                    "🎨 Logo generated: %s",
                    info["clean_name"]
                )

            except Exception:
                logger.exception("Logo generation failed")
                photo = None

        clean_desc = clean_text_content(text)

        # Saved Messages → process immediately
        if event.chat_id == ME_ID:
            storage_msg_id = await save_to_storage(event.message)

            if not storage_msg_id:
                logger.error(
                    "❌ Saved Messages APK skipped: "
                    "storage save failed | filename=%s",
                    filename
                )
                return

            final_caption = build_caption(
                filename,
                clean_desc,
                storage_msg_id
            )

            success_count = 0

            for dest in DEST_CHANNELS:
                ok = await send_to_channel(
                    dest,
                    final_caption,
                    photo
                )

                if ok:
                    STATS["total_sent"] += 1
                    success_count += 1

                await asyncio.sleep(5)

            # Only mark as sent if at least one destination succeeded.
            if success_count > 0:
                mark_sent(filename, file_id)
                logger.info(
                    "✅ Saved Messages APK completed | "
                    "filename=%s | destinations=%s",
                    filename,
                    success_count
                )
            else:
                logger.error(
                    "❌ No destination succeeded | filename=%s",
                    filename
                )

            return

        # Other source channels → queue
        APP_QUEUE.append({
            "msg": event.message,
            "clean_desc": clean_desc,
            "photo": photo,
            "filename": filename,
            "file_id": file_id,
            "unique_id": unique_id,
        })

        SENT_CACHE.append(unique_id)

        if len(SENT_CACHE) > 500:
            SENT_CACHE.pop(0)

        STATS["total_queued"] += 1

        logger.info(
            "📥 Queued APK | filename=%s | queue=%s",
            filename,
            len(APP_QUEUE)
        )

    except Exception:
        logger.exception(
            "❌ Event handler failed | chat_id=%s | message_id=%s",
            event.chat_id,
            event.id
        )

# ============================================================
# WORKER
# ============================================================

async def worker():
    logger.info("⚙️ Worker started")

    while True:
        if not APP_QUEUE:
            await asyncio.sleep(5)
            continue

        item = APP_QUEUE.pop(0)
        filename = item["filename"]

        try:
            # 1. Save original APK to storage
            storage_msg_id = await save_to_storage(item["msg"])

            if not storage_msg_id:
                logger.error(
                    "❌ Queue item skipped: storage failed | filename=%s",
                    filename
                )
                continue

            # 2. Build caption with valid download link
            final_caption = build_caption(
                filename,
                item["clean_desc"],
                storage_msg_id
            )

            # 3. Send to all destination channels
            success_count = 0

            for dest in DEST_CHANNELS:
                ok = await send_to_channel(
                    dest,
                    final_caption,
                    item["photo"]
                )

                if ok:
                    STATS["total_sent"] += 1
                    success_count += 1

                await asyncio.sleep(5)

            # 4. Only mark successful if at least one channel got it
            if success_count > 0:
                mark_sent(filename, item.get("file_id"))

                logger.info(
                    "✅ Queue item completed | filename=%s | "
                    "successful_destinations=%s",
                    filename,
                    success_count
                )
            else:
                logger.error(
                    "❌ Queue item failed on all destinations | "
                    "filename=%s",
                    filename
                )

            # 30-minute gap between queue items
            await asyncio.sleep(1800)

        except Exception:
            logger.exception(
                "❌ Worker error | filename=%s",
                filename
            )
            await asyncio.sleep(10)

# ============================================================
# MAIN
# ============================================================

async def main():
    global ME_ID

    await start_web_server()

    logger.info("🔌 Connecting Telethon...")
    await client.connect()

    if not await client.is_user_authorized():
        logger.error(
            "🚨 SESSION_STRING is empty or invalid. "
            "Telethon user is not authorized."
        )
        await client.disconnect()
        return

    me = await client.get_me()
    ME_ID = me.id

    logger.info("========================================")
    logger.info("✅ Main Monitor Started")
    logger.info("👤 Logged in as: %s (@%s)", me.first_name, me.username)
    logger.info("🆔 User ID: %s", ME_ID)
    logger.info("💾 Storage Channel: %s", STORAGE_CHANNEL_ID)
    logger.info("🤖 Download Bot: @%s", DOWNLOAD_BOT_USERNAME)
    logger.info("📢 Destination Channels: %s", len(DEST_CHANNELS))
    logger.info("🚫 Duplicate Blocker: ACTIVE")
    logger.info("========================================")

    asyncio.create_task(worker())

    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
