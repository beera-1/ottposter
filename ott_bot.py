import os
import logging
import requests
import pytesseract
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
from flask import Flask, request
import threading

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "6390511215"))
BASE_URL = os.getenv("BASE_URL", "https://vague-emylee-fdep1-e666aa0a.koyeb.app")
PORT = int(os.getenv("PORT", 8080))
AUTHORIZED_USERS = [OWNER_ID]

# ---------------- Logging ----------------
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ---------------- Flask App for Health Check ----------------
app = Flask(__name__)

@app.route('/')
def index():
    return '✅ Bot is running.'

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    updater.bot.set_webhook()
    updater.update_queue.put(Update.de_json(request.get_json(force=True), updater.bot))
    return 'ok'

# ---------------- OCR Filter ----------------
def is_text_present(img_url):
    try:
        resp = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert('RGB')
        text = pytesseract.image_to_string(img)
        return bool(text.strip())
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        return False

# ---------------- Selenium Setup ----------------
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/chromium"
    return webdriver.Chrome(executable_path="/usr/bin/chromedriver", options=options)

# ---------------- Scraper Logic ----------------
def scrape_platform(name, url, lang="Multi"):
    posters = []
    try:
        driver = get_driver()
        driver.get(url)
        driver.implicitly_wait(5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and src.startswith("http") and "webp" not in src and is_text_present(src):
                posters.append(src)
            if len(posters) >= 3:
                break
        return {
            "title": f"{name} Title",
            "year": "2025",
            "language": lang,
            "Poster": posters[0] if len(posters) > 0 else "",
            "Portrait": posters[1] if len(posters) > 1 else "",
            "Cover": posters[2] if len(posters) > 2 else "",
        }
    except Exception as e:
        logging.error(f"{name} scraping failed: {e}")
        return {
            "title": f"{name} Error",
            "year": "N/A",
            "language": lang,
            "Poster": "",
            "Portrait": "",
            "Cover": "",
        }

# ---------------- Format Output ----------------
def format_message(title, year, language, posters):
    msg = f"🎬 <b>{title}</b> ({year}) [{language}]\n\n"
    if posters.get("Poster"):
        msg += f"🖼 <b>Poster</b>: {posters['Poster']}\n"
    if posters.get("Portrait"):
        msg += f"📱 <b>Portrait</b>: {posters['Portrait']}\n"
    if posters.get("Cover"):
        msg += f"🖼 <b>Cover</b>: {posters['Cover']}\n"
    msg += "\n🚀 Powered by @PBX1_BOTS"
    return msg

# ---------------- Platform Scrapers ----------------
def scrape_netflix():     return scrape_platform("Netflix",    "https://www.netflix.com/in/browse/genre/34399")
def scrape_prime():       return scrape_platform("Prime Video","https://www.primevideo.com/storefront/home")
def scrape_zee5():        return scrape_platform("ZEE5",       "https://www.zee5.com/movies", "Hindi")
def scrape_hotstar():     return scrape_platform("Hotstar",    "https://www.hotstar.com/in/movies", "Hindi")
def scrape_jiocinema():   return scrape_platform("JioCinema",  "https://www.jiocinema.com/movies", "Hindi")
def scrape_mx():          return scrape_platform("MX Player",  "https://www.mxplayer.in/movies", "Hindi")
def scrape_chaupal():     return scrape_platform("Chaupal",    "https://www.chaupal.tv/movies", "Punjabi")
def scrape_crunchyroll(): return scrape_platform("Crunchyroll","https://www.crunchyroll.com/videos/anime", "Japanese")

# ---------------- Authorization ----------------
def is_authorized(uid): return uid in AUTHORIZED_USERS

def authorize(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return update.message.reply_text("🚫 Owner only.")
    try:
        uid = int(context.args[0])
        if uid not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(uid)
            update.message.reply_text(f"✅ Authorized {uid}")
        else:
            update.message.reply_text("⚠️ Already authorized.")
    except:
        update.message.reply_text("❗ Usage: /authorize <user_id>")

def unauthorize(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return update.message.reply_text("🚫 Owner only.")
    try:
        uid = int(context.args[0])
        if uid in AUTHORIZED_USERS:
            AUTHORIZED_USERS.remove(uid)
            update.message.reply_text(f"🚫 Revoked {uid}")
        else:
            update.message.reply_text("❌ Not authorized.")
    except:
        update.message.reply_text("❗ Usage: /unauthorize <user_id>")

def authlist(update: Update, context: CallbackContext):
    users = "\n".join(map(str, AUTHORIZED_USERS))
    update.message.reply_text(f"🔐 Authorized users:\n{users}")

def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return update.message.reply_text("🚫 Owner only.")
    update.message.reply_text(f"📊 Authorized users: {len(AUTHORIZED_USERS)}")

# ---------------- Command Handlers ----------------
def handle_platform(update: Update, context: CallbackContext, scraper):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    data = scraper()
    if not any([data.get("Poster"), data.get("Portrait"), data.get("Cover")]):
        return update.message.reply_text("❌ No posters found.")
    msg = format_message(data['title'], data['year'], data['language'], data)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)

def scrape_links(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    urls = context.args
    if not urls:
        return update.message.reply_text("❗ Usage: /scrape <link1> <link2>")
    out = "🧩 Extracted Links:\n"
    count = 0
    for url in urls:
        if any(x in url for x in ["gofile", "hubcloud", "pixeldrain", "gdflix"]):
            out += f"✅ <code>{url}</code>\n"
            count += 1
    if count == 0:
        return update.message.reply_text("❌ No valid links found.")
    update.message.reply_text(out, parse_mode="HTML")

# ---------------- Run Bot ----------------
def main():
    global updater
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    platform_cmds = {
        "netflix": scrape_netflix,
        "prime": scrape_prime,
        "zee5": scrape_zee5,
        "hotstar": scrape_hotstar,
        "jiocinema": scrape_jiocinema,
        "mx": scrape_mx,
        "chaupal": scrape_chaupal,
        "crunchyroll": scrape_crunchyroll,
    }

    for cmd, func in platform_cmds.items():
        dp.add_handler(CommandHandler(cmd, lambda u, c, f=func: handle_platform(u, c, f)))

    dp.add_handler(CommandHandler("scrape", scrape_links))
    dp.add_handler(CommandHandler("authorize", authorize))
    dp.add_handler(CommandHandler("unauthorize", unauthorize))
    dp.add_handler(CommandHandler("authlist", authlist))
    dp.add_handler(CommandHandler("stats", stats))

    # Start webhook
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"https://vague-emylee-fdep1-e666aa0a.koyeb.app/7291110510:AAFhV1JZBF-jQK-X96dwUkEGbxoeYl8yd3M"
    )

    updater.idle()

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    main()
