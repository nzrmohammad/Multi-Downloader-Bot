# services/pornhub_service.py

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp

import config  # <--- وارد کردن کانفیگ برای دسترسی به پراکسی
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

PORNHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:[a-zA-Z\d-]+\.)?pornhub\.com/(view_video\.php\?viewkey=|embed/)([a-zA-Z0-9]+)"
)

class PornhubService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(PORNHUB_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال پردازش لینک... 🧐")

        try:
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
                'proxy': config.get_random_proxy(),  # <--- استفاده از سیستم پراکسی خودکار
                'nocheckcertificate': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد. ممکن است لینک نامعتبر باشد یا پراکسی‌های ربات مسدود شده باشند.")
                return

            video_id = info.get('id')
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'N/A')
            view_count = info.get('view_count', 0)

            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            
            caption = (
                f"🔞 **{title}**\n\n"
                f"👤 **کانال:** `{uploader}`\n"
                f"⏳ **مدت زمان:** `{duration_str}`\n"
                f"👁 **بازدید:** `{view_count:,}`\n\n"
                "لطفا کیفیت مورد نظر را برای دانلود انتخاب کنید:"
            )

            keyboard = []
            video_formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
            
            seen_resolutions = set()
            unique_formats = []
            for f in sorted(video_formats, key=lambda x: x.get('height') or 0, reverse=True):
                height = f.get('height')
                if height and height not in seen_resolutions:
                    unique_formats.append(f)
                    seen_resolutions.add(height)

            for f in unique_formats[:3]:
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
                button_text = f"🎬 دانلود کیفیت {f['height']}p ({filesize_mb_str})"
                callback_data = f"dl:prepare:pornhub:video_{f.get('format_id', 'best')}:{video_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")])

            await msg.delete()
            if thumbnail:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Pornhub service error: {e}", exc_info=True)
            await msg.edit_text("❌ خطایی در پردازش لینک رخ داد. ممکن است ویدیو خصوصی، حذف شده یا لینک پراکسی نامعتبر باشد.")