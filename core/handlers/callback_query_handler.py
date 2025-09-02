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
from .plans_handler import show_plans
from .locales import get_text

# وارد کردن هندلرهای اختصاصی از پوشه callbacks
# توجه: فایل download_handler.py سابق اکنون به پکیج download تبدیل شده است
from .callbacks import spotify, youtube, castbox, instagram
from .download import callbacks as download_callbacks 

logger = logging.getLogger(__name__)

async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    مسیریاب اصلی که تمام callback query ها را به هندلر مناسب ارسال می‌کند.
    """
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
            's': spotify.handle_spotify_callback,
            'dl': download_callbacks.handle_download_callback,
            'yt': download_callbacks.handle_playlist_callback,
            'yt_channel': youtube.handle_youtube_channel_callback,
            'spotify': download_callbacks.handle_playlist_callback, 
            'castbox': castbox.handle_castbox_callback,
            'ig_profile': instagram.handle_instagram_profile_callback,
        }

        if prefix in handler_map:
            await handler_map[prefix](update, context, user)
        elif prefix == 'promo':
             # این مورد توسط ConversationHandler مدیریت می‌شود و نیازی به اقدام در اینجا نیست
             pass 
        else:
            logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user: user_manager.User):
    """زبان انتخابی کاربر را در دیتابیس ذخیره کرده و منو را مجددا نمایش می‌دهد."""
    query = update.callback_query
    lang = query.data.split(':')[1]
    async with AsyncSessionLocal() as session:
        await user_manager.set_user_language(session, user, lang)
    start_message = get_text('welcome', lang)
    user.language = lang # آپدیت زبان در آبجکت فعلی برای نمایش صحیح منو
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

# --- ConversationHandler برای ثبت کد تخفیف ---
REDEEM_CODE = range(1)

async def start_redeem_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="promo:cancel_redeem")]]
    await query.edit_message_text(text="لطفاً کد تخفیف خود را وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return REDEEM_CODE

async def receive_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        code = update.message.text
        result_message = await user_manager.redeem_promo_code(session, user, code)
        await update.message.reply_text(result_message, parse_mode='Markdown')
        # نمایش مجدد منوی اصلی
        start_message = get_text('welcome', user.language)
        await update.message.reply_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))
    return ConversationHandler.END

async def cancel_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        start_message = get_text('welcome', user.language)
        await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))
    return ConversationHandler.END

promo_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_redeem_promo, pattern='^promo:start_redeem$')],
    states={REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_code)],},
    fallbacks=[CallbackQueryHandler(cancel_redeem, pattern='^promo:cancel_redeem$')],
)