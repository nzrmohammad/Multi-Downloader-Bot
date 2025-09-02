# services/youtube.py
import re
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService
from core.handlers.user_manager import get_or_create_user, can_download

YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
    r"("
    r"(?:watch\?v=|embed/|v/|shorts/|.+\?v=)?(?:[^&=%\?]{11,})|"  # Video
    r"playlist\?list=[^&=%\?]+|"  # Playlist
    r"(?:c/|channel/|@)[^/\?&]+"  # Channel (all formats)
    r")"
)

class YoutubeService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(YOUTUBE_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        is_channel = bool(re.search(r"/(c/|channel/|@)", url))
        is_playlist = 'playlist?list=' in url

        if is_playlist and user.subscription_tier not in ['gold', 'diamond']:
            await update.message.reply_text("برای دانلود پلی‌لیست، به اشتراک طلایی یا الماسی نیاز دارید.")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از یوتیوب... 🧐")
        
        if is_channel:
            await self.handle_channel_link(msg, context, user, url)
            return

        ydl_opts = {
            'extract_flat': is_playlist,
            'noplaylist': not is_playlist,
            'ignoreerrors': True,
        }
        
        info = await self._extract_info_ydl(url, ydl_opts)

        if not info:
            await msg.edit_text(
                "❌ اطلاعات دریافت نشد. ممکن است ویدیو خصوصی، حذف شده باشد یا محدودیت سنی داشته باشد (و کوکی‌ها نامعتبر باشند)."
            )
            return

        if 'entries' in info and info.get('entries'):  # Playlist
            playlist_title = info.get('title', 'Playlist')
            num_entries = info.get('playlist_count', len(info['entries']))
            text = (f"**پلی‌لیست:** `{playlist_title}`\n"
                    f"**تعداد ویدیوها:** `{num_entries}`\n\n"
                    "لطفا نحوه دانلود را انتخاب کنید:")
            playlist_id = info.get('id')
            keyboard = [
                [InlineKeyboardButton("📦 دانلود همه (ZIP صوتی)", callback_data=f"yt:playlist_zip:{playlist_id}")],
            ]
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        else:  # Single video
            video_id = info.get('id')
            video_title = info.get('title', 'Unknown Title')
            thumbnail_url = info.get('thumbnail')
            duration = info.get('duration_string', 'N/A')
            uploader = info.get('uploader', 'N/A')

            caption = (
                f"**{video_title}**\n\n"
                f"👤 **Uploader:** {uploader}\n"
                f"⏳ **Duration:** {duration}\n\n"
                f"لطفا کیفیت مورد نظر را انتخاب کنید:"
            )

            keyboard = [[InlineKeyboardButton("🎵 بهترین کیفیت صدا (MP3)", callback_data=f"dl:prepare:youtube:audio:{video_id}")]]
            video_formats = [f for f in info.get('formats', []) if f.get('ext') == 'mp4' and f.get('vcodec') != 'none']
            
            seen_resolutions = set()
            unique_formats = []
            for f in sorted(video_formats, key=lambda x: x.get('height', 0), reverse=True):
                if f.get('height') and f.get('height') not in seen_resolutions:
                    unique_formats.append(f)
                    seen_resolutions.add(f['height'])
            
            for f in unique_formats[:3]:
                filesize = f.get('filesize') or f.get('filesize_approx', 0)
                filesize_mb_str = f"~{filesize / 1024 / 1024:.0f}MB" if filesize > 0 else ""
                button_text = f"🎬 ویدیو {f['height']}p ({filesize_mb_str})"
                callback_data = f"dl:prepare:youtube:video_{f['format_id']}:{video_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            await msg.delete()
            if thumbnail_url:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=thumbnail_url,
                    caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
                )
            else:
                await msg.edit_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def handle_channel_link(self, msg, context, user, url: str):
        """لیست پلی‌لیست‌های یک کانال را استخراج و نمایش می‌دهد."""
        await msg.edit_text("در حال استخراج لیست پلی‌لیست‌های کانال... (این فرآیند ممکن است کمی طول بکشد)")
        
        ydl_opts = {'extract_flat': True, 'noplaylist': False, 'playlistend': 50}
        info = await self._extract_info_ydl(url, ydl_opts)

        # --- FIX: بهبود بررسی خطا ---
        if not info:
            await msg.edit_text("❌ استخراج اطلاعات از کانال ناموفق بود.\n\n"
                              "**راه حل:** لطفاً از معتبر بودن کوکی یوتیوب خود (`cookies.txt`) اطمینان حاصل کنید.")
            return

        playlists = [entry for entry in info.get('entries', []) if entry and entry.get('ie_key') == 'YoutubePlaylist']
        
        if not playlists:
            await msg.edit_text("❌ این کانال هیچ پلی‌لیست عمومی ندارد یا دسترسی به آن ممکن نیست.")
            return

        channel_name = info.get('uploader', 'کانال یوتیوب')
        context.bot_data[f"yt_pls_{msg.chat.id}"] = playlists
        
        text = f"**کانال:** `{channel_name}`\n\nلطفاً پلی‌لیست مورد نظر را برای دانلود انتخاب کنید (صفحه ۱):"
        keyboard = self.build_playlist_keyboard(playlists, chat_id=msg.chat.id, page=1)
        await msg.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    def build_playlist_keyboard(self, playlists: list, chat_id: int, page: int = 1, per_page: int = 10) -> InlineKeyboardMarkup:
        """دکمه‌های صفحه‌بندی شده برای لیست پلی‌لیست‌های کانال را ایجاد می‌کند."""
        start = (page - 1) * per_page
        end = start + per_page
        
        buttons = []
        for pl in playlists[start:end]:
            buttons.append([InlineKeyboardButton(f"📁 {pl['title']}", callback_data=f"yt:playlist_zip:{pl['id']}")])
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"yt_channel:page:{page - 1}:{chat_id}"))
        if end < len(playlists):
            nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"yt_channel:page:{page + 1}:{chat_id}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
            
        return InlineKeyboardMarkup(buttons)