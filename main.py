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

# Default queue gap is 30 minutes; change with Saved Messages command /post <minutes>.
POST_INTERVAL_MINUTES = 30

# In-memory poster cache only. No database is used.
POSTER_CACHE = {}
MAX_POSTER_CACHE = 300
POSTER_COUNTER = 0

# ============================================================
# FOOTER / FILTERS
# ============================================================

MY_FOOTER = (
    "\n\n🛡️ <b>APK information:</b> Please scan files before installing.\n"
    "📦 <b>Delivery:</b> Telegram download bot"
)

GAMBLING_KEYWORDS = [
    "1xbet", "aviator", "casino", "gambling",
    "melbet", "baji", "jeet", "cricket365", "betting"
]

BAD_WORDS = [
    "@Getmodpcs", "Join now", "t.me/", "https://", "http://",
    "Subscribe", "Contact admin", "Download", "Install",
    "Follow on", "join our", "join channel", "only 3000 entry"
]

# Skip scam/gambling/hack-promotion posts instead of republishing them.
BLOCKED_PROMO_TERMS = (
    "1xbet", "aviator", "casino", "gambling", "betting", "melbet",
    "baji", "jeet", "cricket365", "deposit money", "daily profit",
    "earn up to", "profit limit", "hack and earn", "use hack",
    "only deposit", "investment guaranteed"
)

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

def _poster_cache_put(storage_msg_id: int, poster_bytes: bytes):
    if not storage_msg_id or not poster_bytes:
        return
    POSTER_CACHE[storage_msg_id] = poster_bytes
    while len(POSTER_CACHE) > MAX_POSTER_CACHE:
        oldest = next(iter(POSTER_CACHE))
        POSTER_CACHE.pop(oldest, None)


def _poster_cache_get(storage_msg_id: int):
    return POSTER_CACHE.get(storage_msg_id)


