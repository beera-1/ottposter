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
from flask import Flask
import threading

# ---------------- Bot Config ----------------
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "YOUR_BOT_TOKEN_HERE")
OWNER_ID     = int(os.getenv("OWNER_ID", "123456789"))
AUTHORIZED_USERS = [OWNER_ID]

# ---------------- Logging ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------- OCR Filter ----------------
def is_text_present(img_url):
    try:
        resp = requests.get(img_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        img  = Image.open(BytesIO(resp.content)).convert('RGB')
        text = pytesseract.image_to_string(img)
        return bool(text.strip())
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        return False

# ---------------- Selenium Setup ----------------
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.binary_location = "/usr/bin/chromium"
    return webdriver.Chrome(executable_path="/usr/bin/chromedriver", options=opts)

# ---------------- Message Formatter ----------------
def format_message(title, year, lang, posters):
    msg = f"🎬 <b>{title}</b> ({year}) [{lang}]\n\n"
    if posters.get("Poster"):
        msg += f"🖼 <b>Poster</b>: {posters['Poster']}\n"
    if posters.get("Portrait"):
        msg += f"📱 <b>Portrait</b>: {posters['Portrait']}\n"
    if posters.get("Cover"):
        msg += f"🖼 <b>Cover</b>: {posters['Cover']}\n"
    msg += "\n🚀 Powered by @PBX1_BOTS"
    return msg

# ---------------- Generic Scraper ----------------
def scrape_platform(name, url, lang="Multi"):
    posters = []
    try:
        drv = get_driver()
        drv.get(url)
        drv.implicitly_wait(5)
        soup = BeautifulSoup(drv.page_source, 'html.parser')
        drv.quit()
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('http') and 'webp' not in src and is_text_present(src):
                posters.append(src)
            if len(posters) >= 3:
                break
        return {
            "title":   f"{name} Title",
            "year":    "2025",
            "language":lang,
            "Poster":  posters[0] if len(posters)>0 else "",
            "Portrait":posters[1] if len(posters)>1 else "",
            "Cover":   posters[2] if len(posters)>2 else "",
        }
    except Exception as e:
        logging.error(f"{name} scraping failed: {e}")
        return {"title":f"{name} Error","year":"N/A","language":lang,"Poster":"","Portrait":"","Cover":""}

# ---------------- Platform Functions ----------------
def scrape_netflix():    return scrape_platform("Netflix",    "https://www.netflix.com/in/browse/genre/34399")
def scrape_prime():      return scrape_platform("Prime Video","https://www.primevideo.com/storefront/home")
def scrape_zee5():       return scrape_platform("ZEE5",       "https://www.zee5.com/movies", "Hindi")
def scrape_hotstar():    return scrape_platform("Hotstar",    "https://www.hotstar.com/in/movies", "Hindi")
def scrape_jiocinema():  return scrape_platform("JioCinema",  "https://www.jiocinema.com/movies", "Hindi")
def scrape_mx():         return scrape_platform("MX Player",  "https://www.mxplayer.in/movies", "Hindi")
def scrape_chaupal():    return scrape_platform("Chaupal",    "https://www.chaupal.tv/movies", "Punjabi")
def scrape_crunchyroll():return scrape_platform("Crunchyroll","https://www.crunchyroll.com/videos/anime", "Japanese")

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

# ---------------- Scrape Links ----------------
def scrape_links(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    urls = context.args
    if not urls:
        return update.message.reply_text("❗ Usage: /scrape <link1> <link2> ...")
    out, cnt = "🧩 Extracted Links:\n", 0
    for url in urls:
        if any(x in url for x in ["gofile","hubcloud","pixeldrain","gdflix"]):
            out += f"✅ <code>{url}</code>\n"
            cnt+=1
    update.message.reply_text(out if cnt else "❌ No valid links found.", parse_mode="HTML")

# ---------------- Unified Handler ----------------
def handle_platform(update: Update, context: CallbackContext, fn):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    data = fn()
    if not any([data.get("Poster"), data.get("Portrait"), data.get("Cover")]):
        return update.message.reply_text("❌ No posters with text found.")
    msg = format_message(data['title'], data['year'], data['language'], data)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

# Map commands
cmds = {
  "netflix":    scrape_netflix,
  "prime":      scrape_prime,
  "zee5":       scrape_zee5,
  "hotstar":    scrape_hotstar,
  "jiocinema":  scrape_jiocinema,
  "mx":         scrape_mx,
  "chaupal":    scrape_chaupal,
  "crunchyroll":scrape_crunchyroll,
}

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Poster commands
    for cmd, fn in cmds.items():
        dp.add_handler(CommandHandler(cmd, lambda u,c, f=fn: handle_platform(u, c, f)))

    # Utility commands
    dp.add_handler(CommandHandler("scrape",     scrape_links))
    dp.add_handler(CommandHandler("authorize",  authorize))
    dp.add_handler(CommandHandler("unauthorize",unauthorize))
    dp.add_handler(CommandHandler("authlist",   authlist))
    dp.add_handler(CommandHandler("stats",      stats))

    updater.start_polling()
    updater.idle()

# ---------------- Dummy Flask Health Check ----------------
app = Flask(__name__)
@app.route("/")
def health():
    return "✅ Bot is running."

if __name__ == "__main__":
    # Start health-check server
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080, debug=False)
    ).start()
    # Start Telegram bot
    main()
