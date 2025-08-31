import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
from services.base_service import BaseService
import config

TWITTER_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(twitter|x)\.com/([a-zA-Z0-9_]+)/status/(\d+)")

class TwitterService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(TWITTER_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک توییتر...")
        try:
            # --- ✨ FIX ✨: اضافه کردن کوکی برای دور زدن محدودیت NSFW ---
            ydl_opts = {
                'quiet': True,
                'cookiefile': None # برای اطمینان از عدم استفاده از فایل کوکی
            }
            # اگر توکن در فایل .env تعریف شده بود، آن را به هدر اضافه کن
            if config.TWITTER_AUTH_TOKEN:
                ydl_opts['http_headers'] = {
                    'Cookie': f'auth_token={config.TWITTER_AUTH_TOKEN}'
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if not info:
                 await msg.edit_text("❌ محتوای این توییت قابل پردازش نیست.")
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
        except Exception as e:
            logging.error(f"Twitter service error: {e}")
            await msg.edit_text("❌ خطایی در پردازش لینک توییتر رخ داد. ممکن است توییت حاوی ویدیو نباشد یا کوکی `TWITTER_AUTH_TOKEN` شما نامعتبر باشد.")