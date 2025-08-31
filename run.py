# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/run.py

import logging
import asyncio
from logging.handlers import RotatingFileHandler
import uvloop

from bot.application import create_application
from bot.handlers import register_handlers
from database import database
from core.handlers.service_manager import initialize_services
from core.scheduler import setup_scheduler
import config

uvloop.install()

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

# FIX: Set noisy libraries to WARNING level to keep logs clean
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING) # This will hide the "Unclosed connection" error


async def main() -> None:
    """ربات را به صورت غیرهمزمان راه‌اندازی و اجرا می‌کند."""
    
    logger.info("Initializing database...")
    await database.create_db()
    
    logger.info("Initializing services in database...")
    await initialize_services()

    asyncio.create_task(config.update_and_test_proxies())

    application = create_application()
    register_handlers(application)
    
    logger.info("Starting bot polling with uvloop...")
    async with application:
        await application.start()
        await application.updater.start_polling()
        
        scheduler = setup_scheduler(application)
        scheduler.add_job(config.update_and_test_proxies, 'interval', hours=12)
        logger.info("Proxy update and validation job scheduled to run every 12 hours.")
        
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")