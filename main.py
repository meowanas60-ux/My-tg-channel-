import os
import re
import asyncio
import logging
import io
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# ============================================================
# ⚙️ কনফিগারেশন
# ============================================================
API_ID         = 34588898
API_HASH       = '4f68786337a85a232c6b18afb91fb5f6'
SESSION_STRING = os.environ.get("SESSION_STRING")

DOWNLOAD_BOT_USERNAME = os.environ.get("DOWNLOAD_BOT_USERNAME", "GetsMods_bot")
STORAGE_CHANNEL_ID    = int(os.environ.get("STORAGE_CHANNEL_ID", "-1003564232245"))

DEST_CHANNELS   = ['sahatanas', 'sahatanass', 'sahatanasss', 'sahatanassss', 'sahatanasssss', 'sahatanassssss']
IGNORE_CHANNELS = {'sahatanas', 'sahatanass', 'sahatanasss', 'sahatanassss', 'sahatanasssss', 'sahatanassssss'}

APP_QUEUE  = []
SENT_CACHE = []
ME_ID      = None

# ============================================================
# 📊 STATS
# ============================================================
STATS = {
    "total_sent":         0,
    "total_queued":       0,
    "duplicates_blocked": 0,
    "logo_generated":     0,
}

# ============================================================
# 🔁 DUPLICATE BLOCKER
# ============================================================
SENT_APK_HASHES = set()
SENT_APK_NAMES  = set()

# ============================================================
# 🎨 FOOTER
# ============================================================
MY_FOOTER = (
    "\n\n👤 **Modder:** Dev by anas\n"
    "🔰 **Downloaded from:** @sahatanas\n"
    "📢 **Join our backup:** @sahatanass\n"
    "✅ **Safe & Tested Mod Apps!**"
)

GAMBLING_KEYWORDS = ["1xbet","aviator","casino","gambling","melbet","baji","jeet","cricket365","betting"]
BAD_WORDS = ["@Getmodpcs","Join now","t.me/GetsMods_bot","Subscribe","Contact admin","Download","Install","Follow on"]

logging.basicConfig(level=logging.INFO)

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    print("🚨 WARNING: SESSION_STRING not found!")
    client = TelegramClient(StringSession(""), API_ID, API_HASH)


# ============================================================
# 🌐 WEB SERVER
# ============================================================
async def start_web_server():
    async def handle(request):
        return web.Response(text="Bot is strictly alive!")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()


# ============================================================
# 🧹 CLEANING
# ============================================================
def clean_text_content(text):
    if not text: return ""
    for w in BAD_WORDS:
        text = text.replace(w, "")
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'@\S+', '', text)
    text = re.sub(r't\.me\/\S+', '', text)
    text = re.sub(r'[\(\)\[\]]', '', text)
    return text.strip()


# ============================================================
# 📦 APK NAME PARSER
# ============================================================
def parse_apk_name(filename: str) -> dict:
    name = filename
    for ext in ('.apk', '.xapk', '.apks'):
        name = name.replace(ext, '').replace(ext.upper(), '')

    name = re.sub(r'^[a-z]{2,3}\.[a-z0-9]+\.', '', name, flags=re.IGNORECASE)

    version_match = re.search(r'[_\-\s]*(v?\d+[\.\d]+)', name, re.IGNORECASE)
    version = version_match.group(1) if version_match else ""
    if version and not version.lower().startswith('v'):
        version = "v" + version

    clean = re.sub(r'[_\-\s]*(v?\d+[\.\d]+)', '', name, flags=re.IGNORECASE)
    clean = re.sub(r'[_\-\s]*(mod|premium|pro|plus|unlocked|cracked|patched|hack|gold|vip)',
                   '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[_\-]+', ' ', clean).strip()
    clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean).strip()
    if not clean:
        clean = filename.split('.')[0][:20]

    display = f"{clean}"
    if version:
        display += f" {version}"
    display += " | Anas APK"

    return {
        "clean_name":   clean,
        "version":      version,
        "full_display": display,
    }


# ============================================================
# 🎨 AUTO LOGO GENERATOR
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

    for y in range(H):
        r1,g1,b1 = int(bg1[1:3],16), int(bg1[3:5],16), int(bg1[5:7],16)
        r2,g2,b2 = max(r1-30,0), max(g1-30,0), max(b1-30,0)
        ratio = y / H
        draw.line([(0,y),(W,y)], fill=(
            int(r1+(r2-r1)*ratio),
            int(g1+(g2-g1)*ratio),
            int(b1+(b2-b1)*ratio)
        ))

    ar,ag,ab = int(accent[1:3],16), int(accent[3:5],16), int(accent[5:7],16)
    for i in range(3):
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        d2 = ImageDraw.Draw(overlay)
        r2 = 180 + i*30
        cx, cy = W//2, H//2-30
        d2.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(ar,ag,ab, 30-i*10))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    initials = "".join(w[0].upper() for w in app_name.split()[:2]) or app_name[:2].upper()

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
        font_sm  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_tag = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm  = font_big
        font_tag = font_big

    bbox = draw.textbbox((0,0), initials, font=font_big)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx, ty = (W-tw)//2, (H-th)//2-50
    draw.text((tx+4, ty+4), initials, font=font_big, fill=(0,0,0,120))
    draw.text((tx, ty), initials, font=font_big, fill="white")

    bbox2 = draw.textbbox((0,0), app_name[:18], font=font_sm)
    draw.text(((W-(bbox2[2]-bbox2[0]))//2, ty+th+20),
              app_name[:18], font=font_sm, fill=(ar,ag,ab))

    tag = "★ Anas APK ★"
    bbox3 = draw.textbbox((0,0), tag, font=font_tag)
    draw.text(((W-(bbox3[2]-bbox3[0]))//2, H-60), tag, font=font_tag, fill="white")
    draw.rectangle([0, H-8, W, H], fill=(ar,ag,ab))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ============================================================
# 📸 PHOTO FINDER
# ============================================================
async def get_photo(event):
    try:
        if event.photo:
            return event.photo
        msgs = await client.get_messages(event.chat_id, limit=5,
                                         max_id=event.id+3, min_id=event.id-3)
        for m in msgs:
            if m.photo and m.id != event.id:
                return m.photo
    except Exception as e:
        print(f"Photo search error: {e}")
    return None


# ============================================================
# 🔍 DUPLICATE CHECK
# ============================================================
def is_duplicate(filename: str, file_id=None) -> bool:
    info = parse_apk_name(filename)
    name_key = info["clean_name"].lower().strip()
    if file_id and file_id in SENT_APK_HASHES:
        STATS["duplicates_blocked"] += 1
        return True
    if name_key in SENT_APK_NAMES:
        STATS["duplicates_blocked"] += 1
        return True
    return False

def mark_sent(filename: str, file_id=None):
    info = parse_apk_name(filename)
    name_key = info["clean_name"].lower().strip()
    SENT_APK_NAMES.add(name_key)
    if file_id:
        SENT_APK_HASHES.add(file_id)
    if len(SENT_APK_NAMES) > 500:
        SENT_APK_NAMES.discard(next(iter(SENT_APK_NAMES)))


# ============================================================
# 🤖 CAPTION BUILDER — Download link caption-এর ভেতরে
# ============================================================
def build_caption(filename: str, desc: str, storage_msg_id: int = None) -> str:
    info = parse_apk_name(filename)
    lines = [f"📱 **{info['full_display']}**"]
    if info['version']:
        lines.append(f"🔖 **Version:** {info['version']}")
    lines.append(f"📦 **File:** `{filename}`")
    if desc:
        lines.append(f"\n📝 {desc}")

    # ✅ Download link caption-এর ভেতরে — সবসময় কাজ করে
    if storage_msg_id:
        lines.append(
            f"\n⬇️ **[Download APK](https://t.me/{DOWNLOAD_BOT_USERNAME}?start=dl_{storage_msg_id})**"
        )

    lines.append(MY_FOOTER)
    return "\n".join(lines)


# ============================================================
# 💾 STORAGE CHANNEL — APK save করো
# ============================================================
async def save_to_storage(apk_msg) -> int | None:
    try:
        saved = await client.forward_messages(STORAGE_CHANNEL_ID, apk_msg)
        msg_id = saved.id if hasattr(saved, 'id') else saved[0].id
        print(f"💾 Saved to storage: msg_id={msg_id}")
        return msg_id
    except Exception as e:
        print(f"❌ Storage save error: {e}")
        return None


# ============================================================
# 📤 SEND TO DESTINATION CHANNEL
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
                parse_mode='md',
                link_preview=False
            )
        elif photo:
            await client.send_file(
                dest,
                file=photo,
                caption=caption,
                parse_mode='md',
                link_preview=False
            )
        else:
            await client.send_message(
                dest,
                message=caption,
                parse_mode='md',
                link_preview=False
            )
        return True

    except FloodWaitError as e:
        print(f"⏳ FloodWait {e.seconds}s for {dest}")
        await asyncio.sleep(e.seconds + 5)
        return False
    except Exception as e:
        print(f"❌ Send error to {dest}: {e}")
        return False


# ============================================================
# 🎯 EVENT HANDLER
# ============================================================
@client.on(events.NewMessage())
async def handler(event):
    global ME_ID
    try:
        # ── /alive command
        if event.is_private:
            sender = await event.get_sender()
            if sender and sender.id == ME_ID:
                if event.text == "/alive":
                    await event.reply(
                        f"✅ **Bot is Online!**\n"
                        f"📊 Queue: {len(APP_QUEUE)} files\n"
                        f"📤 Total Sent: {STATS['total_sent']}\n"
                        f"🚫 Duplicates Blocked: {STATS['duplicates_blocked']}"
                    )
                    return
                if event.text == "/stats":
                    await event.reply(
                        f"📊 **Bot Statistics**\n\n"
                        f"✅ Total Sent: `{STATS['total_sent']}`\n"
                        f"📥 Total Queued: `{STATS['total_queued']}`\n"
                        f"🚫 Duplicates Blocked: `{STATS['duplicates_blocked']}`\n"
                        f"🎨 Logos Generated: `{STATS['logo_generated']}`\n"
                        f"🗃️ Queue Now: `{len(APP_QUEUE)}`\n"
                        f"💾 Known APKs: `{len(SENT_APK_NAMES)}`"
                    )
                    return

        if not event.document:
            return

        chat = await event.get_chat()
        chat_username = getattr(chat, 'username', None)
        if chat_username in IGNORE_CHANNELS:
            return

        filename = event.file.name if event.file else None
        if not filename or not filename.lower().endswith(('.apk', '.xapk', '.apks')):
            return

        text = event.message.text or ""
        if any(x in (filename + text).lower() for x in GAMBLING_KEYWORDS):
            return

        file_id = str(event.file.id) if event.file and event.file.id else None
        if is_duplicate(filename, file_id):
            print(f"⛔ Duplicate blocked: {filename}")
            return

        unique_id = f"{chat_username}_{event.message.id}"
        if unique_id in SENT_CACHE:
            return

        # Photo / Logo
        photo = await get_photo(event)
        if photo is None:
            info = parse_apk_name(filename)
            try:
                photo = generate_apk_logo(info["clean_name"])
                STATS["logo_generated"] += 1
                print(f"🎨 Logo generated: {info['clean_name']}")
            except Exception as e:
                print(f"Logo error: {e}")
                photo = None

        # Saved Messages থেকে direct পাঠানো
        if event.chat_id == ME_ID:
            storage_msg_id = await save_to_storage(event.message)
            clean_desc = clean_text_content(text)
            final_caption = build_caption(filename, clean_desc, storage_msg_id)
            for dest in DEST_CHANNELS:
                ok = await send_to_channel(dest, final_caption, photo)
                if ok:
                    STATS["total_sent"] += 1
                await asyncio.sleep(5)
            mark_sent(filename, file_id)
            return

        # Queue-এ add
        clean_desc = clean_text_content(text)
        APP_QUEUE.append({
            "msg":       event.message,
            "clean_desc": clean_desc,
            "photo":     photo,
            "filename":  filename,
            "file_id":   file_id,
        })
        SENT_CACHE.append(unique_id)
        if len(SENT_CACHE) > 200:
            SENT_CACHE.pop(0)
        STATS["total_queued"] += 1
        print(f"📥 Queued: {filename} | Queue: {len(APP_QUEUE)}")

    except Exception as e:
        print(f"Handler error: {e}")


# ============================================================
# ⚙️ WORKER
# ============================================================
async def worker():
    while True:
        if APP_QUEUE:
            item = APP_QUEUE.pop(0)
            try:
                # Storage-এ save করো → msg_id পাও → caption বানাও
                storage_msg_id = await save_to_storage(item["msg"])
                final_caption = build_caption(
                    item["filename"],
                    item["clean_desc"],
                    storage_msg_id
                )

                for dest in DEST_CHANNELS:
                    ok = await send_to_channel(dest, final_caption, item["photo"])
                    if ok:
                        STATS["total_sent"] += 1
                    await asyncio.sleep(5)

                mark_sent(item["filename"], item.get("file_id"))
                await asyncio.sleep(1800)  # 30 min gap

            except Exception as e:
                print(f"Worker error: {e}")
        else:
            await asyncio.sleep(5)


# ============================================================
# 🚀 MAIN
# ============================================================
async def main():
    global ME_ID
    await start_web_server()
    await client.connect()

    if not await client.is_user_authorized():
        print("\n🚨 ERROR: SESSION_STRING is empty or invalid!\n")
        return

    me = await client.get_me()
    ME_ID = me.id
    print(f"\n✅ Logged in as: {me.first_name} (@{me.username})")
    print(f"💾 Storage Channel: {STORAGE_CHANNEL_ID}")
    print(f"🔘 Download Bot: @{DOWNLOAD_BOT_USERNAME}")
    print(f"🚫 Duplicate Blocker: ACTIVE")
    print(f"📊 Commands: /alive | /stats\n")

    asyncio.create_task(worker())
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
