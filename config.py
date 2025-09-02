# config.py

import random
import logging
import asyncio
import aiohttp
from core.settings import settings

logger = logging.getLogger(__name__)

# ================== سیستم مدیریت و اعتبارسنجی پراکسی (نسخه حرفه‌ای) ==================

# --- FIX: لیستی از بهترین منابع عمومی برای دریافت پراکسی ---
# این لیست شامل منابع معتبری است که به طور منظم به‌روزرسانی می‌شوند.
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

RAW_PROXIES: set[str] = set() # استفاده از set برای حذف خودکار موارد تکراری
VALIDATED_PROXIES: list[str] = []
VALIDATION_LOCK = asyncio.Lock()

# --- تنظیمات قابل تغییر برای بهینه‌سازی ---
TEST_URL = 'https://api.google.com'
MAX_CONCURRENT_TESTS = 500
TEST_TIMEOUT = 3
REVALIDATION_THRESHOLD = 20
INITIAL_QUICK_TEST_COUNT = 100

async def _fetch_proxies_from_url(session: aiohttp.ClientSession, url: str) -> set[str]:
    """پراکسی‌ها را از یک URL مشخص به صورت غیرهمزمان دریافت می‌کند."""
    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                text = await response.text()
                # پراکسی‌ها را تمیز کرده و به فرمت http://ip:port در می‌آورد
                return {f"http://{p.strip()}" for p in text.splitlines() if p.strip()}
            else:
                logger.warning(f"Failed to fetch proxies from {url}, status code: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching proxies from {url}: {e}")
    return set()

async def test_proxy(session: aiohttp.ClientSession, proxy: str) -> str | None:
    """یک پراکسی را به صورت غیرهمزمان تست می‌کند."""
    try:
        async with session.get(TEST_URL, proxy=proxy, timeout=TEST_TIMEOUT) as response:
            if response.status < 500: # هر پاسخی غیر از خطای سرور به معنی کار کردن پراکسی است
                return proxy
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass # خطاهای معمول شبکه و تایم‌اوت را نادیده بگیر
    except Exception as e:
        logger.debug(f"Unexpected error while testing proxy {proxy}: {e}")
    return None

async def update_and_test_proxies():
    """
    لیست پراکسی‌ها را از چندین منبع آپدیت و اعتبارسنجی می‌کند.
    """
    global RAW_PROXIES, VALIDATED_PROXIES
    
    if VALIDATION_LOCK.locked():
        logger.info("Proxy validation is already in progress. Skipping.")
        return

    async with VALIDATION_LOCK:
        logger.info("Starting proxy update and validation process from multiple sources...")

        # --- FIX: دریافت همزمان پراکسی‌ها از تمام منابع ---
        async with aiohttp.ClientSession() as session:
            tasks = [_fetch_proxies_from_url(session, url) for url in PROXY_SOURCES]
            results = await asyncio.gather(*tasks)
        
        # ادغام تمام پراکسی‌های دریافت شده در یک مجموعه (set) برای حذف تکراری‌ها
        RAW_PROXIES = set.union(*results)
        
        if not RAW_PROXIES:
            logger.error("Could not fetch any proxies from any source. Proxy system will be inactive.")
            VALIDATED_PROXIES = []
            return
            
        logger.info(f"Fetched {len(RAW_PROXIES)} unique raw proxies from {len(PROXY_SOURCES)} sources.")

        # پراکسی‌ها را به لیست تبدیل کرده و به صورت تصادفی مرتب می‌کنیم
        proxy_list = list(RAW_PROXIES)
        random.shuffle(proxy_list)

        logger.info(f"Starting initial quick test on {INITIAL_QUICK_TEST_COUNT} random proxies...")
        quick_test_proxies = proxy_list[:INITIAL_QUICK_TEST_COUNT]
        
        async with aiohttp.ClientSession() as session:
            tasks = [test_proxy(session, proxy) for proxy in quick_test_proxies]
            results = await asyncio.gather(*tasks)
            initial_proxies = [res for res in results if res]
        
        if initial_proxies:
            VALIDATED_PROXIES = initial_proxies
            logger.info(f"Quick test complete. Found {len(VALIDATED_PROXIES)} initial working proxies. Bot is ready.")
        else:
            logger.warning("Quick test found no working proxies. Starting full scan immediately.")

        logger.info("Continuing with full validation in the background...")
        full_validated = list(VALIDATED_PROXIES)
        remaining_proxies = proxy_list[INITIAL_QUICK_TEST_COUNT:]
        
        async with aiohttp.ClientSession() as session:
            tasks = [test_proxy(session, proxy) for proxy in remaining_proxies]
            for i in range(0, len(tasks), MAX_CONCURRENT_TESTS):
                batch = tasks[i:i + MAX_CONCURRENT_TESTS]
                results = await asyncio.gather(*batch)
                full_validated.extend([res for res in results if res])
                logger.debug(f"Background validation progress: Total valid proxies so far: {len(full_validated)}")

        if full_validated:
            logger.info(f"Full validation complete. Total working proxies: {len(full_validated)}.")
            VALIDATED_PROXIES = full_validated
        else:
            logger.warning("Full validation could not find any working proxies.")
            VALIDATED_PROXIES = []


def get_random_proxy() -> str | None:
    """یک پراکسی شانسی از لیست معتبر برمی‌گرداند."""
    if VALIDATED_PROXIES:
        return random.choice(VALIDATED_PROXIES)
    return None

def handle_proxy_failure(failed_proxy: str):
    """یک پراکسی خراب را از لیست حذف کرده و در صورت نیاز، تست مجدد را فعال می‌کند."""
    global VALIDATED_PROXIES
    if failed_proxy in VALIDATED_PROXIES:
        VALIDATED_PROXIES.remove(failed_proxy)
        logger.warning(f"Removed failed proxy. Remaining valid proxies: {len(VALIDATED_PROXIES)}")

        if len(VALIDATED_PROXIES) < REVALIDATION_THRESHOLD and not VALIDATION_LOCK.locked():
            logger.warning("Proxy count below threshold. Triggering re-validation.")
            asyncio.create_task(update_and_test_proxies())