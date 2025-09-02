# core/handlers/callback_query_handler.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from database.database import AsyncSessionLocal
from core import user_manager
from .menu_handler import (
    handle_menu_callback, handle_settings_callback, handle_about_callback,
    handle_account_callback, handle_service_status_callback, get_main_menu_keyboard
)
from .spotify_handler import handle_spotify_callback
from .download_handler import handle_download_callback, handle_playlist_zip_download
from .plans_handler import show_plans
from .locales import get_text
from services.castbox import CastboxService
# --- FIX: ایمپورت جدید ---
from services.youtube import YoutubeService

logger = logging.getLogger(__name__)


async def handle_castbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """
    دکمه‌های مربوط به سرویس کست‌باکس (صفحه‌بندی و انتخاب برای دانلود) را پردازش می‌کند.
    """
    query = update.callback_query
    await query.answer()
    
    command, *params = query.data.split(':')[1:]
    
    castbox_service = CastboxService()
    
    if command == 'page':
        page = int(params[0])
        chat_id = int(params[1])
        episodes = context.bot_data.get(f"castbox_eps_{chat_id}", [])
        if episodes:
            keyboard = castbox_service.build_episode_keyboard(episodes, chat_id=chat_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            
    elif command == 'dl':
        episode_id = params[0]
        episode_url = f"https://castbox.fm/ep/{episode_id}"
        
        original_message = await query.edit_message_text(f"در حال آماده‌سازی برای دانلود قسمت انتخابی...")
        
        class MockUpdate:
            def __init__(self, message, effective_user):
                self.message = message
                self.effective_user = effective_user

        mock_update = MockUpdate(original_message, query.from_user)
        await castbox_service.process(mock_update, context, user, episode_url)

# --- FIX: هندلر جدید برای صفحه‌بندی پلی‌لیست‌های یوتیوب ---
async def handle_youtube_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """دکمه‌های صفحه‌بندی پلی‌لیست‌های یوتیوب را مدیریت می‌کند."""
    query = update.callback_query
    await query.answer()

    command, page_str, chat_id_str = query.data.split(':')[1:]
    page = int(page_str)
    chat_id = int(chat_id_str)

    playlists = context.bot_data.get(f"yt_pls_{chat_id}", [])
    if playlists:
        youtube_service = YoutubeService()
        keyboard = youtube_service.build_playlist_keyboard(playlists, chat_id, page=page)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"Could not edit YouTube channel page message: {e}")


async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تمام دکمه‌های شیشه‌ای را به هندلر مناسب مسیردهی می‌کند."""
    query = update.callback_query
    await query.answer()

    prefix = query.data.split(':')[0]
    
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)

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
            # --- FIX: افزودن هندلر جدید برای صفحه‌بندی یوتیوب ---
            'yt_channel': handle_youtube_channel_callback,
            'spotify': handle_playlist_zip_download,
            'castbox': handle_castbox_callback,
        }

        if prefix in handler_map:
            await handler_map[prefix](update, context, user)
        elif prefix == 'promo':
             pass
        else:
            logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user: user_manager.User):
    """زبان کاربر را تنظیم می‌کند."""
    query = update.callback_query
    lang = query.data.split(':')[1]
    
    async with AsyncSessionLocal() as session:
        await user_manager.set_user_language(session, user, lang)
        
    start_message = get_text('welcome', lang)
    user.language = lang
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

# --- Promo Code Conversation ---
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
    """کد تخفیف را دریافت و اعتبارسنجی می‌کند."""
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        code = update.message.text
        
        result_message = await user_manager.redeem_promo_code(session, user, code)
        await update.message.reply_text(result_message, parse_mode='Markdown')
        
        start_message = get_text('welcome', user.language)
        await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))
    return ConversationHandler.END

async def cancel_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فرآیند ثبت کد را لغو می‌کند."""
    query = update.callback_query
    await query.answer()
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        start_message = get_text('welcome', user.language)
        await query.edit_message_text(
            start_message,
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