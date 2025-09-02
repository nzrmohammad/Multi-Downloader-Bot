# services/pornhub.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import can_download

# --- FIX: الگوی جامع برای پشتیبانی از ویدیو، کانال، مدل و پلی‌لیست ---
PORNHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:[a-zA-Z\d-]+\.)?pornhub\.com/(view_video\.php\?viewkey=|embed/|model/|pornstar/|channel/|playlist/)([a-zA-Z0-9_-]+)"
)

class PornhubService(BaseService):
    async def can_handle(self, url: str) -> bool:
        """بررسی می‌کند که آیا لینک مربوط به پورن‌هاب است یا خیر."""
        return re.match(PORNHUB_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        """لینک‌های پورن‌هاب را پردازش می‌کند."""
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال پردازش لینک... 🧐")

        # --- FIX: استخراج لیست ویدیوها بدون دانلود اولیه ---
        # این کار به ما اجازه می‌دهد محتوای کانال‌ها و پلی‌لیست‌ها را نمایش دهیم
        info = await self._extract_info_ydl(url, ydl_opts={'extract_flat': True, 'quiet': True})

        if not info:
            await msg.edit_text("❌ اطلاعات دریافت نشد. ممکن است لینک نامعتبر باشد یا ویدیو حذف شده باشد.")
            return

        # --- FIX: مدیریت لینک‌های کانال، مدل یا پلی‌لیست ---
        if 'entries' in info and info.get('entries'):
            playlist_title = info.get('title', 'Pornhub Selection')
            uploader = info.get('uploader', 'N/A')
            thumbnail = info.get('thumbnail')
            
            caption = (
                f"🔞 **مجموعه:** `{playlist_title}`\n"
                f"👤 **از:** `{uploader}`\n\n"
                f"**تعداد کل ویدیوها:** `{len(info['entries'])}`\n"
                "لطفاً ویدیوی مورد نظر برای دانلود را انتخاب کنید (نمایش ۱۰ ویدیوی اول):"
            )
            
            keyboard = []
            # نمایش ۱۰ ویدیوی اول برای جلوگیری از طولانی شدن لیست
            for entry in info['entries'][:10]:
                video_id = entry.get('id')
                if video_id:
                    keyboard.append([InlineKeyboardButton(f"🎬 {entry.get('title', 'Unknown Video')}", callback_data=f"dl:prepare:pornhub:video_best:{video_id}")])
            
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
            return

        # --- مدیریت لینک تکی ویدیو با اطلاعات کامل‌تر ---
        video_id = info.get('id')
        title = info.get('title', 'Unknown Title')
        thumbnail = info.get('thumbnail')
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'N/A')
        view_count = info.get('view_count', 0)
        
        # --- FIX: استخراج تگ‌ها و دسته‌بندی‌ها ---
        categories = ', '.join(info.get('categories', []))
        tags = ', '.join(info.get('tags', []))
        tags_display = f"`{tags[:150]}...`" if len(tags) > 150 else f"`{tags}`"

        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
        
        caption = (
            f"🔞 **{title}**\n\n"
            f"👤 **کانال/مدل:** `{uploader}`\n"
            f"⏳ **مدت زمان:** `{duration_str}`\n"
            f"👁 **بازدید:** `{view_count:,}`\n"
            f"🗂 **دسته‌بندی:** `{categories}`\n"
            f"🏷 **تگ‌ها:** {tags_display}\n\n"
            "لطفا کیفیت مورد نظر را برای دانلود انتخاب کنید:"
        )

        keyboard = []
        video_formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
        
        seen_resolutions = set()
        # نمایش حداکثر ۳ کیفیت برای سادگی
        for f in sorted(video_formats, key=lambda x: x.get('height') or 0, reverse=True):
            height = f.get('height')
            if height and height not in seen_resolutions:
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
                button_text = f"🎬 دانلود کیفیت {f['height']}p ({filesize_mb_str})"
                callback_data = f"dl:prepare:pornhub:video_{f.get('format_id', 'best')}:{video_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                seen_resolutions.add(height)
                if len(seen_resolutions) >= 3:
                    break
        
        if not seen_resolutions: # اگر هیچ کیفیتی پیدا نشد
             keyboard.append([InlineKeyboardButton("🎬 بهترین کیفیت", callback_data=f"dl:prepare:pornhub:video_best:{video_id}")])

        keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")])

        await msg.delete()
        if thumbnail:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')