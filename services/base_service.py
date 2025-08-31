# services/base_service.py

import logging
from typing import Any, Dict
import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes
import config

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
        این متد پراکسی و مدیریت خطای پایه را به صورت خودکار انجام می‌دهد.
        """
        # تنظیمات پیش‌فرض yt-dlp
        default_opts = {
            'quiet': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'proxy': config.get_random_proxy(),
        }
        
        # ادغام تنظیمات پیش‌فرض با تنظیمات ورودی
        if ydl_opts:
            default_opts.update(ydl_opts)

        try:
            with yt_dlp.YoutubeDL(default_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info
        except yt_dlp.utils.DownloadError as e:
            # این خطاها معمولا به دلیل مشکلات لینک (خصوصی بودن، حذف شدن) است
            logger.warning(f"yt-dlp DownloadError for URL {url}: {e}")
            return None
        except Exception as e:
            # خطاهای دیگر ممکن است مربوط به شبکه یا پراکسی باشند
            logger.error(f"Generic error in _extract_info_ydl for URL {url}: {e}", exc_info=True)
            return None