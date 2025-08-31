# services/tiktok.py

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp

import config
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
            ydl_opts = {
                'quiet': True,
                'proxy': config.get_random_proxy(),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if not info:
                await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد. ممکن است لینک نامعتبر باشد.")
                return

            video_id = info.get('id')
            caption_text = (
                f"🎶 **ویدیوی تیک‌تاک**\n\n"
                f"👤 **ارسال کننده:** `{info.get('uploader', 'N/A')}`\n\n"
                "برای دانلود ویدیو روی دکمه زیر کلیک کنید."
            )
            keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:prepare:tiktok:video_best:{video_id}")]]
            
            await msg.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await msg.edit_text("❌ خطایی در پردازش لینک تیک‌تاک رخ داد.")
            logging.error(f"TikTok Error: {e}")