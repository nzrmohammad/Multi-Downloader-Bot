import logging
from logging.handlers import RotatingFileHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    CallbackQueryHandler, ApplicationBuilder
)
from telegram.request import HTTPXRequest

import config
from core import user_manager
from database import database
from services import youtube, spotify

from core.handlers.menu_handler import get_main_menu_keyboard, handle_menu_callback, handle_settings_callback, handle_about_callback, handle_stats_callback
from core.handlers.admin_handler import handle_admin_callback
from core.handlers.spotify_handler import handle_spotify_callback
from core.handlers.download_handler import handle_download_callback as general_download_handler
from core.handlers.locales import get_text, translations

# --- تنظیمات پیشرفته لاگ ---
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

# --- Service Dispatcher ---
SERVICES = [youtube.YoutubeService(), spotify.SpotifyService()]

async def dispatch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    for service in SERVICES:
        if await service.can_handle(url):
            await service.process(update, context)
            return
    await update.message.reply_text("لینک ارسال شده پشتیبانی نمی‌شود. 🙁")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_manager.get_or_create_user(update)
    if user.language is None:
        keyboard = [
            [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en")],
            [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang:fa")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please select your language:", reply_markup=reply_markup)
    else:
        start_message = get_text('welcome', user.language)
        await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split(':')[1]
    user_manager.set_user_language(query.from_user.id, lang)
    await query.answer(get_text('language_selected', lang))
    
    user = user_manager.get_or_create_user(update)
    start_message = get_text('welcome', user.language)
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))


async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Callback query received: {query.data} from user {query.from_user.id}")
    prefix = query.data.split(':')[0]
    
    if prefix == 'set_lang':
        await set_language(update, context)
    elif prefix == 'menu':
        await handle_menu_callback(update, context)
    elif prefix == 'settings':
        await handle_settings_callback(update, context)
    elif prefix == 'admin':
        await handle_admin_callback(update, context)
    elif prefix == 's':
        await handle_spotify_callback(update, context)
    elif prefix == 'dl':
        await general_download_handler(update, context)
    elif prefix == 'about':
        await handle_about_callback(update, context)
    elif prefix == 'stats':
        await handle_stats_callback(update, context)
    else:
        logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

def main() -> None:
    database.create_db()

    # --- رفع خطای شبکه: افزایش زمان انتظار (Timeout) ---
    # زمان انتظار برای اتصال را ۳۰ ثانیه و زمان انتظار برای خواندن پاسخ را ۶۰ ثانیه تنظیم می‌کنیم
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=60.0)
    
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_link))
    application.add_handler(CallbackQueryHandler(main_callback_router))

    logger.info("Bot is running. Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()