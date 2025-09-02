# services/redtube_service.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download

REDTUBE_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?redtube\.com/(\d+)")

class RedTubeService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(REDTUBE_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        # --- FIX: ADDED DOWNLOAD LIMIT CHECK ---
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return
            
        msg = await update.message.reply_text("در حال پردازش لینک RedTube... 🧐")
        
        ydl_opts = {'legacy_server_connect': True}
        info = await self._extract_info_ydl(url, ydl_opts)
        
        if not info:
            await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد. ممکن است لینک نامعتبر باشد یا ویدیو حذف شده باشد.")
            return

        video_id = info.get('id')
        title = info.get('title', 'Unknown Title')
        thumbnail = info.get('thumbnail')
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'N/A')
        view_count = info.get('view_count', 0)

        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
        
        caption = (f"🔞 **{title}**\n\n"
                   f"👤 **کانال:** `{uploader}`\n"
                   f"⏳ **مدت زمان:** `{duration_str}`\n"
                   f"👁 **بازدید:** `{view_count:,}`\n\n"
                   "لطفا کیفیت مورد نظر را برای دانلود انتخاب کنید:")

        keyboard = []
        video_formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none']
        
        seen_resolutions = set()
        for f in sorted(video_formats, key=lambda x: x.get('height') or 0, reverse=True):
            height = f.get('height')
            if height and height not in seen_resolutions:
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
                button_text = f"🎬 دانلود کیفیت {f['height']}p ({filesize_mb_str})"
                callback_data = f"dl:prepare:redtube:video_{f.get('format_id', 'best')}:{video_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                seen_resolutions.add(height)
                if len(seen_resolutions) >= 3:
                    break
        
        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")])

        await msg.delete()
        if thumbnail:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                                         reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')