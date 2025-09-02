# core/handlers/callbacks/youtube_callback.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.youtube import YoutubeService

logger = logging.getLogger(__name__)

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