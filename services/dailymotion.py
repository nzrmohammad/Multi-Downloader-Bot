# services/dailymotion.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download

DAILYMOTION_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?dailymotion\.com/video/([a-zA-Z0-9]+)")

class DailymotionService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(DAILYMOTION_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از Dailymotion...")
        info = await self._extract_info_ydl(url)
        
        if not info:
            await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد.")
            return

        video_id = info.get('id')
        title = info.get('title', 'Dailymotion Video')
        uploader = info.get('uploader', 'N/A')
        thumbnail = info.get('thumbnail')

        caption = (f"🎬 **{title}**\n"
                   f"👤 **Uploader:** `{uploader}`\n\n"
                   "کیفیت مورد نظر را انتخاب کنید:")
        keyboard = [
            [InlineKeyboardButton("🎵 دانلود صدا (MP3)", callback_data=f"dl:prepare:dailymotion:audio:{video_id}")],
            [InlineKeyboardButton("🎥 دانلود ویدیو (720p)", callback_data=f"dl:prepare:dailymotion:video_720:{video_id}")],
        ]
        
        await msg.delete()
        if thumbnail:
             await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail,
                caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        else:
             await context.bot.send_message(
                chat_id=update.effective_chat.id, text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )