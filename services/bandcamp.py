# services/bandcamp.py
import re
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download
from core.handlers.download.callbacks import url_cache  # وارد کردن حافظه موقت

BANDCAMP_URL_PATTERN = re.compile(r"(?:https?://)?([a-zA-Z0-9-]+\.bandcamp\.com)/?(?:(track|album)/([a-zA-Z0-9-]+))?")

class BandcampService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(BANDCAMP_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از Bandcamp...")
        info = await self._extract_info_ydl(url, ydl_opts={'extract_flat': True, 'quiet': True})
        
        if not info:
            await msg.edit_text("❌ اطلاعات دریافت نشد. ممکن است لینک نامعتبر باشد.")
            return

        if 'entries' in info and info.get('entries'):
            playlist_title = info.get('title', 'Bandcamp Release')
            uploader = info.get('uploader', 'N/A')
            thumbnail = info.get('thumbnail')
            
            caption = (
                f"🎵 **آلبوم/هنرمند:** `{playlist_title}`\n"
                f"👤 **از:** `{uploader}`\n\n"
                f"**تعداد کل آهنگ‌ها:** `{len(info['entries'])}`\n"
                "لطفاً آهنگ مورد نظر برای دانلود را انتخاب کنید:"
            )
            
            keyboard = []
            for entry in info['entries']:
                full_url = entry.get('url')
                if full_url:
                    # FIX: استفاده از کلید کوتاه و ذخیره URL کامل در حافظه موقت
                    short_key = uuid.uuid4().hex[:12]
                    url_cache[short_key] = full_url
                    keyboard.append([InlineKeyboardButton(f"🎧 {entry.get('title', 'Unknown Track')}", callback_data=f"dl:prepare:bandcamp:audio:{short_key}")])
            
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
        else:
            full_url = info.get('webpage_url', url)
            if not full_url:
                await msg.edit_text("❌ آدرس آهنگ یافت نشد.")
                return

            # FIX: استفاده از کلید کوتاه برای تک‌آهنگ
            short_key = uuid.uuid4().hex[:12]
            url_cache[short_key] = full_url
            
            title = info.get('track', info.get('title', 'Bandcamp Release'))
            uploader = info.get('artist', 'N/A')
            thumbnail = info.get('thumbnail')

            caption = (
                f"🎵 **{title}**\n"
                f"👤 **Artist:** `{uploader}`\n\n"
                "برای دانلود روی دکمه زیر کلیک کنید."
            )
            keyboard = [[InlineKeyboardButton("🎧 دانلود", callback_data=f"dl:prepare:bandcamp:audio:{short_key}")]]
            
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