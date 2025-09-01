# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/callback_query_handler.py

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
from services.castbox import CastboxService # <--- ایمپورت جدید

logger = logging.getLogger(__name__)


async def handle_castbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """
    دکمه‌های مربوط به سرویس کست‌باکس (صفحه‌بندی و انتخاب برای دانلود) را پردازش می‌کند.
    """
    query = update.callback_query
    await query.answer()
    
    command, *params = query.data.split(':')[1:]
    
    # یک نمونه از سرویس کست‌باکس برای دسترسی به متدهای آن ایجاد می‌کنیم
    castbox_service = CastboxService()
    
    if command == 'page':
        page = int(params[0])
        chat_id = int(params[1])
        # لیست کامل قسمت‌ها را که قبلا ذخیره کرده بودیم، بازیابی می‌کنیم
        episodes = context.bot_data.get(f"castbox_eps_{chat_id}", [])
        if episodes:
            keyboard = castbox_service.build_episode_keyboard(episodes, chat_id=chat_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            
    elif command == 'dl':
        episode_id = params[0]
        # لینک مستقیم قسمت را بر اساس شناسه انتخاب شده می‌سازیم
        episode_url = f"https://castbox.fm/ep/{episode_id}"
        
        # پیام را ویرایش می‌کنیم تا به کاربر اطلاع دهیم دانلود در حال آماده‌سازی است
        # نکته: چون متد process خودش پیام را ویرایش می‌کند، باید آبجکت message را به آن پاس دهیم.
        # راه ساده‌تر این است که آبجکت update را مستقیما پاس دهیم.
        original_message = await query.edit_message_text(f"در حال آماده‌سازی برای دانلود قسمت انتخابی...")
        
        # یک آبجکت update شبیه‌سازی شده می‌سازیم تا پیام صحیح را به متد process بدهیم
        class MockUpdate:
            def __init__(self, message, effective_user):
                self.message = message
                self.effective_user = effective_user

        mock_update = MockUpdate(original_message, query.from_user)

        # متد اصلی process را برای شروع دانلود فراخوانی می‌کنیم
        await castbox_service.process(mock_update, context, user, episode_url)


async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تمام دکمه‌های شیشه‌ای را به هندلر مناسب مسیردهی می‌کند."""
    query = update.callback_query
    await query.answer()

    prefix = query.data.split(':')[0]
    
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)

        # دیکشنری برای نگاشت پیشوند callback به تابع مربوطه
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
            'spotify': handle_playlist_zip_download,
            'castbox': handle_castbox_callback, # <--- هندلر جدید اضافه شد
        }

        if prefix in handler_map:
            # پاس دادن آبجکت user به هندلرها برای جلوگیری از کوئری مجدد
            await handler_map[prefix](update, context, user)
        elif prefix == 'promo': # هندلر پرومو کد جداگانه مدیریت می‌شود
             pass # توسط ConversationHandler مدیریت می‌شود
        else:
            logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user: user_manager.User):
    """زبان کاربر را تنظیم می‌کند."""
    query = update.callback_query
    lang = query.data.split(':')[1]
    
    async with AsyncSessionLocal() as session:
        await user_manager.set_user_language(session, user, lang)
        
    start_message = get_text('welcome', lang)
    # آپدیت کردن زبان در خود آبجکت user برای نمایش صحیح منو
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
        
        # نمایش مجدد منوی اصلی
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