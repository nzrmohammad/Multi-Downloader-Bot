# services/bandcamp.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

BANDCAMP_URL_PATTERN = re.compile(r"(?:https?://)?([a-zA-Z0-9-]+\.bandcamp\.com)/(track|album)/([a-zA-Z0-9-]+)")

class BandcampService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(BANDCAMP_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از Bandcamp...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            item_id = info.get('id')
            title = info.get('track', info.get('title', 'Bandcamp Release'))
            uploader = info.get('artist', 'N/A')
            thumbnail = info.get('thumbnail')

            caption = (
                f"🎵 **{title}**\n"
                f"👤 **Artist:** `{uploader}`\n\n"
                "برای دانلود روی دکمه زیر کلیک کنید."
            )
            # Bandcamp downloads are audio by default
            keyboard = [[InlineKeyboardButton("🎧 دانلود", callback_data=f"dl:audio:{item_id}")]]
            
            await msg.delete()
            if thumbnail:
                 await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=thumbnail,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                 await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        except Exception as e:
            await msg.edit_text("❌ خطایی در پردازش لینک Bandcamp رخ داد.")
            print(f"Bandcamp Error: {e}")