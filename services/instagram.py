# services/instagram.py

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp

import config  # <--- وارد کردن کانفیگ برای دسترسی به پراکسی
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

INSTAGRAM_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/(p|reel|tv)/([a-zA-Z0-9_-]+)")

class InstagramService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(INSTAGRAM_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از اینستاگرام...")
        try:
            ydl_opts = {
                'quiet': True,
                'proxy': config.get_random_proxy(), # <--- استفاده از سیستم پراکسی خودکار
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if not info:
                await msg.edit_text("❌ اطلاعات پست دریافت نشد. ممکن است پست خصوصی باشد یا پراکسی‌های ربات مسدود شده باشند.")
                return

            video_id = info.get('id')
            caption_text = (
                f"📸 **پست اینستاگرام**\n\n"
                f"👤 **ارسال کننده:** `{info.get('uploader', 'N/A')}`\n\n"
                "برای دانلود ویدیو روی دکمه زیر کلیک کنید."
            )
            # توجه: اینستاگرام ممکن است چندین ویدیو/عکس داشته باشد. این کد فقط اولین مورد را در نظر می‌گیرد.
            keyboard = [[InlineKeyboardButton("🎬 دانلود", callback_data=f"dl:prepare:instagram:video:{video_id}")]]
            
            await msg.delete()
            # ارسال با عکس پست به جای متن خالی
            thumbnail = info.get('thumbnail')
            if thumbnail:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=thumbnail,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            await msg.edit_text("❌ خطایی در پردازش لینک اینستاگرام رخ داد. ممکن است پست خصوصی باشد.")
            logging.error(f"Instagram Error: {e}")