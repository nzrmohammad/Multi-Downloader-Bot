import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

# Regex for YouTube video and playlist URLs
YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
    r"(watch\?v=|embed/|v/|.+\?v=|playlist\?list=)?([^&=%\?]{11,})")

class YoutubeService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(YOUTUBE_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = get_or_create_user(update)
        url = update.message.text

        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        is_playlist = 'playlist' in url
        
        # Premium check for playlists
        if is_playlist and user.subscription_tier not in ['gold', 'platinum']:
            await update.message.reply_text("برای دانلود پلی‌لیست، به اشتراک طلایی یا پلاتینیوم نیاز دارید.")
            return

        await update.message.reply_text("در حال استخراج اطلاعات... لطفاً صبر کنید. 🧐")
        
        try:
            # Extract info without downloading
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': is_playlist}) as ydl:
                info = ydl.extract_info(url, download=False)

            if 'entries' in info:  # It's a playlist
                await update.message.reply_text(f"پلی‌لیست با {len(info['entries'])} ویدیو شناسایی شد.")
                for entry in info['entries'][:10]: # Limit to first 10 for performance
                    video_id = entry.get('id')
                    video_title = entry.get('title', 'Unknown Title')
                    keyboard = [[
                        InlineKeyboardButton(f"🎵 {video_title[:30]}.. (صدا)", callback_data=f"yt:audio:{video_id}"),
                        InlineKeyboardButton(f"🎬 {video_title[:30]}.. (ویدیو)", callback_data=f"yt:video_720:{video_id}")
                    ]]
                    await update.message.reply_text("انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:  # It's a single video
                video_id = info.get('id')
                video_title = info.get('title', 'Unknown Title')
                keyboard = [
                    [InlineKeyboardButton("🎵 بهترین کیفیت صدا (MP3)", callback_data=f"yt:audio:{video_id}")],
                    [InlineKeyboardButton("🎬 ویدیو 720p", callback_data=f"yt:video_720:{video_id}")],
                ]
                await update.message.reply_text(f"کیفیت مورد نظر برای «{video_title}» را انتخاب کنید:", 
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.message.reply_text("خطایی در پردازش لینک یوتیوب رخ داد. لطفاً مطمئن شوید لینک معتبر است.")