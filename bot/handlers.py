# bot/handlers.py

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    InlineQueryHandler,
    ConversationHandler,
)
import uuid
import re
import requests
from urllib.parse import urlparse
import yt_dlp
import logging

from core import user_manager
from services import SERVICES

# --- وارد کردن تمام هندلرها ---
from core.handlers.menu_handler import (
    get_main_menu_keyboard,
    handle_menu_callback,
    handle_settings_callback,
    handle_about_callback,
    handle_account_callback,
    handle_service_status_callback,
)
from core.handlers.admin_handler import admin_conv_handler
from core.handlers.spotify_handler import handle_spotify_callback
from core.handlers.download_handler import handle_download_callback, handle_playlist_zip_download
from core.handlers.locales import get_text
from core.handlers.service_manager import get_service_status
from core.handlers.plans_handler import show_plans
from core.user_manager import redeem_promo_code
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup


logger = logging.getLogger(__name__)

# --- توابع کمکی ---
URL_REGEX = r"(https?://[^\s]+)"

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
    """لینک‌ها را شناسایی کرده و بر اساس پلن کاربر، به صورت تکی یا دسته‌ای پردازش می‌کند."""
    user = user_manager.get_or_create_user(update)
    user_id = user.user_id
    extra_log_info = {'user_id': user_id}

    if user.is_banned:
        await update.message.reply_text("شما از استفاده از این ربات محروم شده‌اید.")
        return

    text = update.message.text
    urls = re.findall(URL_REGEX, text)
    
    if not urls:
        await update.message.reply_text("هیچ لینک معتبری در پیام شما یافت نشد. 🧐")
        return

    batch_limit = user_manager.get_batch_limit(user)

    if len(urls) > batch_limit:
        await update.message.reply_text(
            f"شما مجاز به ارسال حداکثر {batch_limit} لینک در یک پیام هستید.\n"
            f"لطفاً برای افزایش محدودیت، اشتراک خود را ارتقا دهید."
        )
        return
    
    if len(urls) > 1:
        await update.message.reply_text(
            f"✅ درخواست شما برای دانلود {len(urls)} لینک دریافت شد. "
            "دانلودها به زودی یکی پس از دیگری برای شما ارسال خواهند شد."
        )

    for url in urls:
        resolved_url = resolve_shortened_url(url)
        found_service = False
        for service in SERVICES:
            service_name = service.__class__.__name__.replace("Service", "").lower()
            if not get_service_status(service_name):
                continue

            if await service.can_handle(resolved_url):
                logger.info(f"Link handled by {service_name}: {url}", extra=extra_log_info)
                try:
                    await service.process(update, context, url=resolved_url)
                except Exception as e:
                    logger.error(f"Error processing {url} with {service_name}: {e}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ متاسفانه در پردازش لینک زیر خطایی رخ داد:\n`{url}`"
                    )
                found_service = True
                break
        
        if not found_service:
            logger.warning(f"Unsupported link: {url}", extra=extra_log_info)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"لینک زیر پشتیبانی نمی‌شود: `{url}`"
            )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start را مدیریت می‌کند."""
    user = user_manager.get_or_create_user(update)
    start_message = get_text('welcome', user.language)
    await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زبان کاربر را تنظیم می‌کند."""
    query = update.callback_query
    await query.answer()
    lang = query.data.split(':')[1]
    user_manager.set_user_language(query.from_user.id, lang)
    
    user = user_manager.get_or_create_user(update)
    start_message = get_text('welcome', user.language)
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جستجوی inline را مدیریت می‌کند."""
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

    user_id = query.from_user.id
    extra_log_info = {'user_id': user_id}
    logger.info(f"Callback query received: {query.data}", extra=extra_log_info)

    parts = query.data.split(':')
    prefix = parts[0]
    command = parts[1] if len(parts) > 1 else None

    # این هندلر ConversationHandler ادمین را مسدود نمی‌کند چون ConversationHandler زودتر ثبت شده
    if prefix in ['admin', 'promo']:
        logger.info(f"Callback for '{prefix}' is being passed to ConversationHandler.")
        return

    if prefix == 'yt' and command == 'playlist_zip':
        await handle_playlist_zip_download(update, context)
        return

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
    }

    if prefix in handler_map:
        await handler_map[prefix](update, context)
    else:
        logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}", extra=extra_log_info)

# --- Promo Code Redemption Conversation ---
REDEEM_CODE = range(1)

async def start_redeem_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند ثبت کد تخفیف."""
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="promo:cancel_redeem")]]
    await query.edit_message_text(
        text="لطفاً کد تخفیف خود را وارد کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REDEEM_CODE

async def receive_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """کد تخفیف را از کاربر دریافت و اعتبارسنجی می‌کند."""
    user_id = update.effective_user.id
    code = update.message.text
    
    result_message = redeem_promo_code(user_id, code)
    
    await update.message.reply_text(result_message, parse_mode='Markdown')
    
    # بازگشت به منوی اصلی پس از تلاش برای ثبت کد
    user = user_manager.get_or_create_user(update)
    await update.message.reply_text(
        get_text('welcome', user.language),
        reply_markup=get_main_menu_keyboard(user.user_id, user.language)
    )
    return ConversationHandler.END

async def cancel_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فرآیند ثبت کد را لغو می‌کند."""
    query = update.callback_query
    await query.answer()
    user = user_manager.get_or_create_user(update)
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
    application.add_handler(admin_conv_handler)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("plans", show_plans))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_link))
    application.add_handler(CallbackQueryHandler(main_callback_router))
    application.add_handler(InlineQueryHandler(inline_query_handler))