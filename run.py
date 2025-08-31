# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/run.py

import logging
import asyncio
from logging.handlers import RotatingFileHandler
import uvloop  # <--- افزودن uvloop

from bot.application import create_application
from bot.handlers import register_handlers
from database import database
from core.handlers.service_manager import initialize_services
from core.scheduler import setup_scheduler
import config

# --- نصب uvloop برای عملکرد بهتر asyncio ---
uvloop.install()

# --- تنظیمات لاگ (کلاس ContextFilter و بقیه کدها بدون تغییر) ---
class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'user_id'):
            record.user_id = 'SYSTEM'
        if not hasattr(record, 'message_id'):
            record.message_id = 'N/A'
        return True

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s - [user_id:%(user_id)s] - [message_id:%(message_id)s]')
file_handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.addFilter(ContextFilter())
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.addFilter(ContextFilter())
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


async def main() -> None:
    """ربات را به صورت غیرهمزمان راه‌اندازی و اجرا می‌کند."""

    # --- آماده‌سازی اولیه پایگاه داده ---
    logger.info("Initializing database...")
    await database.create_db()

    # --- ثبت سرویس‌ها در پایگاه داده ---
    logger.info("Initializing services in database...")
    await initialize_services()

    # --- به‌روزرسانی پراکسی‌ها ---
    config.update_proxies_from_source()

    # --- ساخت اپلیکیشن و ثبت هندلرها ---
    application = create_application()
    register_handlers(application)

    # --- اجرای ربات و زمان‌بند در یک حلقه asyncio ---
    logger.info("Starting bot polling with uvloop...")
    async with application:
        await application.start()
        await application.updater.start_polling()

        scheduler = setup_scheduler(application)
        scheduler.add_job(config.update_proxies_from_source, 'interval', minutes=60)
        logger.info("Proxy update job scheduled.")

        # این حلقه بی‌نهایت، اسکریپت را تا زمان توقف دستی (Ctrl+C) زنده نگه می‌دارد
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")