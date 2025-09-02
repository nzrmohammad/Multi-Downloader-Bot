# services/facebook_service.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download

FACEBOOK_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/(?:watch/?\?v=|video\.php\?v=|.+/videos/)(\d+)")

class FacebookService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(FACEBOOK_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        # --- FIX: ADDED DOWNLOAD LIMIT CHECK ---
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return
            
        msg = await update.message.reply_text("در حال پردازش لینک فیسبوک...")
        
        info = await self._extract_info_ydl(url)
        
        if not info:
            await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد. ممکن است ویدیو خصوصی باشد.")
            return

        video_id = info.get('id')
        title = info.get('title', 'Facebook Video')
        uploader = info.get('uploader', 'N/A')
        thumbnail = info.get('thumbnail')

        caption = (
            f"**👍 ویدیوی فیسبوک**\n\n"
            f"**عنوان:** `{title}`\n"
            f"**ارسال کننده:** `{uploader}`"
        )
        
        keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو (کیفیت HD)", callback_data=f"dl:prepare:facebook:video_hd:{video_id}")]]
        
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