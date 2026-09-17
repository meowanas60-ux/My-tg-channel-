import os
import re
import io
import asyncio
import logging
from html import escape as html_escape
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
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

PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "https://my-tg-channel.onrender.com"
).rstrip("/")

ADSTERRA_SMARTLINK = (
    "https://www.profitableratecpmnetwork.com/"
    "kh4t4gsu0?key=827386a9e5fed85caafe0ab18cc6f8d0"
)

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
# WEB SERVER + APK LANDING PAGE
# ============================================================

def landing_page_html(storage_msg_id: int, app_name: str = "APK Application", version: str = "Latest", filename: str = "Android Application") -> str:
    safe_app_name = html_escape(app_name or "APK Application")
    safe_version = html_escape(version or "Latest")
    safe_filename = html_escape(filename or "Android Application")
    telegram_link = f"https://t.me/{DOWNLOAD_BOT_USERNAME}?start=dl_{storage_msg_id}"
    visited_key = f"anas_ad_visited_{storage_msg_id}"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_app_name} | Anas APK System</title>
<meta name="description" content="Download {safe_app_name} from Anas APK System.">
<style>
*{{box-sizing:border-box}}
html{{min-height:100%}}
body{{min-height:100vh;margin:0;padding:24px 12px;font-family:Arial,Helvetica,sans-serif;color:#fff;background:linear-gradient(180deg,#70bd79 0%,#55a99a 38%,#347fb1 72%,#2364a4 100%)}}
.page{{width:100%;max-width:480px;margin:0 auto}}
.brand{{text-align:center;margin:8px 0 24px}}
.brand-symbol{{width:94px;height:94px;margin:0 auto 18px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.16);border:2px solid rgba(255,255,255,.55);box-shadow:0 10px 30px rgba(0,0,0,.12);font-size:31px;font-weight:800;letter-spacing:-2px}}
.brand h1{{margin:0;font-size:25px;font-weight:800}}
.brand p{{margin:8px 0 0;color:rgba(255,255,255,.82);font-size:13px}}
.card{{padding:22px;border-radius:24px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);box-shadow:0 18px 45px rgba(0,0,0,.13);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}}
.app-icon{{width:78px;height:78px;margin:0 auto 14px;border-radius:20px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.92);color:#277bb0;font-size:26px;font-weight:800;box-shadow:0 8px 20px rgba(0,0,0,.12)}}
.app-title{{text-align:center;margin-bottom:18px}}
.app-title h2{{margin:0;font-size:23px;font-weight:800;word-break:break-word}}
.app-title span{{display:inline-block;margin-top:8px;padding:5px 11px;border-radius:30px;background:rgba(255,255,255,.18);color:rgba(255,255,255,.9);font-size:12px}}
.details{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:18px 0}}
.detail{{padding:12px 8px;border-radius:13px;text-align:center;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.16)}}
.detail small{{display:block;margin-bottom:5px;color:rgba(255,255,255,.7);font-size:10px;text-transform:uppercase}}
.detail strong{{display:block;color:#fff;font-size:13px;word-break:break-word}}
.ad-box{{width:100%;margin:22px 0;padding:7px 0;text-align:center;overflow:hidden}}
.ad-label{{margin-bottom:7px;color:rgba(255,255,255,.65);font-size:10px;letter-spacing:1px;text-transform:uppercase}}
.section-title{{margin:20px 0 8px;font-size:17px}}
.description{{margin:0;color:rgba(255,255,255,.8);font-size:13px;line-height:1.7}}
.file-name{{margin-top:15px;padding:11px;border-radius:10px;background:rgba(0,0,0,.12);color:rgba(255,255,255,.78);font-size:11px;line-height:1.5;word-break:break-word}}
.download-btn{{display:block;width:100%;margin-top:22px;padding:15px 18px;border:0;border-radius:13px;background:#fff;color:#2775aa;font-size:16px;font-weight:800;text-align:center;text-decoration:none;cursor:pointer;box-shadow:0 8px 22px rgba(0,0,0,.15);transition:transform .2s,background .2s}}
.download-btn:hover{{background:#eaf7ff;transform:translateY(-2px)}}
.download-btn:active{{transform:translateY(0)}}
.note{{margin:12px 0 0;color:rgba(255,255,255,.72);font-size:11px;line-height:1.6;text-align:center}}
.footer{{margin:22px 0 5px;color:rgba(255,255,255,.68);font-size:11px;text-align:center}}
@media(max-width:360px){{body{{padding:18px 9px}}.card{{padding:17px}}.brand h1{{font-size:22px}}}}
</style>
</head>
<body>
<main class="page">
<header class="brand"><div class="brand-symbol">GM</div><h1>Anas APK System</h1><p>Android Applications &amp; Downloads</p></header>
<section class="card">
<div class="app-icon">APK</div>
<div class="app-title"><h2>{safe_app_name}</h2><span>{safe_version}</span></div>
<div class="details">
<div class="detail"><small>Version</small><strong>{safe_version}</strong></div>
<div class="detail"><small>Platform</small><strong>Android</strong></div>
<div class="detail"><small>File Type</small><strong>APK</strong></div>
<div class="detail"><small>Source</small><strong>Telegram</strong></div>
</div>

<!-- Adsterra Native Banner -->
<div class="ad-box"><div class="ad-label">Advertisement</div>
<script async="async" data-cfasync="false" src="https://pl31376477.profitableratecpmnetwork.com/57efad1efb9e1a90ad6d5626c971d9e6/invoke.js"></script>
<div id="container-57efad1efb9e1a90ad6d5626c971d9e6"></div>
</div>

<h3 class="section-title">About this application</h3>
<p class="description">Review the application information below. Click the continue button to proceed to the download process.</p>
<div class="file-name"><strong>File:</strong> {safe_filename}</div>

<!-- First click: Smartlink. After Back: Telegram bot. -->
<a id="continueDownload" class="download-btn" href="{ADSTERRA_SMARTLINK}" target="_self" rel="nofollow sponsored noopener noreferrer">Continue to Download</a>
<p id="downloadNote" class="note">Tap once to continue. Return to this page and tap again to open the Telegram download bot.</p>
</section>
<div class="footer">© 2026 Anas APK System</div>
</main>

<!-- Adsterra Social Bar -->
<script src="https://pl31376479.profitableratecpmnetwork.com/47/9e/72/479e72023d7d0e8985828d9969ff82a3.js"></script>
<script>
(function() {{
  const button = document.getElementById('continueDownload');
  const note = document.getElementById('downloadNote');
  const smartLink = {ADSTERRA_SMARTLINK!r};
  const telegramLink = {telegram_link!r};
  const visitedKey = {visited_key!r};

  function setTelegramMode() {{
    button.href = telegramLink;
    button.target = '_self';
    button.textContent = 'Get APK from Telegram';
    note.textContent = 'Tap the button again to open the Telegram bot and receive the file.';
  }}

  if (sessionStorage.getItem(visitedKey) === 'true') {{
    setTelegramMode();
  }}

  button.addEventListener('click', function() {{
    if (sessionStorage.getItem(visitedKey) !== 'true') {{
      sessionStorage.setItem(visitedKey, 'true');
      button.href = smartLink;
      button.target = '_self';
      return;
    }}
    button.href = telegramLink;
    button.target = '_self';
  }});
}})();
</script>
</body>
</html>'''


async def start_web_server():
    async def health_handler(request):
        return web.Response(text="Anas APK System is alive ✅", content_type="text/plain")

    async def landing_handler(request):
        try:
            storage_msg_id = int(request.match_info["storage_msg_id"])
            app_name = request.query.get("name", "APK Application")
            version = request.query.get("version", "Latest")
            filename = request.query.get("file", "Android Application")
            return web.Response(
                text=landing_page_html(storage_msg_id, app_name, version, filename),
                content_type="text/html",
                charset="utf-8"
            )
        except (TypeError, ValueError):
            return web.Response(text="Invalid download link", status=400, content_type="text/plain")
        except Exception:
            logger.exception("Landing page failed")
            return web.Response(text="Landing page error", status=500, content_type="text/plain")

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/download/{storage_msg_id}", landing_handler)

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
# REAL APP LOGO / BRANDED POSTER
# ============================================================

# Known official domains. The bot tries these first when looking for
# an online logo. Add more apps/domains here whenever needed.
APP_DOMAINS = {
    "youtube": ["youtube.com"],
    "youtube lite": ["youtube.com"],
    "youtube vanced": ["youtube.com"],
    "deepseek": ["deepseek.com"],
    "spotify": ["spotify.com"],
    "spotiduck": ["spotify.com"],
    "tiktok": ["tiktok.com"],
    "facebook": ["facebook.com"],
    "instagram": ["instagram.com"],
    "telegram": ["telegram.org"],
    "whatsapp": ["whatsapp.com"],
    "capcut": ["capcut.com"],
    "snapchat": ["snapchat.com"],
    "netflix": ["netflix.com"],
    "chatgpt": ["openai.com"],
    "openai": ["openai.com"],
    "gemini": ["gemini.google.com", "google.com"],
    "google": ["google.com"],
    "chrome": ["google.com"],
    "discord": ["discord.com"],
    "reddit": ["reddit.com"],
    "pinterest": ["pinterest.com"],
    "x": ["x.com"],
    "twitter": ["x.com"],
    "linkedin": ["linkedin.com"],
    "canva": ["canva.com"],
    "picsart": ["picsart.com"],
    "shazam": ["shazam.com"],
}


def _normalise_app_name(name: str) -> str:
    name = (name or "").lower()
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def logo_domains_for_app(app_name: str):
    normalized = _normalise_app_name(app_name)
    domains = []

    for key, values in APP_DOMAINS.items():
        if key in normalized or normalized in key:
            domains.extend(values)

    # Reasonable candidates for lesser-known apps.
    compact = normalized.replace(" ", "")
    if compact:
        domains.extend([
            f"{compact}.com",
            f"{compact}.app",
            f"{compact}.net",
        ])

    # Keep order but remove duplicates.
    return list(dict.fromkeys(domains))


async def fetch_online_app_logo(app_name: str):
    """Fetch an online logo from Google's favicon service.

    Returns PNG/JPEG bytes only when a valid image is received.
    No generated initials are used as a fallback.
    """
    import aiohttp

    domains = logo_domains_for_app(app_name)
    if not domains:
        return None

    timeout = aiohttp.ClientTimeout(total=12)
    headers = {
        "User-Agent": "Mozilla/5.0 AnasAPKSystem/1.0"
    }

    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        ) as session:
            for domain in domains:
                url = (
                    "https://www.google.com/s2/favicons"
                    f"?domain={quote(domain)}&sz=256"
                )

                try:
                    async with session.get(url, allow_redirects=True) as resp:
                        if resp.status != 200:
                            continue

                        data = await resp.read()
                        if len(data) < 100:
                            continue

                        try:
                            image = Image.open(io.BytesIO(data))
                            image.load()
                            if image.width < 16 or image.height < 16:
                                continue
                            logger.info(
                                "🌐 Online logo found | app=%s | domain=%s",
                                app_name,
                                domain
                            )
                            return data
                        except Exception:
                            continue
                except Exception:
                    continue
    except Exception:
        logger.exception("Online logo lookup failed | app=%s", app_name)

    logger.warning("⚠️ No online logo found | app=%s", app_name)
    return None


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def create_branded_poster(app_name: str, logo_bytes: bytes) -> bytes:
    """Create a purple/blue branded poster using the real app logo."""
    W, H = 1080, 1080

    img = Image.new("RGB", (W, H), "#321078")
    px = img.load()

    # Purple-to-blue gradient matching the requested reference style.
    top = (116, 11, 191)
    bottom = (19, 35, 151)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        ImageDraw.Draw(img).line((0, y, W, y), fill=(r, g, b))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Abstract leaf-like diagonal shapes.
    leaf_color = (17, 7, 91, 145)
    for x, y, w, h in [
        (-40, 20, 220, 620), (110, -30, 170, 520),
        (300, -70, 150, 430), (820, -40, 180, 560),
        (950, 120, 190, 530), (-80, 690, 260, 500),
        (820, 730, 250, 500),
    ]:
        od.polygon(
            [(x, y), (x + w, y + 40), (x + w // 2, y + h),
             (x + w // 3, y + h // 3)],
            fill=leaf_color
        )

    # Soft glow behind the icon.
    od.ellipse((250, 170, 830, 750), fill=(210, 30, 255, 45))
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    muted = (232, 218, 255, 255)

    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    f_brand = _font(font_bold, 54)
    f_sub = _font(font_regular, 28)
    f_app = _font(font_bold, 64)
    f_small = _font(font_regular, 27)
    f_tag = _font(font_bold, 30)

    def centered(text, y, font, fill=white):
        box = draw.textbbox((0, 0), text, font=font)
        x = (W - (box[2] - box[0])) // 2
        draw.text((x, y), text, font=font, fill=fill)

    centered("Anas APK System", 55, f_brand)
    centered("Android Applications & Downloads", 125, f_sub, muted)

    # Real logo in a clean rounded white frame.
    try:
        icon = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        icon.thumbnail((420, 420), Image.Resampling.LANCZOS)

        frame = Image.new("RGBA", (500, 500), (255, 255, 255, 255))
        mask = Image.new("L", (500, 500), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, 499, 499), radius=72, fill=255)
        frame.putalpha(mask)

        icon_canvas = Image.new("RGBA", (500, 500), (255, 255, 255, 0))
        ix = (500 - icon.width) // 2
        iy = (500 - icon.height) // 2
        icon_canvas.alpha_composite(icon, (ix, iy))
        icon_canvas.putalpha(mask)

        shadow = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((30, 30, 530, 530), radius=80, fill=(0, 0, 0, 130))
        shadow = shadow.filter(ImageFilter.GaussianBlur(25))
        img.alpha_composite(shadow, (260, 205))
        img.alpha_composite(frame, (290, 205))
        img.alpha_composite(icon_canvas, (290, 205))
    except Exception as exc:
        raise RuntimeError(f"Invalid online logo image: {exc}")

    clean_name = app_name.strip() or "APK Application"
    if len(clean_name) > 25:
        clean_name = clean_name[:25].rstrip() + "…"

    centered(clean_name, 755, f_app)
    centered("Official app logo • Android APK", 835, f_small, muted)

    # Bottom brand strip.
    strip_y = 930
    draw.rounded_rectangle(
        (70, strip_y, W - 70, 1000),
        radius=28,
        fill=(8, 5, 65, 180),
        outline=(180, 80, 255, 220),
        width=3
    )
    centered("★ Anas APK ★", 950, f_tag)

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()

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
            f"{PUBLIC_BASE_URL}/download/{storage_msg_id}"
            f"?name={quote(info['clean_name'])}"
            f"&version={quote(info['version'] or 'Latest')}"
            f"&file={quote(filename)}"
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

        # If the source message has no photo, find the real app logo online.
        # If no valid logo is found, skip this APK instead of generating fake
        # initials such as YT, D, or SD.
        if photo is None:
            info = parse_apk_name(filename)
            online_logo = await fetch_online_app_logo(info["clean_name"])

            if online_logo is None:
                logger.warning(
                    "⏭️ APK skipped: real logo not found | app=%s | filename=%s",
                    info["clean_name"],
                    filename
                )
                return

            try:
                photo = create_branded_poster(
                    info["clean_name"],
                    online_logo
                )
                STATS["logo_generated"] += 1
                logger.info(
                    "🖼️ Real online logo poster created: %s",
                    info["clean_name"]
                )
            except Exception:
                logger.exception("Real logo poster creation failed")
                return
        elif not isinstance(photo, bytes):
            # A source photo may be unrelated to the APK. Keep it only when
            # the user supplied a photo; otherwise online logo is preferred.
            pass

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
