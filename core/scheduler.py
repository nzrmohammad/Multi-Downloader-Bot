# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/scheduler.py

import logging
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.database import AsyncSessionLocal
from core.handlers import user_manager

logger = logging.getLogger(__name__)

async def send_daily_report(application: Application):
    """گزارش روزانه را برای ادمین ارسال می‌کند و آمار کاربران را ریست می‌کند."""
    bot = application.bot
    extra_log_info = {'user_id': 'SCHEDULER'}
    
    # --- تهیه گزارش برای ادمین ---
    try:
        async with AsyncSessionLocal() as session:
            stats = await user_manager.get_bot_stats(session)
            
            admin_report = (
                f"📊 **گزارش روزانه ربات**\n\n"
                f"👤 **تعداد کل کاربران:** `{stats['total_users']}`\n"
                f"✨ **کاربران جدید امروز:** `{stats['new_users_today']}`\n"
                f"📥 **مجموع دانلودها (کل):** `{stats['total_downloads']}`\n\n"
                f"**تفکیک دانلودها بر اساس سرویس (کل):**\n"
            )
            
            service_stats = "\n".join(
                [f"▪️ **{s.capitalize()}:** `{c}`" for s, c in sorted(stats['service_counts'].items(), key=lambda item: item[1], reverse=True)]
            ) if stats['service_counts'] else "آماری ثبت نشده."
            
            admin_report += service_stats
        
        await bot.send_message(
            chat_id=bot.settings.ADMIN_ID, # <-- استفاده از تنظیمات
            text=admin_report,
            parse_mode='Markdown'
        )
        logger.info("گزارش روزانه با موفقیت برای ادمین ارسال شد.", extra=extra_log_info)

    except Exception as e:
        logger.error(f"خطا در ارسال گزارش برای ادمین: {e}", exc_info=True, extra=extra_log_info)

    # --- ریست کردن آمار روزانه کاربران ---
    async with AsyncSessionLocal() as session:
        all_user_ids = await user_manager.get_all_user_ids(session)
        for user_id in all_user_ids:
            user = await user_manager.find_user_by_id(session, user_id)
            if user:
                # ریست کردن دانلود روزانه
                user.daily_downloads = 0
        await session.commit()
    
    logger.info("آمار دانلود روزانه تمام کاربران ریست شد.", extra=extra_log_info)


def setup_scheduler(application: Application):
    """زمان‌بند را برای اجرای وظایف روزانه تنظیم می‌کند."""
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    scheduler.add_job(send_daily_report, 'cron', hour=23, minute=59, args=[application])
    scheduler.start()
    logger.info("زمان‌بند (Scheduler) با موفقیت برای ساعت ۲۳:۵۹ تنظیم شد.")
    return scheduler