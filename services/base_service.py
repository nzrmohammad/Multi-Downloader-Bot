# services/base_service.py

import logging
from typing import Any, Dict
import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes
import config
from core.settings import settings
from yt_dlp.utils import DownloadError

logger = logging.getLogger(__name__)

class BaseService:
    """
    کلاس پایه انتزاعی برای تمام سرویس‌های دانلود.
    هر سرویس جدید باید از این کلاس ارث‌بری کرده و متدهای آن را پیاده‌سازی کند.
    """
    async def can_handle(self, url: str) -> bool:
        """بررسی می‌کند که آیا این سرویس می‌تواند URL داده شده را پردازش کند."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """درخواست کاربر را پردازش کرده و گزینه‌های دانلود را ارائه می‌دهد."""
        raise NotImplementedError("This method must be implemented by a subclass.")

    async def _extract_info_ydl(self, url: str, ydl_opts: Dict[str, Any] = None) -> Dict[str, Any] | None:
        """
        یک متد کمکی برای استخراج اطلاعات با استفاده از yt-dlp.
        این متد پراکسی و مدیریت خطای پایه را به صورت خودکار با ۳ بار تلاش مجدد انجام می‌دهد.
        """
        max_retries = 3
        for attempt in range(max_retries):
            proxy = config.get_random_proxy()
            try:
                default_opts = {
                    'quiet': True,
                    'noplaylist': True,
                    'nocheckcertificate': True,
                    'proxy': proxy,
                }

                # FIX: Add cookie file to yt-dlp options if it exists
                if settings.YOUTUBE_COOKIES_FILE and "youtube.com" in url:
                    default_opts['cookiefile'] = settings.YOUTUBE_COOKIES_FILE
                    logger.info("Using YouTube cookies file for extraction.")

                if ydl_opts:
                    default_opts.update(ydl_opts)

                with yt_dlp.YoutubeDL(default_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                return info

            except DownloadError as e:
                # FIX: Report the failed proxy to the smart handler
                if proxy and 'proxy' in str(e).lower():
                    config.handle_proxy_failure(proxy)
                    logger.warning(f"Proxy error on attempt {attempt + 1}/{max_retries} for URL {url}.")
                    if attempt < max_retries - 1:
                        continue
                
                logger.warning(f"yt-dlp DownloadError for URL {url}: {e}")
                return None
            except Exception as e:
                if proxy:
                    config.handle_proxy_failure(proxy)
                logger.error(f"Generic error in _extract_info_ydl for URL {url} on attempt {attempt + 1}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    continue
        
        logger.error(f"Failed to extract info for {url} after {max_retries} attempts.")
        return None