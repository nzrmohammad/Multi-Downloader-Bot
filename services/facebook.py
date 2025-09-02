# services/facebook.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download

# --- FIX: الگوی جامع برای پشتیبانی از انواع لینک‌های ویدیو، پست و اشتراک‌گذاری ---
FACEBOOK_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|m\.|web\.)?facebook\.com/(?:.+/posts|watch|video\.php|reel|share)"
)

class FacebookService(BaseService):
    async def can_handle(self, url: str) -> bool:
        """بررسی می‌کند که آیا لینک مربوط به فیسبوک است یا خیر."""
        return re.search(FACEBOOK_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        """لینک‌های ویدیویی فیسبوک را پردازش می‌کند."""
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return
            
        msg = await update.message.reply_text("در حال پردازش لینک فیسبوک...")
        
        # ارسال URL کامل به yt-dlp که می‌تواند انواع فرمت‌ها را مدیریت کند
        info = await self._extract_info_ydl(url)
        
        if not info:
            await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد. ممکن است ویدیو خصوصی باشد، حذف شده باشد یا فقط حاوی متن باشد.")
            return

        video_id = info.get('id')
        title = info.get('title', 'Facebook Video')
        uploader = info.get('uploader', 'N/A')
        thumbnail = info.get('thumbnail')
        duration = info.get('duration', 0)
        
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"

        caption = (
            f"👍 **ویدیوی فیسبوک**\n\n"
            f"**عنوان:** `{title}`\n"
            f"**ارسال کننده:** `{uploader}`\n"
            f"**مدت زمان:** `{duration_str}`\n\n"
            "لطفا کیفیت مورد نظر را برای دانلود انتخاب کنید:"
        )
        
        keyboard = []
        video_formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
        
        keyboard.append([InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data=f"dl:prepare:facebook:audio:{video_id}")])

        sd_format = next((f for f in video_formats if f.get('height') and f.get('height') <= 480), None)
        hd_format = next((f for f in sorted(video_formats, key=lambda x: x.get('height') or 0, reverse=True) if f.get('height') and f.get('height') >= 720), None)

        if sd_format:
            filesize = sd_format.get('filesize') or sd_format.get('filesize_approx', 0)
            filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
            keyboard.append([InlineKeyboardButton(f"🎬 کیفیت SD ({filesize_mb_str})", callback_data=f"dl:prepare:facebook:video_{sd_format.get('format_id', 'sd')}:{video_id}")])

        if hd_format:
            filesize = hd_format.get('filesize') or hd_format.get('filesize_approx', 0)
            filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
            keyboard.append([InlineKeyboardButton(f"🎬 کیفیت HD ({filesize_mb_str})", callback_data=f"dl:prepare:facebook:video_{hd_format.get('format_id', 'hd')}:{video_id}")])
        
        if not sd_format and not hd_format and video_formats:
            keyboard.append([InlineKeyboardButton("🎬 بهترین کیفیت", callback_data=f"dl:prepare:facebook:video_best:{video_id}")])

        if not video_formats: # اگر هیچ فرمت ویدیویی پیدا نشد
            await msg.edit_text("❌ محتوای ویدیویی در این لینک یافت نشد.")
            return

        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")])

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