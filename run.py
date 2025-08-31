import logging
import asyncio
from logging.handlers import RotatingFileHandler

from bot.application import create_application
from bot.handlers import register_handlers
from database import database
from core.handlers.service_manager import initialize_services
from core.scheduler import setup_scheduler


# --- تنظیمات لاگ ---
class ContextFilter(logging.Filter):
    """یک فیلتر برای اضافه کردن اطلاعات اضافی مانند user_id به لاگ‌ها."""
    def filter(self, record):
        if not hasattr(record, 'user_id'):
            record.user_id = 'SYSTEM'
        return True

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s - [user_id:%(user_id)s]')

# File Handler
file_handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.addFilter(ContextFilter())

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.addFilter(ContextFilter())

# Root Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


async def main() -> None:
    """ربات را به صورت غیرهمزمان راه‌اندازی و اجرا می‌کند."""
    
    # --- آماده‌سازی اولیه ---
    database.create_db()
    initialize_services()

    # --- ساخت اپلیکیشن و ثبت هندلرها ---
    application = create_application()
    register_handlers(application)
    
    # --- اجرای ربات و زمان‌بند در یک حلقه asyncio ---
    async with application:
        # این دو خط، ربات و event loop آن را راه‌اندازی می‌کنند
        await application.start()
        await application.updater.start_polling()
        
        # اکنون که حلقه در حال اجراست، زمان‌بند را راه‌اندازی می‌کنیم
        setup_scheduler(application)
        
        # این حلقه بی‌نهایت باعث می‌شود برنامه اصلی تا ابد در حال اجرا بماند
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")