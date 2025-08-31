# services/reddit_service.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService

REDDIT_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?reddit\.com/r/([a-zA-Z0-9_]+)/comments/([a-zA-Z0-9]+)")

class RedditService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(REDDIT_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک ردیت...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_id = info.get('id')
            title = info.get('title', 'Reddit Video')
            uploader = info.get('uploader', 'N/A') 
            subreddit = info.get('channel', 'N/A')

            caption = (
                f"**🤖 پست ردیت**\n\n"
                f"**عنوان:** `{title}`\n"
                f"**ساب‌ردیت:** `r/{subreddit}`\n"
                f"**کاربر:** `u/{uploader}`"
            )

            # فرمت جدید: dl:prepare:service_name:quality_info:resource_id
            keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:prepare:reddit:video:{video_id}")]]
            
            await msg.delete()
            await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Reddit service error: {e}")
            await msg.edit_text("❌ خطایی در پردازش لینک ردیت رخ داد.")