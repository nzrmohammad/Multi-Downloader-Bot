# services/tiktok.py

import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp

from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

TIKTOK_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/(@[a-zA-Z0-9_.-]+)/video/(\d+)")

class TikTokService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(TIKTOK_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از تیک‌تاک...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_id = info.get('id')
            caption_text = (
                f"🎶 **ویدیوی تیک‌تاک**\n\n"
                f"👤 **ارسال کننده:** `{info.get('uploader', 'N/A')}`\n\n"
                "برای دانلود ویدیو روی دکمه زیر کلیک کنید."
            )
            keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:video:{video_id}")]]
            
            await msg.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await msg.edit_text("❌ خطایی در پردازش لینک تیک‌تاک رخ داد.")
            print(f"TikTok Error: {e}")