def landing_page_html(
    storage_msg_id: int,
    app_name: str = "APK Application",
    version: str = "Latest",
    filename: str = "Android Application",
) -> str:
    safe_app_name = html_escape(app_name or "APK Application")
    safe_version = html_escape(version or "Latest")
    safe_filename = html_escape(filename or "Android Application")
    telegram_link = f"https://t.me/{DOWNLOAD_BOT_USERNAME}?start=dl_{storage_msg_id}"
    variant = sum((i + 1) * ord(ch) for i, ch in enumerate(filename or app_name)) % 6
    poster_url = f"/poster/{storage_msg_id}?name={quote(app_name or 'APK Application')}&version={quote(version or 'Latest')}&variant={variant}"
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
html{{min-height:100%;background:#09051d}}
body{{min-height:100vh;margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;color:#fff;background:#09051d;overflow-x:hidden}}
.page{{width:100%;min-height:100vh;position:relative;isolation:isolate}}
.hero{{position:relative;min-height:100vh;display:flex;align-items:flex-end;justify-content:center;padding:18px 12px 28px;overflow:hidden}}
.hero-bg{{position:absolute;inset:0;background-image:linear-gradient(180deg,rgba(7,3,25,.10) 0%,rgba(7,3,25,.30) 42%,rgba(7,3,25,.94) 92%),url('{poster_url}');background-size:cover;background-position:center top;filter:saturate(1.08);transform:scale(1.04);z-index:-3}}
.hero-blur{{position:absolute;inset:-35px;background-image:url('{poster_url}');background-size:cover;background-position:center top;filter:blur(28px) saturate(1.15);opacity:.38;z-index:-4}}
.hero-glass{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.04),rgba(5,2,20,.18) 42%,rgba(5,2,20,.82) 100%);z-index:-2}}
.content{{width:100%;max-width:520px;margin:0 auto}}
.topbar{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding:0 4px}}
.brand{{font-size:14px;font-weight:800;letter-spacing:.3px;text-shadow:0 2px 12px rgba(0,0,0,.45)}}
.badge{{padding:7px 11px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.26);backdrop-filter:blur(10px);font-size:11px;font-weight:700}}
.card{{padding:20px;border-radius:26px;background:rgba(8,4,27,.70);border:1px solid rgba(255,255,255,.18);box-shadow:0 20px 55px rgba(0,0,0,.38);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}}
.kicker{{display:flex;align-items:center;gap:8px;color:#d9ccff;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px}}
.dot{{width:7px;height:7px;border-radius:50%;background:#7cffc4;box-shadow:0 0 12px #7cffc4}}
.app-title{{margin:9px 0 4px;font-size:29px;line-height:1.12;font-weight:900;word-break:break-word}}
.version{{color:#c9bce9;font-size:13px}}
.details{{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin:18px 0 12px}}
.detail{{padding:11px 10px;border-radius:13px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10)}}
.detail small{{display:block;color:#9f93bd;font-size:9px;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px}}
.detail strong{{display:block;color:#fff;font-size:12px;word-break:break-word}}
.ad-box{{width:100%;margin:14px 0 5px;padding:6px 0;text-align:center;overflow:hidden}}
.ad-label{{margin-bottom:6px;color:#8e83aa;font-size:9px;letter-spacing:1px;text-transform:uppercase}}
.file-name{{margin-top:13px;padding:11px 12px;border-radius:12px;background:rgba(0,0,0,.20);color:#d7d0e5;font-size:11px;line-height:1.5;word-break:break-word}}
.download-btn{{display:block;width:100%;margin-top:16px;padding:15px 18px;border:0;border-radius:14px;background:linear-gradient(135deg,#fff,#d9ccff);color:#31116e;font-size:16px;font-weight:900;text-align:center;text-decoration:none;cursor:pointer;box-shadow:0 10px 28px rgba(0,0,0,.26);transition:transform .18s,filter .18s}}
.download-btn:hover{{filter:brightness(1.04);transform:translateY(-1px)}}
.download-btn:active{{transform:translateY(0)}}
.note{{margin:10px 0 0;color:#9e94af;font-size:10px;line-height:1.5;text-align:center}}
.warning{{margin-top:13px;color:#bcb3ca;font-size:10px;line-height:1.55;text-align:center}}
.footer{{margin:13px 0 0;color:#8d839e;font-size:10px;text-align:center}}
@media(max-width:380px){{.hero{{padding:12px 9px 18px}}.card{{padding:16px;border-radius:22px}}.app-title{{font-size:25px}}}}
</style>
</head>
<body>
<main class="page">
<section class="hero">
<div class="hero-blur"></div><div class="hero-bg"></div><div class="hero-glass"></div>
<div class="content">
<div class="topbar"><div class="brand">ANAS APK SYSTEM</div><div class="badge">ANDROID APK</div></div>
<section class="card">
<div class="kicker"><span class="dot"></span> New APK release</div>
<h1 class="app-title">{safe_app_name}</h1>
<div class="version">Version: {safe_version}</div>
<div class="details">
<div class="detail"><small>Platform</small><strong>Android</strong></div>
<div class="detail"><small>Type</small><strong>APK</strong></div>
<div class="detail"><small>Delivery</small><strong>Telegram Bot</strong></div>
<div class="detail"><small>Source</small><strong>ANAS APK</strong></div>
</div>

<div class="ad-box"><div class="ad-label">Advertisement</div>
<script async="async" data-cfasync="false" src="https://pl31376477.profitableratecpmnetwork.com/57efad1efb9e1a90ad6d5626c971d9e6/invoke.js"></script>
<div id="container-57efad1efb9e1a90ad6d5626c971d9e6"></div>
</div>

<div class="file-name"><strong>File:</strong> {safe_filename}</div>
<a id="continueDownload" class="download-btn" href="{ADSTERRA_SMARTLINK}" target="_self" rel="nofollow sponsored noopener noreferrer">Continue to Download</a>
<p id="downloadNote" class="note">Continue once, return here, then open Telegram to receive your APK.</p>
<p class="warning">🛡️ Please scan the APK before installing.</p>
</section>
<div class="footer">© 2026 Anas APK System</div>
</div>
</section>
</main>
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
    button.textContent = 'Get APK from Telegram';
    note.textContent = 'Tap the button to open the Telegram bot and receive the file.';
  }}
  if (sessionStorage.getItem(visitedKey) === 'true') setTelegramMode();
  button.addEventListener('click', function() {{
    if (sessionStorage.getItem(visitedKey) !== 'true') {{
      sessionStorage.setItem(visitedKey, 'true');
      button.href = smartLink;
      return;
    }}
    button.href = telegramLink;
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

    async def poster_handler(request):
        try:
            storage_msg_id = int(request.match_info["storage_msg_id"])
            if storage_msg_id <= 0:
                raise ValueError
            cached = _poster_cache_get(storage_msg_id)
            if cached:
                return web.Response(body=cached, content_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

            app_name = request.query.get("name", "APK Application")
            variant = int(request.query.get("variant", str(storage_msg_id)))
            poster = await make_dynamic_poster(app_name, variant=variant)
            if not poster:
                return web.Response(status=404, text="Poster unavailable")
            _poster_cache_put(storage_msg_id, poster)
            return web.Response(body=poster, content_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
        except (TypeError, ValueError):
            return web.Response(text="Invalid poster link", status=400, content_type="text/plain")
        except Exception:
            logger.exception("Poster endpoint failed")
            return web.Response(text="Poster error", status=500, content_type="text/plain")

    app.router.add_get("/poster/{storage_msg_id}", poster_handler)

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

    # Remove source-channel handles / promo tags commonly embedded in filenames.
    clean = re.sub(r"@[A-Za-z0-9_]{3,}", " ", clean)
    clean = re.sub(r"(?i)\b(?:easy\s*apk|anas\s*apk|apk\s*mod)\b", " ", clean)
    clean = re.sub(r"[_\-]+", " ", clean).strip()
    clean = re.sub(r"\s+", " ", clean).strip()
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
    "twitter": ["x.com"],
    "mx player": ["mxplayer.in"],
    "mxplayer": ["mxplayer.in"],
    "playit": ["playit.vc", "playit.app"],
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
    """Return domains only for confident app-name matches.

    Avoid substring matches such as the ``x`` in ``hex blade``; those
    caused unrelated logos to be attached to an APK.
    """
    normalized = _normalise_app_name(app_name)
    domains = []

    for key, values in APP_DOMAINS.items():
        key_norm = _normalise_app_name(key)
        if normalized == key_norm or normalized.startswith(key_norm + " ") or normalized.endswith(" " + key_norm):
            domains.extend(values)

    # A single-letter brand is only safe when it is the complete app name.
    if normalized in {"x", "twitter"}:
        domains.extend(["x.com", "twitter.com"])

    # For unknown apps, do not guess a random favicon domain. A wrong logo
    # is worse than skipping the poster.
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


def _fit_logo_to_square(logo_bytes: bytes, size: int = 430):
    icon = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    icon.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    x = (size - icon.width) // 2
    y = (size - icon.height) // 2
    canvas.alpha_composite(icon, (x, y))
    return canvas


def _draw_centered(draw, text, y, font, width, fill=(255, 255, 255, 255)):
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _make_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        c = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, w, y), fill=c)
    return img.convert("RGBA")


def create_branded_poster(app_name: str, logo_bytes: bytes, variant: int = 0) -> bytes:
    'Create one of several branded poster layouts. The layout changes per APK.'
    global POSTER_COUNTER
    W, H = 1080, 1080
    clean_name = (app_name or "APK Application").strip()
    if len(clean_name) > 28:
        clean_name = clean_name[:28].rstrip() + "…"

    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    f_brand = _font(font_bold, 52)
    f_sub = _font(font_regular, 27)
    f_app = _font(font_bold, 61)
    f_small = _font(font_regular, 26)
    f_tag = _font(font_bold, 29)

    # Choose the layout from the APK/storage identity when available.
    # This keeps the exact same poster for the channel and landing page.
    layout = int(variant) % 6
    POSTER_COUNTER += 1

    palettes = [
        ((118, 10, 194), (20, 31, 150)),
        ((14, 104, 125), (24, 35, 113)),
        ((168, 28, 92), (48, 20, 132)),
        ((18, 104, 65), (19, 31, 111)),
        ((18, 70, 120), (40, 20, 105)),
        ((150, 52, 20), (64, 18, 92)),
    ]
    img = _make_gradient((W, H), *palettes[layout])
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    if layout == 0:
        for x, y, w, h in [(-40, 20, 220, 620), (110, -30, 170, 520), (820, -40, 180, 560), (950, 120, 190, 530), (-80, 690, 260, 500)]:
            od.polygon([(x, y), (x+w, y+40), (x+w//2, y+h), (x+w//3, y+h//3)], fill=(10, 5, 80, 120))
        od.ellipse((250, 160, 830, 740), fill=(230, 30, 255, 45))
    elif layout == 1:
        for r in (190, 300, 420, 540):
            od.ellipse((540-r, 540-r, 540+r, 540+r), outline=(255,255,255,35), width=5)
        od.rectangle((0, 0, W, 190), fill=(0, 0, 0, 55))
    elif layout == 2:
        for i in range(-300, 1300, 180):
            od.polygon([(i, 0), (i+120, 0), (i-180, H), (i-300, H)], fill=(255, 255, 255, 18))
        od.ellipse((100, 210, 980, 1090), fill=(0, 0, 0, 38))
    elif layout == 3:
        od.rounded_rectangle((55, 45, W-55, H-45), radius=55, outline=(255,255,255,55), width=3)
        for x, y, r in [(110,160,80),(930,170,120),(120,900,130),(930,900,90)]:
            od.ellipse((x-r,y-r,x+r,y+r), fill=(255,255,255,22))
    elif layout == 4:
        od.rectangle((0, 0, W, 170), fill=(0,0,0,65))
        od.rectangle((0, 880, W, H), fill=(0,0,0,80))
        for x in (90, 990):
            od.ellipse((x-180, 380, x+180, 740), fill=(255,255,255,18))
    else:
        od.polygon([(0, 0), (W, 0), (W, 360), (700, 0)], fill=(255,255,255,22))
        od.polygon([(0, H), (0, 760), (380, H)], fill=(0,0,0,55))
        od.rounded_rectangle((65, 65, W-65, H-65), radius=48, outline=(255,255,255,45), width=3)

    overlay = overlay.filter(ImageFilter.GaussianBlur(7))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    white = (255,255,255,255)
    muted = (235,225,255,235)

    _draw_centered(draw, "Anas APK System", 52, f_brand, W, white)
    _draw_centered(draw, "Android Applications & Downloads", 122, f_sub, W, muted)

    icon = _fit_logo_to_square(logo_bytes, 430)
    frame_x, frame_y, frame_s = 290, 215, 500
    shadow = Image.new("RGBA", (560,560), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((30,30,530,530), radius=82, fill=(0,0,0,130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    img.alpha_composite(shadow, (frame_x-30, frame_y-10))

    frame = Image.new("RGBA", (frame_s, frame_s), (255,255,255,255))
    mask = Image.new("L", (frame_s, frame_s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,frame_s-1,frame_s-1), radius=72, fill=255)
    frame.putalpha(mask)
    img.alpha_composite(frame, (frame_x, frame_y))
    img.alpha_composite(icon, (frame_x + 35, frame_y + 35))

    _draw_centered(draw, clean_name, 760, f_app, W, white)
    _draw_centered(draw, "Official app logo • Android APK", 835, f_small, W, muted)

    strip_y = 930
    if layout % 2 == 0:
        draw.rounded_rectangle((70, strip_y, W-70, 1000), radius=28, fill=(8,5,65,205), outline=(215,115,255,230), width=3)
        _draw_centered(draw, "★ Anas APK ★", 950, f_tag, W, white)
    else:
        draw.rounded_rectangle((70, strip_y, W-70, 1000), radius=28, fill=(10,12,35,175), outline=(255,255,255,175), width=2)
        _draw_centered(draw, "★ Anas APK ★", 950, f_tag, W, white)

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


async def make_dynamic_poster(app_name: str, variant: int = 0):
    'Fetch the matching app logo and generate one coherent branded poster.'
    logo = await fetch_online_app_logo(app_name)
    if not logo:
        return None
    try:
        poster = create_branded_poster(app_name, logo, variant=variant)
        STATS["logo_generated"] += 1
        return poster
    except Exception:
        logger.exception("Dynamic poster creation failed | app=%s", app_name)
        return None

# ============================================================
# PHOTO FINDER
# ============================================================

async def get_photo(event):
    """Return only a photo attached to this exact APK message.

    Do not inspect nearby messages: adjacent paid-promotion images can
    otherwise be incorrectly attached to an unrelated APK.
    """
    try:
        return event.photo if event.photo else None
    except Exception:
        logger.exception(
            "Photo read failed | chat_id=%s | message_id=%s",
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
    desc: str = "",
    storage_msg_id: int = None,
    poster_variant: int = 0
) -> str:
    info = parse_apk_name(filename)

    lines = [
        f"📱 <b>{html_escape(info['full_display'])}</b>"
    ]

    if info["version"]:
        lines.append(f"🔖 <b>Version:</b> {html_escape(info['version'])}")

    lines.append(f"📦 <b>File:</b> <code>{html_escape(filename)}</code>")
    lines.append("\n📝 <b>Clean APK release post</b>")

    if storage_msg_id and storage_msg_id > 0:
        download_url = (
            f"{PUBLIC_BASE_URL}/download/{storage_msg_id}"
            f"?name={quote(info['clean_name'])}"
            f"&version={quote(info['version'] or 'Latest')}"
            f"&file={quote(filename)}"
            f"&variant={int(poster_variant) % 6}"
        )
        lines.append(
            f"\n⬇️ <b><a href=\"{download_url}\">Download APK</a></b>"
        )
    else:
        lines.append("\n⚠️ Download link is temporarily unavailable.")

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

                # Change queue posting interval from Saved Messages: /post 30
                post_match = re.fullmatch(r"/post(?:\s+(\d{1,4}))?", command)
                if post_match:
                    global POST_INTERVAL_MINUTES
                    if post_match.group(1) is None:
                        await event.reply(
                            f"⏱️ Current posting interval: <b>{POST_INTERVAL_MINUTES} minutes</b>\\n"
                            "Change it by sending <code>/post 30</code> or <code>/post 15</code> in Saved Messages.",
                            parse_mode="html"
                        )
                    else:
                        minutes = int(post_match.group(1))
                        if not 1 <= minutes <= 1440:
                            await event.reply(
                                "⚠️ Minutes must be between 1 and 1440. Example: <code>/post 30</code>",
                                parse_mode="html"
                            )
                        else:
                            POST_INTERVAL_MINUTES = minutes
                            await event.reply(
                                f"✅ Posting interval changed to <b>{POST_INTERVAL_MINUTES} minutes</b>.\\n"
                                "This applies to the next queue wait. It resets to 30 minutes after a Render restart.",
                                parse_mode="html"
                            )
                    return

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
        source_content = (filename + " " + text).lower()

        if any(
            keyword in source_content
            for keyword in GAMBLING_KEYWORDS
        ) or any(
            keyword in source_content
            for keyword in BLOCKED_PROMO_TERMS
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

        # Always create our own branded poster from the app logo.
        # Source-channel photos are intentionally ignored so unrelated
        # images never get attached to the wrong APK.
        info = parse_apk_name(filename)
        online_logo = await fetch_online_app_logo(info["clean_name"])

        photo = None
        if online_logo is not None:
            try:
                photo = create_branded_poster(
                    info["clean_name"],
                    online_logo,
                    variant=sum((i + 1) * ord(ch) for i, ch in enumerate(filename)) % 6
                )
                STATS["logo_generated"] += 1
                logger.info(
                    "🖼️ Dynamic branded poster created: %s",
                    info["clean_name"]
                )
            except Exception:
                logger.exception("Dynamic poster creation failed; posting without image")
                photo = None
        else:
            logger.warning(
                "📝 No matching logo found; APK will be posted without image | app=%s | filename=%s",
                info["clean_name"],
                filename
            )

        # Do not republish source captions, external links, or join-channel promotions.
        clean_desc = ""

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

            _poster_cache_put(storage_msg_id, photo)

            poster_variant = sum((i + 1) * ord(ch) for i, ch in enumerate(filename)) % 6
            final_caption = build_caption(
                filename,
                clean_desc,
                storage_msg_id,
                poster_variant=poster_variant
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
            "poster_variant": sum((i + 1) * ord(ch) for i, ch in enumerate(filename)) % 6,
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
            _poster_cache_put(storage_msg_id, item["photo"])

            poster_variant = item.get("poster_variant", sum((i + 1) * ord(ch) for i, ch in enumerate(filename)) % 6)
            final_caption = build_caption(
                filename,
                item["clean_desc"],
                storage_msg_id,
                poster_variant=poster_variant
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

            # Configurable gap between queue items (default remains 30 minutes).
            await asyncio.sleep(POST_INTERVAL_MINUTES * 60)

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
    logger.info("⏱️ Posting interval: %s minutes (Saved Messages: /post <minutes>)", POST_INTERVAL_MINUTES)
    logger.info("========================================")

    asyncio.create_task(worker())

    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
