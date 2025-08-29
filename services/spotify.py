# services/spotify.py

import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes

import config
from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

SPOTIFY_URL_PATTERN = re.compile(r"https://open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)")

class SpotifyService(BaseService):
    def __init__(self):
        auth_manager = SpotifyClientCredentials(client_id=config.SPOTIPY_CLIENT_ID, client_secret=config.SPOTIPY_CLIENT_SECRET)
        self.sp = spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=15,
            retries=3
        )

    async def can_handle(self, url: str) -> bool:
        return re.match(SPOTIFY_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        match = re.match(SPOTIFY_URL_PATTERN, url)
        link_type, item_id = match.groups()

        await update.message.delete()
        processing_message = await context.bot.send_message(chat_id=update.effective_chat.id, text="در حال پردازش لینک اسپاتیفای... 🕵️")

        try:
            if link_type == 'track':
                track_info = self.sp.track(item_id)
                caption, reply_markup = self.build_track_panel(track_info)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=track_info['album']['images'][0]['url'],
                    caption=caption, reply_markup=reply_markup, parse_mode='Markdown'
                )
            elif link_type == 'album':
                album_info = self.sp.album(item_id)
                caption, reply_markup = self.build_album_panel(album_info)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=album_info['images'][0]['url'],
                    caption=caption, reply_markup=reply_markup, parse_mode='Markdown'
                )
            await processing_message.delete()
        except Exception as e:
            await processing_message.edit_text(f"مشکلی در پردازش لینک اسپاتیفای پیش آمد: {e}")

    def build_track_panel(self, track_info: dict):
        track_id = track_info['id']
        title = track_info['name']
        artists = ', '.join([artist['name'] for artist in track_info['artists']])
        album_name = track_info['album']['name']
        release_date = track_info['album']['release_date']
        isrc = track_info.get('external_ids', {}).get('isrc', 'N/A')
        album_art_url = track_info['album']['images'][0]['url']
        artist_id = track_info['artists'][0]['id']
        album_id = track_info['album']['id']
        youtube_search_query = f"{artists} - {title} official audio".replace(' ', '+')

        caption = (
            f"🎧 **Title:** `{title}`\n"
            f"🎤 **Artist:** `{artists}`\n"
            f"💽 **Album:** `{album_name}`\n"
            f"🗓 **Release Date:** `{release_date}`\n"
            f"❗️ **Is Local:** `False`\n"
            f"🌐 **ISRC:** `{isrc}`\n\n"
            f"Track id: `{track_id}`"
        )

        keyboard = [
            [InlineKeyboardButton("📜 View Lyrics", callback_data=f"s:ly:{track_id}")],
            [InlineKeyboardButton("⬇️ Download Track", callback_data=f"s:d:{track_id}")],
            [InlineKeyboardButton("🖼 Download Image", url=album_art_url)],
            [InlineKeyboardButton("📀 View Album", callback_data=f"s:va:{album_id}:{track_id}")],
            [InlineKeyboardButton("🧑‍🎤 View Artist", callback_data=f"s:vr:{artist_id}:{track_id}")],
            [InlineKeyboardButton("🎵 Listen on Spotify", url=track_info['external_urls']['spotify']),
             InlineKeyboardButton("📺 Watch on YouTube", url=f"https://www.youtube.com/results?search_query={youtube_search_query}")],
            [InlineKeyboardButton("❌ Close", callback_data="s:c")]
        ]
        return caption, InlineKeyboardMarkup(keyboard)

    def build_album_panel(self, album_info: dict):
        album_id = album_info.get('id')
        album_name = album_info.get('name', 'N/A')
        artists = ', '.join([artist.get('name', 'N/A') for artist in album_info.get('artists', [])])
        total_tracks = album_info.get('total_tracks', 'N/A')
        release_date = album_info.get('release_date', 'N/A')

        caption = (f"📀 **Album:** `{album_name}`\n"
                   f"👥 **Artists:** `{artists or 'N/A'}`\n"
                   f"🎶 **Total tracks:** `{total_tracks}`\n"
                   f"📅 **Published on:** `{release_date}`")

        keyboard = [
            [InlineKeyboardButton("🖼 Download Album Image!", url=album_info.get('images', [{}])[0].get('url', ''))],
            [InlineKeyboardButton("👀 View Album Track's!", callback_data=f"s:vat:{album_id}:1")],
        ]

        # Safely add the "View Artist" button only if artist info is available
        if album_info.get('artists'):
            artist_id = album_info['artists'][0].get('id')
            if artist_id:
                keyboard.append([InlineKeyboardButton("🧑‍🎤 View Album Artist's!", callback_data=f"s:vr:{artist_id}:{album_id}")])

        keyboard.append([
            InlineKeyboardButton("🎵 Listen On Spotify", url=album_info.get('external_urls', {}).get('spotify', '')),
            InlineKeyboardButton("❌ Close", callback_data="s:c")
        ])
        
        return caption, InlineKeyboardMarkup(keyboard)

    async def reshow_track_panel(self, track_id: str, message: Message):
        track_info = self.sp.track(track_id)
        caption, reply_markup = self.build_track_panel(track_info)
        await message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode='Markdown')