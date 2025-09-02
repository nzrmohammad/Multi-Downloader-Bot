import logging
import os
from pathlib import Path
import asyncio
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
from services.youtube import YoutubeService
from services.instagram import InstagramService 
from pydantic_core import ValidationError

logger = logging.getLogger(__name__)

async def handle_instagram_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    action = parts[1]
    user_pk = parts[2]
    
    client = InstagramService._client
    if not client:
        await query.message.reply_text("❌ سرویس اینستاگرام در حال حاضر در دسترس نیست.")
        return

    loop = asyncio.get_running_loop()
    download_paths = []
    try:
        if action == 'pfp':
            await query.message.reply_text("در حال دانلود عکس پروفایل با بالاترین کیفیت...")
            user_info = await loop.run_in_executor(None, lambda: client.user_info(user_pk))
            path = await loop.run_in_executor(None, lambda: client.photo_download_by_url(str(user_info.profile_pic_url_hd), folder="downloads"))
            download_paths.append(path)

        elif action == 'stories':
            await query.message.reply_text("در حال دانلود استوری‌ها...")
            stories = await loop.run_in_executor(None, lambda: client.user_stories(user_pk))
            for story in stories:
                path = await loop.run_in_executor(None, lambda: client.story_download(story.pk, folder="downloads"))
                download_paths.append(path)
        
        elif action == 'highlights':
            await query.message.reply_text("در حال دانلود هایلایت‌ها... (این فرآیند ممکن است زمان‌بر باشد)")
            highlights = await loop.run_in_executor(None, lambda: client.user_highlights(user_pk))
            for highlight in highlights:
                # --- FIX: استفاده از نام صحیح تابع برای دانلود هایلایت ---
                paths = await loop.run_in_executor(None, lambda: client.highlight_download(highlight.pk, folder="downloads"))
                # highlight_download یک لیست از مسیرها برمی‌گرداند
                download_paths.extend(paths)

        if not download_paths:
            await query.message.reply_text("هیچ محتوایی برای دانلود یافت نشد.")
            return

        await query.message.reply_text(f"✅ دانلود {len(download_paths)} فایل کامل شد. در حال آپلود...")
        for path in download_paths:
            with open(path, 'rb') as file_to_send:
                if Path(path).suffix == ".mp4":
                    await context.bot.send_video(chat_id=query.message.chat_id, video=file_to_send)
                else:
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_to_send)
    
    # --- FIX: مدیریت خطای ValidationError به صورت جداگانه ---
    except ValidationError as e:
        logger.error(f"Pydantic validation error during Instagram download: {e}", exc_info=True)
        await query.message.reply_text("❌ دانلود ناموفق بود. اینستاگرام ساختار داده‌های خود را تغییر داده و کتابخانه نیاز به آپدیت دارد.")
    except Exception as e:
        logger.error(f"Error during Instagram profile download: {e}", exc_info=True)
        await query.message.reply_text(f"❌ خطایی در هنگام دانلود رخ داد: {e}")
    finally:
        for path in download_paths:
            if os.path.exists(path):
                os.remove(path)


async def handle_castbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()
    command, *params = query.data.split(':')[1:]
    castbox_service = CastboxService()
    if command == 'page':
        page, chat_id = map(int, params)
        episodes = context.bot_data.get(f"castbox_eps_{chat_id}", [])
        if episodes:
            keyboard = castbox_service.build_episode_keyboard(episodes, chat_id=chat_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)
    elif command == 'dl':
        episode_id = params[0]
        episode_url = f"https://castbox.fm/ep/{episode_id}"
        original_message = await query.edit_message_text(f"در حال آماده‌سازی برای دانلود قسمت انتخابی...")
        class MockUpdate:
            def __init__(self, message, effective_user): self.message, self.effective_user = message, effective_user
        await castbox_service.process(MockUpdate(original_message, query.from_user), context, user, episode_url)

async def handle_youtube_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()
    command, page_str, chat_id_str = query.data.split(':')[1:]
    page, chat_id = int(page_str), int(chat_id_str)
    playlists = context.bot_data.get(f"yt_pls_{chat_id}", [])
    if playlists:
        youtube_service = YoutubeService()
        keyboard = youtube_service.build_playlist_keyboard(playlists, chat_id, page=page)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"Could not edit YouTube channel page message: {e}")

async def main_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            'yt_channel': handle_youtube_channel_callback,
            'spotify': handle_playlist_zip_download,
            'castbox': handle_castbox_callback,
            # --- FIX: افزودن هندلر جدید برای دکمه‌های پروفایل اینستاگرام ---
            'ig_profile': handle_instagram_profile_callback,
        }

        if prefix in handler_map:
            await handler_map[prefix](update, context, user)
        elif prefix == 'promo':
             pass # Handled by promo_conv_handler
        else:
            logger.warning(f"Unknown callback prefix '{prefix}' from data: {query.data}")

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user: user_manager.User):
    query = update.callback_query
    lang = query.data.split(':')[1]
    async with AsyncSessionLocal() as session:
        await user_manager.set_user_language(session, user, lang)
    start_message = get_text('welcome', lang)
    user.language = lang
    await query.edit_message_text(start_message, reply_markup=get_main_menu_keyboard(user.user_id, user.language))

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