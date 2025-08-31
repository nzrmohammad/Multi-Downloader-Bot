# config.py

import random
import logging
import requests
import asyncio
import aiohttp
from core.settings import settings

logger = logging.getLogger(__name__)

# ================== سیستم مدیریت و اعتبارسنجی پراکسی ==================

RAW_PROXIES: list[str] = []
VALIDATED_PROXIES: list[str] = []
VALIDATION_LOCK = asyncio.Lock()

# --- تنظیمات قابل تغییر برای بهینه‌سازی ---
TEST_URL = 'https://api.google.com'
MAX_CONCURRENT_TESTS = 500
TEST_TIMEOUT = 3
REVALIDATION_THRESHOLD = 20
INITIAL_QUICK_TEST_COUNT = 100

async def test_proxy(session: aiohttp.ClientSession, proxy: str) -> str | None:
    """یک پراکسی را به صورت غیرهمزمان تست می‌کند."""
    try:
        async with session.get(TEST_URL, proxy=proxy, timeout=TEST_TIMEOUT) as response:
            if response.status < 500:
                return proxy
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.debug(f"Unexpected error while testing proxy {proxy}: {e}")
    return None

async def update_and_test_proxies():
    """
    لیست پراکسی‌ها را آپدیت و اعتبارسنجی می‌کند.
    """
    global RAW_PROXIES, VALIDATED_PROXIES
    
    if VALIDATION_LOCK.locked():
        logger.info("Proxy validation is already in progress. Skipping.")
        return

    async with VALIDATION_LOCK:
        logger.info("Starting proxy update and validation process...")
        if not settings.PROXY_SOURCE_URL:
            logger.warning("PROXY_SOURCE_URL not set. Proxy system disabled.")
            VALIDATED_PROXIES = []
            return

        try:
            response = requests.get(settings.PROXY_SOURCE_URL, timeout=15)
            response.raise_for_status()
            proxies_from_url = [f"http://{p.strip()}" for p in response.text.splitlines() if p.strip()]
            
            if not proxies_from_url:
                logger.warning("Proxy source returned an empty list.")
                return
            
            random.shuffle(proxies_from_url)
            RAW_PROXIES = proxies_from_url
            logger.info(f"Fetched {len(RAW_PROXIES)} raw proxies.")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch proxies: {e}")
            return

        logger.info(f"Starting initial quick test on {INITIAL_QUICK_TEST_COUNT} random proxies...")
        quick_test_proxies = RAW_PROXIES[:INITIAL_QUICK_TEST_COUNT]
        
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
        remaining_proxies = RAW_PROXIES[INITIAL_QUICK_TEST_COUNT:]
        
        async with aiohttp.ClientSession() as session:
            tasks = [test_proxy(session, proxy) for proxy in remaining_proxies]
            for i in range(0, len(tasks), MAX_CONCURRENT_TESTS):
                batch = tasks[i:i + MAX_CONCURRENT_TESTS]
                results = await asyncio.gather(*batch)
                full_validated.extend([res for res in results if res])
                # این لاگ دیگر در حالت INFO نمایش داده نمی‌شود
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