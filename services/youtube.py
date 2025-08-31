# services/youtube.py
import re
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config  # <--- وارد کردن کانفیگ برای دسترسی به پراکسی
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
    r"(watch\?v=|embed/|v/|.+\?v=|playlist\?list=)?([^&=%\?]{11,})")

class YoutubeService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(YOUTUBE_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)

        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        is_playlist = 'playlist' in url
        
        if is_playlist and user.subscription_tier not in ['gold', 'platinum', 'diamond']:
            await update.message.reply_text("برای دانلود پلی‌لیست، به اشتراک طلایی یا الماسی نیاز دارید.")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات از یوتیوب... 🧐")
        
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': is_playlist,
                'noplaylist': not is_playlist,
                'ignoreerrors': True,
                'proxy': config.get_random_proxy(),  # <--- استفاده از سیستم پراکسی خودکار
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                await msg.edit_text(
                    "❌ خطایی در دریافت اطلاعات از یوتیوب رخ داد.\n"
                    "این مشکل معمولاً به دلیل محدودیت‌های یوتیوب روی IP سرور است. لطفاً چند دقیقه دیگر دوباره تلاش کنید."
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

                keyboard = []
                keyboard.append([InlineKeyboardButton("🎵 بهترین کیفیت صدا (MP3)", callback_data=f"dl:prepare:youtube:audio:{video_id}")])

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
                
                if thumbnail_url:
                    await msg.delete()
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=thumbnail_url,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                else:
                    await msg.edit_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        except Exception as e:
            await msg.edit_text("خطایی در پردازش لینک یوتیوب رخ داد. لطفاً مطمئن شوید لینک معتبر است.")
            logging.error(f"YouTube processing error: {e}", exc_info=True)