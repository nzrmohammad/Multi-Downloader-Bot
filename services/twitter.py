# services/twitter.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.settings import settings
from core.user_manager import can_download

TWITTER_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(twitter|x)\.com/([a-zA-Z0-9_]+)/status/(\d+)")

class TwitterService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(TWITTER_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        # --- FIX: ADDED DOWNLOAD LIMIT CHECK ---
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return
            
        msg = await update.message.reply_text("در حال پردازش لینک توییتر...")
        
        ydl_opts = {}
        if settings.TWITTER_AUTH_TOKEN:
            ydl_opts['http_headers'] = {'Cookie': f'auth_token={settings.TWITTER_AUTH_TOKEN}'}

        info = await self._extract_info_ydl(url, ydl_opts)
        
        if not info:
            await msg.edit_text("❌ محتوای این توییت قابل پردازش نیست. ممکن است نیاز به لاگین داشته باشد یا ویدیو نداشته باشد.")
            return

        video_id = info.get('id')
        uploader = info.get('uploader', 'N/A')
        description = info.get('description', '').split('\n')[0]
        thumbnail = info.get('thumbnail')

        caption = (
            f"**🐦 توییت از:** `{uploader}`\n\n"
            f"*{description}*\n\n"
            "برای دانلود ویدیو روی دکمه زیر کلیک کنید."
        )
        
        keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:prepare:twitter:video:{video_id}")]]
        
        await msg.delete()
        if thumbnail:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )