import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

SPOTIFY_URL_PATTERN = re.compile(r"https?://open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)")

class SpotifyService(BaseService):
    def __init__(self):
        auth_manager = SpotifyClientCredentials(client_id=config.SPOTIPY_CLIENT_ID, client_secret=config.SPOTIPY_CLIENT_SECRET)
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    async def can_handle(self, url: str) -> bool:
        return re.match(SPOTIFY_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = get_or_create_user(update)
        url = update.message.text
        match = re.match(SPOTIFY_URL_PATTERN, url)
        link_type = match.group(1)

        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        # Premium check for albums/playlists
        if link_type in ['album', 'playlist'] and user.subscription_tier not in ['platinum']:
             await update.message.reply_text("برای دانلود آلبوم یا پلی‌لیست از اسپاتیفای، به اشتراک پلاتینیوم نیاز دارید.")
             return
        
        await update.message.reply_text("در حال پردازش لینک اسپاتیفای... 🕵️")
        
        try:
            # Handle single track
            if link_type == 'track':
                track_info = self.sp.track(url)
                song_name = track_info['name']
                artist_name = track_info['artists'][0]['name']
                search_query = f"{artist_name} - {song_name} Audio"
                await self._search_and_present(search_query, update)
            # Handle album/playlist (simplified)
            else:
                 await update.message.reply_text("در حال استخراج آهنگ‌ها از آلبوم/پلی‌لیست...")
                 # Logic to iterate through tracks and present them one by one
                 
        except Exception as e:
            await update.message.reply_text("مشکلی در پیدا کردن آهنگ شما پیش آمد.")
            
    async def _search_and_present(self, query, update):
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            search_result = ydl.extract_info(f"ytsearch1:{query}", download=False)['entries'][0]
            video_id = search_result.get('id')
            video_title = search_result.get('title', 'Unknown Title')

        keyboard = [[InlineKeyboardButton("🎵 دانلود صدا (MP3)", callback_data=f"yt:audio:{video_id}")]]
        await update.message.reply_text(f"بهترین نتیجه برای «{query}»:\n«{video_title}»\n\nلطفا انتخاب کنید:", 
                                    reply_markup=InlineKeyboardMarkup(keyboard))