# config.py

import random
import logging
import requests
from core.settings import settings # <--- وارد کردن از کلاس تنظیمات جدید

logger = logging.getLogger(__name__)

# ================== سیستم مدیریت پراکسی اتوماتیک ==================

PROXIES: list[str] = [] # این لیست در حافظه نگهداری و به صورت دوره‌ای آپدیت می‌شود

def update_proxies_from_source():
    """
    لیست پراکسی‌ها را از منبع آنلاین می‌خواند و لیست داخلی را آپدیت می‌کند.
    """
    global PROXIES
    if not settings.PROXY_SOURCE_URL:
        logger.warning("PROXY_SOURCE_URL is not set. Proxy system is disabled.")
        PROXIES = []
        return

    try:
        logger.info(f"Attempting to update proxies from: {settings.PROXY_SOURCE_URL}")
        response = requests.get(settings.PROXY_SOURCE_URL, timeout=15)
        response.raise_for_status()
        
        proxies_from_url = [f"http://{p.strip()}" for p in response.text.splitlines() if p.strip()]
        
        if proxies_from_url:
            PROXIES = proxies_from_url
            logger.info(f"Successfully updated {len(PROXIES)} proxies.")
        else:
            logger.warning("Proxy source URL returned an empty list. Keeping the old list of proxies.")

    except requests.RequestException as e:
        logger.error(f"Failed to fetch proxies from source URL: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during proxy update: {e}")

def get_random_proxy() -> str | None:
    """
    یک پراکسی به صورت شانسی از لیست فعال برمی‌گرداند.
    """
    if PROXIES:
        return random.choice(PROXIES)
    return None