import os
import random
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Telegram configurations
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
SENSITIVE_SERVICES = os.getenv("SENSITIVE_SERVICES", "").split(',')
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID")) if os.getenv("LOG_CHANNEL_ID") else None

# Spotify API configurations
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# Twitter Auth Cookie
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN")

# --- Genius API Configuration Re-added ---
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")


# ================== سیستم مدیریت پراکسی اتوماتیک ==================

PROXY_SOURCE_URL = os.getenv("PROXY_SOURCE_URL")
PROXIES = [] # این لیست در حافظه نگهداری و به صورت دوره‌ای آپدیت می‌شود

def update_proxies_from_source():
    """
    لیست پراکسی‌ها را از منبع آنلاین می‌خواند و لیست داخلی را آپدیت می‌کند.
    """
    global PROXIES
    if not PROXY_SOURCE_URL:
        logger.warning("PROXY_SOURCE_URL is not set in .env file. Proxy system is disabled.")
        PROXIES = []
        return

    try:
        logger.info(f"Attempting to update proxies from: {PROXY_SOURCE_URL}")
        response = requests.get(PROXY_SOURCE_URL, timeout=15)
        response.raise_for_status()
        
        # پراکسی‌ها را از متن پاسخ استخراج و پیشوند http:// را به آن‌ها اضافه می‌کنیم
        proxies_from_url = [f"http://{p.strip()}" for p in response.text.splitlines() if p.strip()]
        
        if proxies_from_url:
            PROXIES = proxies_from_url
            logger.info(f"Successfully updated {len(PROXIES)} proxies.")
        else:
            # اگر لیست خالی بود، لیست قبلی را نگه می‌داریم تا ربات متوقف نشود
            logger.warning("Proxy source URL returned an empty list. Keeping the old list of proxies.")

    except requests.RequestException as e:
        logger.error(f"Failed to fetch proxies from source URL: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during proxy update: {e}")

def get_random_proxy():
    """
    یک پراکسی به صورت شانسی از لیست فعال برمی‌گرداند.
    """
    if PROXIES:
        return random.choice(PROXIES)
    return None

# ======================================================================


# Validate essential configurations
if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN and ADMIN_ID must be set in the .env file!")
if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set!")
if not GENIUS_ACCESS_TOKEN:
    raise ValueError("GENIUS_ACCESS_TOKEN must be set!")