# services/vimeo.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

VIMEO_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?vimeo\.com/(\d+)")

class VimeoService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(VIMEO_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از Vimeo...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
            
            video_id = info.get('id')
            title = info.get('title', 'Vimeo Video')
            uploader = info.get('uploader', 'N/A')
            thumbnail = info.get('thumbnail')

            caption = (
                f"🎬 **{title}**\n"
                f"👤 **Uploader:** `{uploader}`\n\n"
                "کیفیت مورد نظر را انتخاب کنید:"
            )
            keyboard = [
                [InlineKeyboardButton("🎵 دانلود صدا (MP3)", callback_data=f"dl:audio:{video_id}")],
                [InlineKeyboardButton("🎥 دانلود ویدیو (720p)", callback_data=f"dl:video_720:{video_id}")],
            ]
            
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
            await msg.edit_text("❌ خطایی در پردازش لینک Vimeo رخ داد.")
            print(f"Vimeo Error: {e}")