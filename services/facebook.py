# services/facebook_service.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService

FACEBOOK_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/(?:watch/?\?v=|video\.php\?v=|.+/videos/)(\d+)")

class FacebookService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(FACEBOOK_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک فیسبوک...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_id = info.get('id')
            title = info.get('title', 'Facebook Video')
            uploader = info.get('uploader', 'N/A')
            thumbnail = info.get('thumbnail')

            caption = (
                f"**👍 ویدیوی فیسبوک**\n\n"
                f"**عنوان:** `{title}`\n"
                f"**ارسال کننده:** `{uploader}`"
            )
            
            # فرمت جدید: dl:prepare:service_name:quality_info:resource_id
            keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو (کیفیت HD)", callback_data=f"dl:prepare:facebook:video_hd:{video_id}")]]
            
            await msg.delete()
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Facebook service error: {e}")
            await msg.edit_text("❌ خطایی در پردازش لینک فیسبوک رخ داد.")