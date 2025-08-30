# main.py

import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ApplicationBuilder,
    CallbackQueryHandler,
)
from telegram.request import HTTPXRequest
import requests
from urllib.parse import urlparse

import config
from database import database
from core import user_manager
from services import SERVICES  # <-- وارد کردن لیست مرکزی سرویس‌ها

# --- وارد کردن تمام هندلرها ---
from core.handlers.menu_handler import (
    get_main_menu_keyboard,
    handle_menu_callback,
    handle_settings_callback,
    handle_about_callback,
    handle_account_callback,
)
from core.handlers.admin_handler import admin_conv_handler
from core.handlers.spotify_handler import handle_spotify_callback
from core.handlers.download_handler import handle_download_callback as general_download_handler
from core.handlers.locales import get_text
from core.handlers.service_manager import initialize_services, get_service_status
from core.handlers.plans_handler import show_plans


# --- تنظیمات لاگ ---
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logging.getLogger("httpx").setLevel(logging.WARNING)


# --- توابع کمکی ---
def resolve_shortened_url(url: str) -> str:
    """لینک‌های کوتاه شده را به لینک اصلی تبدیل می‌کند."""
    parsed_url = urlparse(url)
    if 'on.soundcloud.com' in parsed_url.netloc:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code == 200 and response.url != url:
                logger.info(f"لینک کوتاه {url} به {response.url} تبدیل شد.")
                return response.url
        except requests.RequestException as e:
            logger.error(f"خطا در باز کردن لینک کوتاه {url}: {e}")
            return url
    return url


# --- هندلرهای اصلی ربات ---
async def dispatch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لینک‌ها را به سرویس مناسب ارسال می‌کند."""
    original_url = update.message.text
    resolved_url = resolve_shortened_url(original_url)

    for service in SERVICES:
        service_name = service.__class__.__name__.replace("Service", "").lower()
        if not get_service_status(service_name):
            continue  # اگر سرویس غیرفعال بود، آن را نادیده بگیر

        if await service.can_handle(resolved_url):
            if service_name in config.SENSITIVE_SERVICES:
                user = update.effective_user
                alert_text = (
                    f"🚨 **هشدار دانلود حساس** 🚨\n\n"
                    f"کاربر: `{user.id}` (@{user.username or 'N/A'})\n"
                    f"سرویس: **{service_name.capitalize()}**\n"
                    f"لینک: `{original_url}`"
                )
                await context.bot.send_message(chat_id=config.ADMIN_ID, text=alert_text, parse_mode='Markdown')
            
            await service.process(update, context, url=resolved_url)
            return
            
    await update.message.reply_text("لینک ارسال شده پشتیبانی نمی‌شود یا سرویس آن غیرفعال است. 🙁")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start را مدیریت می‌کند."""
    user = user_manager.get_or_create_user(update)
    start_message = get_text('welcome', user.language)
    await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زبان کاربر را تنظیم می‌کند."""
    query = update.callback_query
    lang = query.data.split(':')[1]
    user_manager.set_user_language(query.from_user.id, lang)
    await query.answer(get_text('language_selected', lang))
    
    user = user_manager.get_or_create_user(update)
    start_message = get_text('welcome', user.language)
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تمام دکمه‌های شیشه‌ای (callback) را مسیردهی می‌کند."""
    query = update.callback_query
    logger.info(f"Callback query received: {query.data} from user {query.from_user.id}")
    prefix = query.data.split(':')[0]
    
    # این مکالمه ادمین است و به صورت جداگانه مدیریت می‌شود
    if prefix == 'admin':
        await query.message.reply_text("برای ورود به پنل مدیریت از دستور /admin استفاده کنید.")
        return

    if prefix == 'set_lang':
        await set_language(update, context)
    elif prefix == 'menu':
        await handle_menu_callback(update, context)
    elif prefix == 'account':
        await handle_account_callback(update, context)
    elif prefix == 'settings':
        await handle_settings_callback(update, context)
    elif prefix == 'about':
        await handle_about_callback(update, context)
    elif prefix == 'plans':
        await show_plans(update, context)
    elif prefix in ['s', 'dl', 'sc', 'yt']:
        # دانلودر عمومی برای yt, sc و دانلودهای مستقیم
        if prefix in ['dl', 'sc', 'yt']:
             await general_download_handler(update, context)
        # هندلر مخصوص اسپاتیفای
        elif prefix == 's':
             await handle_spotify_callback(update, context)
    else:
        logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")


# --- تابع اصلی برنامه ---
def main() -> None:
    """ربات را راه‌اندازی و اجرا می‌کند."""
    
    # ۱. ابتدا دیتابیس و جداول را بسازید
    database.create_db()
    
    # ۲. سپس سرویس‌ها را در دیتابیس برای پنل مدیریت ثبت کنید
    initialize_services()

    # تنظیمات شبکه
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=60.0)
    
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request)
        .build()
    )

    # --- ثبت تمام هندلرها ---
    application.add_handler(admin_conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("plans", show_plans))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_link))
    application.add_handler(CallbackQueryHandler(main_callback_router))

    logger.info("Bot is running. Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()