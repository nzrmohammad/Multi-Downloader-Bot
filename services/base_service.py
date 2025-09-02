# services/base_service.py

import logging
from typing import Any, Dict
import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes
import config
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
        این متد پراکسی را به صورت خودکار انجام می‌دهد.
        """
        proxy = config.get_random_proxy()
        try:
            default_opts = {
                'quiet': True,
                'noplaylist': True,
                'nocheckcertificate': True,
                'proxy': proxy,
            }

            if ydl_opts:
                default_opts.update(ydl_opts)

            with yt_dlp.YoutubeDL(default_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info

        except DownloadError as e:
            if proxy and 'proxy' in str(e).lower():
                config.handle_proxy_failure(proxy)
            logger.warning(f"yt-dlp DownloadError for URL {url}: {e}")
            return None
        except Exception as e:
            if proxy:
                config.handle_proxy_failure(proxy)
            logger.error(f"Generic error in _extract_info_ydl for URL {url}: {e}", exc_info=True)
            return None