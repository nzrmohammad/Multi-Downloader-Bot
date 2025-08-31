# bot/handlers.py

import re
import uuid
import logging
from urllib.parse import urlparse
import requests
import yt_dlp
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler, InlineQueryHandler, ConversationHandler
)

from database.database import AsyncSessionLocal
from services import SERVICES
from core import user_manager
from core.handlers.menu_handler import (
    get_main_menu_keyboard, handle_menu_callback, handle_settings_callback, 
    handle_about_callback, handle_account_callback, handle_service_status_callback
)
from core.handlers.admin_handler import admin_conv_handler
from core.handlers.spotify_handler import handle_spotify_callback
from core.handlers.download_handler import handle_download_callback, handle_playlist_zip_download
from core.handlers.locales import get_text
from core.handlers.service_manager import get_service_status # توجه: این تابع باید async شود
from core.handlers.plans_handler import show_plans
# from core.user_manager import redeem_promo_code # این تابع باید async شود

logger = logging.getLogger(__name__)

URL_REGEX = r"(https?://[^\s]+)"

def resolve_shortened_url(url: str) -> str:
    """لینک‌های کوتاه شده را به لینک اصلی تبدیل می‌کند."""
    parsed_url = urlparse(url)
    if 'on.soundcloud.com' in parsed_url.netloc:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code == 200 and response.url != url:
                return response.url
        except requests.RequestException:
            return url
    return url

# --- هندلرهای اصلی ربات ---

async def dispatch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لینک‌ها را شناسایی کرده و به سرویس مناسب ارسال می‌کند."""
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        
        if user.is_banned:
            await update.message.reply_text("شما از استفاده از این ربات محروم شده‌اید.")
            return

        urls = re.findall(URL_REGEX, update.message.text or "")
        if not urls:
            await update.message.reply_text("هیچ لینک معتبری در پیام شما یافت نشد. 🧐")
            return

        batch_limit = user_manager.get_batch_limit(user)
        if len(urls) > batch_limit:
            await update.message.reply_text(f"شما مجاز به ارسال حداکثر {batch_limit} لینک در یک پیام هستید.")
            return
        
        if len(urls) > 1:
            await update.message.reply_text(f"✅ {len(urls)} لینک دریافت شد. دانلودها به زودی ارسال خواهند شد.")

        for url in urls:
            resolved_url = resolve_shortened_url(url)
            found_service = False
            for service in SERVICES:
                # service_is_enabled = await get_service_status(session, service.__class__.__name__.replace("Service", "").lower())
                # if not service_is_enabled: continue
                
                if await service.can_handle(resolved_url):
                    try:
                        await service.process(update, context, url=resolved_url)
                    except Exception as e:
                        logger.error(f"Error processing {url} with {service.__class__.__name__}: {e}", exc_info=True)
                        await context.bot.send_message(chat_id=user.user_id, text=f"❌ در پردازش لینک زیر خطایی رخ داد:\n`{url}`")
                    found_service = True
                    break
            
            if not found_service:
                await context.bot.send_message(chat_id=user.user_id, text=f"لینک زیر پشتیبانی نمی‌شود: `{url}`")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start را مدیریت می‌کند."""
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        start_message = get_text('welcome', user.language)
        await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زبان کاربر را تنظیم می‌کند."""
    query = update.callback_query
    await query.answer()
    lang = query.data.split(':')[1]
    
    async with AsyncSessionLocal() as session:
        await user_manager.set_user_language(session, query.from_user.id, lang)
        user = await user_manager.get_or_create_user(session, update)
        start_message = get_text('welcome', user.language)
        await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جستجوی inline را مدیریت می‌کند (بدون نیاز به دیتابیس)."""
    query = update.inline_query.query
    if not query or len(query) < 3:
        return

    results = []
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True, 'default_search': 'ytsearch5'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(query, download=False)
            
            for entry in search_result.get('entries', []):
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=entry.get('title', 'Unknown Title'),
                        input_message_content=InputTextMessageContent(f"https://www.youtube.com/watch?v={entry.get('id')}"),
                        description=f"By: {entry.get('uploader', 'N/A')}",
                        thumbnail_url=entry.get('thumbnail'),
                    )
                )
    except Exception as e:
        logger.error(f"Error in inline search: {e}", extra={'user_id': update.inline_query.from_user.id})

    await update.inline_query.answer(results, cache_time=10)

async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تمام دکمه‌های شیشه‌ای را به هندلر مناسب مسیردهی می‌کند."""
    query = update.callback_query
    await query.answer()

    prefix = query.data.split(':')[0]
    
    handler_map = {
        'set_lang': set_language,
        'menu': handle_menu_callback,
        'account': handle_account_callback,
        'settings': handle_settings_callback,
        'about': handle_about_callback,
        'plans': show_plans,
        'services': handle_service_status_callback,
        's': handle_spotify_callback,
        'dl': handle_download_callback,
        'yt': handle_playlist_zip_download,
    }

    if prefix in handler_map:
        await handler_map[prefix](update, context)
    else:
        logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

# --- Promo Code Conversation ---
REDEEM_CODE = range(1)

async def start_redeem_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="promo:cancel_redeem")]]
    await query.edit_message_text(
        text="لطفاً کد تخفیف خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REDEEM_CODE

async def receive_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """کد تخفیف را دریافت و اعتبارسنجی می‌کند."""
    async with AsyncSessionLocal() as session:
        user_id = update.effective_user.id
        code = update.message.text
        
        # result_message = await user_manager.redeem_promo_code(session, user_id, code)
        # await update.message.reply_text(result_message, parse_mode='Markdown')
        
        user = await user_manager.get_or_create_user(session, update)
        await update.message.reply_text(
            get_text('welcome', user.language),
            reply_markup=get_main_menu_keyboard(user.user_id, user.language)
        )
    return ConversationHandler.END

async def cancel_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فرآیند ثبت کد را لغو می‌کند."""
    query = update.callback_query
    await query.answer()
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        await query.edit_message_text(
            get_text('welcome', user.language),
            reply_markup=get_main_menu_keyboard(user.user_id, user.language)
        )
    return ConversationHandler.END

promo_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_redeem_promo, pattern='^promo:start_redeem$')],
    states={
        REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_code)],
    },
    fallbacks=[CallbackQueryHandler(cancel_redeem, pattern='^promo:cancel_redeem$')],
)

def register_handlers(application: Application):
    """تمام هندلرها را به اپلیکیشن اضافه می‌کند."""
    application.add_handler(promo_conv_handler)
    application.add_handler(admin_conv_handler) # این هندلر باید async شود
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("plans", show_plans))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_link))
    application.add_handler(CallbackQueryHandler(main_callback_router))
    application.add_handler(InlineQueryHandler(inline_query_handler))