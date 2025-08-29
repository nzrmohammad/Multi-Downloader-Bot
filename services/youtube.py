import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

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
        
        if is_playlist and user.subscription_tier not in ['gold', 'platinum']:
            await update.message.reply_text("برای دانلود پلی‌لیست، به اشتراک طلایی یا پلاتینیوم نیاز دارید.")
            return

        await update.message.reply_text("در حال استخراج اطلاعات... لطفاً صبر کنید. 🧐")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': is_playlist}) as ydl:
                info = ydl.extract_info(url, download=False)

            if 'entries' in info:  # Playlist
                await update.message.reply_text(f"پلی‌لیست با {len(info['entries'])} ویدیو شناسایی شد. در حال ارسال گزینه‌های دانلود برای ۱۰ ویدیوی اول...")
                for entry in info['entries'][:10]:
                    video_id = entry.get('id')
                    video_title = entry.get('title', 'Unknown Title')
                    keyboard = [[
                        InlineKeyboardButton(f"🎵 صدا", callback_data=f"yt:audio:{video_id}"),
                        InlineKeyboardButton(f"🎬 ویدیو", callback_data=f"yt:video_720:{video_id}")
                    ]]
                    await update.message.reply_text(f"▶️ {video_title}", reply_markup=InlineKeyboardMarkup(keyboard))
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

                keyboard = [
                    [InlineKeyboardButton("🎵 بهترین کیفیت صدا (MP3)", callback_data=f"yt:audio:{video_id}")],
                    [InlineKeyboardButton("🎬 ویدیو 720p", callback_data=f"yt:video_720:{video_id}")],
                ]
                
                if thumbnail_url:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=thumbnail_url,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text("خطایی در پردازش لینک یوتیوب رخ داد. لطفاً مطمئن شوید لینک معتبر است.")