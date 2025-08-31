# services/twitch_service.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService

TWITCH_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?twitch\.tv/(?:videos/(\d+)|clips/([a-zA-Z0-9_-]+)|([a-zA-Z0-9_]+)/clip/([a-zA-Z0-9_-]+))")

class TwitchService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(TWITCH_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک توییچ...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)

            video_id = info.get('id')
            title = info.get('title', 'Twitch Stream')
            uploader = info.get('uploader', 'N/A')
            thumbnail = info.get('thumbnail')
            is_clip = 'clip' in url or 'clips' in info.get('webpage_url', '')

            caption = (f"**🎮 ویدیوی توییچ**\n\n"
                       f"**{'کلیپ' if is_clip else 'استریم'}:** `{title}`\n"
                       f"**استریمر:** `{uploader}`")
            
            # --- ✨ FIX ✨ ---
            keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:video:{video_id}")]]
            
            await msg.delete()
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Twitch service error: {e}")
            await msg.edit_text("❌ خطایی در پردازش لینک توییچ رخ داد.")