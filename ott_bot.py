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

# ---------------- Bot Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "6390511215"))
AUTHORIZED_USERS = [OWNER_ID]

# ---------------- Logging ----------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ---------------- OCR Filter ----------------
def is_text_present(img_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(img_url, headers=headers, timeout=10)
        img = Image.open(BytesIO(response.content)).convert('RGB')
        text = pytesseract.image_to_string(img)
        return bool(text.strip())
    except Exception as e:
        logging.error(f"OCR Error: {e}")
        return False

# ---------------- Selenium Setup ----------------
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/usr/bin/chromium"
    return webdriver.Chrome(executable_path="/usr/bin/chromedriver", options=chrome_options)

# ---------------- Output Format ----------------
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

# ---------------- Scraper Template ----------------
def scrape_platform(name, url, lang="Multi"):
    posters = []
    try:
        driver = get_driver()
        driver.get(url)
        driver.implicitly_wait(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('http') and 'webp' not in src:
                if is_text_present(src):
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

# ---------------- Platform Scrapers ----------------
def scrape_netflix(): return scrape_platform("Netflix", "https://www.netflix.com/in/browse/genre/34399")
def scrape_prime(): return scrape_platform("Prime Video", "https://www.primevideo.com/storefront/home")
def scrape_zee5(): return scrape_platform("ZEE5", "https://www.zee5.com/movies", "Hindi")
def scrape_hotstar(): return scrape_platform("Hotstar", "https://www.hotstar.com/in/movies", "Hindi")
def scrape_jiocinema(): return scrape_platform("JioCinema", "https://www.jiocinema.com/movies", "Hindi")
def scrape_mx(): return scrape_platform("MX Player", "https://www.mxplayer.in/movies", "Hindi")
def scrape_chaupal(): return scrape_platform("Chaupal", "https://www.chaupal.tv/movies", "Punjabi")
def scrape_crunchyroll(): return scrape_platform("Crunchyroll", "https://www.crunchyroll.com/videos/anime", "Japanese")

# ---------------- Authorization System ----------------
def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

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

# ---------------- Scrape Handler ----------------
def scrape(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    links = context.args
    if not links:
        return update.message.reply_text("❗ Usage: /scrape <link1> <link2>")
    output = "🧩 Extracted Links:\n"
    valid = 0
    for url in links:
        if any(x in url for x in ["gofile", "hubcloud", "pixeldrain", "gdflix"]):
            output += f"✅ <code>{url}</code>\n"
            valid += 1
    if valid == 0:
        update.message.reply_text("❌ No valid links found.")
    else:
        update.message.reply_text(output, parse_mode="HTML")

# ---------------- Telegram Platform Handlers ----------------
def handle_platform(update: Update, context: CallbackContext, scraper_func):
    if not is_authorized(update.effective_user.id):
        return update.message.reply_text("🚫 Unauthorized user.")
    try:
        data = scraper_func()
        if not any([data.get("Poster"), data.get("Portrait"), data.get("Cover")]):
            update.message.reply_text("❌ No posters with text found.")
            return
        msg = format_message(data['title'], data['year'], data['language'], data)
        update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    except Exception as e:
        logging.error(f"Bot error: {e}")
        update.message.reply_text("❌ Failed to fetch posters. Try again later.")

# Bot Command Functions
def netflix(update: Update, context: CallbackContext): handle_platform(update, context, scrape_netflix)
def prime(update: Update, context: CallbackContext): handle_platform(update, context, scrape_prime)
def zee5(update: Update, context: CallbackContext): handle_platform(update, context, scrape_zee5)
def hotstar(update: Update, context: CallbackContext): handle_platform(update, context, scrape_hotstar)
def jiocinema(update: Update, context: CallbackContext): handle_platform(update, context, scrape_jiocinema)
def mx(update: Update, context: CallbackContext): handle_platform(update, context, scrape_mx)
def chaupal(update: Update, context: CallbackContext): handle_platform(update, context, scrape_chaupal)
def crunchyroll(update: Update, context: CallbackContext): handle_platform(update, context, scrape_crunchyroll)

# ---------------- Bot Start ----------------
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("netflix", netflix))
    dp.add_handler(CommandHandler("prime", prime))
    dp.add_handler(CommandHandler("zee5", zee5))
    dp.add_handler(CommandHandler("hotstar", hotstar))
    dp.add_handler(CommandHandler("jiocinema", jiocinema))
    dp.add_handler(CommandHandler("mx", mx))
    dp.add_handler(CommandHandler("chaupal", chaupal))
    dp.add_handler(CommandHandler("crunchyroll", crunchyroll))

    dp.add_handler(CommandHandler("scrape", scrape))
    dp.add_handler(CommandHandler("authorize", authorize))
    dp.add_handler(CommandHandler("unauthorize", unauthorize))
    dp.add_handler(CommandHandler("authlist", authlist))
    dp.add_handler(CommandHandler("stats", stats))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
