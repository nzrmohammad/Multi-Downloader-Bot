# core/scheduler.py

import logging
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from core import user_manager

logger = logging.getLogger(__name__)

async def send_daily_report(application: Application):
    """گزارش روزانه را برای ادمین و کاربران ارسال می‌کند."""
    bot = application.bot
    extra_log_info = {'user_id': 'SCHEDULER'}
    
    # --- تهیه گزارش برای ادمین ---
    try:
        stats = user_manager.get_bot_stats()
        admin_report = (
            f"📊 **گزارش روزانه ربات**\n\n"
            f"👥 **کاربران جدید امروز:** `{stats['new_users_today']}`\n"
            f"📥 **مجموع دانلودهای امروز:** `{stats['total_downloads']}`\n"
            f"👤 **تعداد کل کاربران:** `{stats['total_users']}`\n\n"
            f"**تفکیک دانلودها:**\n"
        )
        
        service_stats = "\n".join(
            [f"▪️ **{s.capitalize()}:** `{c}`" for s, c in stats['service_counts'].items()]
        ) if stats['service_counts'] else "آماری برای امروز ثبت نشده."
        
        admin_report += service_stats
        
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=admin_report,
            parse_mode='Markdown'
        )
        logger.info("گزارش روزانه با موفقیت برای ادمین ارسال شد.", extra=extra_log_info)

    except Exception as e:
        logger.error(f"خطا در ارسال گزارش برای ادمین: {e}", exc_info=True, extra=extra_log_info)

    # --- ارسال گزارش برای کاربران و ریست کردن آمار روزانه ---
    all_user_ids = user_manager.get_all_user_ids()
    for user_id in all_user_ids:
        try:
            user = user_manager.find_user_by_id(user_id)
            if user and user.daily_downloads > 0:
                user_report = f"📊 گزارش امروز شما:\n\n" \
                              f"شما امروز **{user.daily_downloads}** دانلود موفق داشته‌اید."
                
                await bot.send_message(chat_id=user_id, text=user_report)
            
            # ریست کردن دانلود روزانه
            user_manager.reset_daily_downloads(user_id)

        except Exception as e:
            # از خطاهای مربوط به کاربران حذف شده یا بلاک کرده جلوگیری می‌کند
            if 'bot was blocked' in str(e) or 'user is deactivated' in str(e):
                logger.warning(f"کاربر {user_id} ربات را بلاک کرده یا غیرفعال است.", extra=extra_log_info)
            else:
                logger.error(f"خطا در ارسال گزارش برای کاربر {user_id}: {e}", extra=extra_log_info)
    
    logger.info("آمار دانلود روزانه تمام کاربران ریست شد.", extra=extra_log_info)


def setup_scheduler(application: Application):
    """زمان‌بند را برای اجرای وظایف روزانه تنظیم می‌کند."""
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    scheduler.add_job(send_daily_report, 'cron', hour=23, minute=59, args=[application])
    scheduler.start()
    logger.info("زمان‌بند (Scheduler) با موفقیت برای ساعت ۲۳:۵۹ تنظیم شد.")
    return scheduler # <--- این خط را اضافه کنید