import logging
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import config
from services.spotify import SpotifyService 

# --- Initialize APIs ---
# Initialize Spotipy with increased timeout for network stability
auth_manager = SpotifyClientCredentials(client_id=config.SPOTIPY_CLIENT_ID, client_secret=config.SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(
    auth_manager=auth_manager,
    requests_timeout=15,  # Timeout in seconds
    retries=3
)


async def handle_spotify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all callbacks with the 's:' (spotify) prefix."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    command = parts[1]
    item_id = parts[2] if len(parts) > 2 else None
    original_track_id_or_album_id = parts[3] if len(parts) > 3 else None

    try:
        if command == 'd': # download
            from .download_handler import handle_download_callback as general_download_handler
            await general_download_handler(update, context)

        elif command == 'ly': # lyrics
            track_info = sp.track(item_id)
            song_title = track_info['name']
            artist_name = track_info['artists'][0]['name']

            await query.edit_message_caption(caption=f" searching for lyrics of '{song_title}'...")

            # Use a try-except block specifically for the Genius request
            try:
                song = genius.search_song(song_title, artist_name)
            except Exception as e:
                logging.error(f"Genius API error: {e}")
                song = None

            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data=f"s:rs:{item_id}")]]
            if song and song.lyrics:
                lyrics = song.lyrics
                if len(lyrics) > 4000:
                    lyrics = lyrics[:4000] + "\n\n[Lyrics truncated...]"

                caption = f"📜 **Lyrics for {song_title}**:\n\n{lyrics}"
                await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else:
                await query.edit_message_caption(caption=" متاسفانه متن این آهنگ پیدا نشد.", reply_markup=InlineKeyboardMarkup(keyboard))

        elif command == 'va': # view_album
            album_id = item_id
            spotify_service = SpotifyService()
            album_info = sp.album(album_id)
            caption, reply_markup = spotify_service.build_album_panel(album_info)
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.effective_chat.id, photo=album_info['images'][0]['url'],
                                         caption=caption, reply_markup=reply_markup, parse_mode='Markdown')

        elif command == 'vat': # view_album_tracks
            album_id = item_id
            page = int(original_track_id_or_album_id)

            album_info = sp.album(album_id)
            offset = (page - 1) * 10
            tracks_result = sp.album_tracks(album_id, limit=10, offset=offset)

            caption = f"💿 **{album_info['name']}** - Tracks ({offset+1} - {offset+len(tracks_result['items'])}):"
            keyboard = []
            for track in tracks_result['items']:
                keyboard.append([InlineKeyboardButton(f"🎧 {track['name']}", callback_data=f"s:d:{track['id']}")])

            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"s:vat:{album_id}:{page-1}"))
            if tracks_result['next']:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"s:vat:{album_id}:{page+1}"))

            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton("⬅️ Back to Album", callback_data=f"s:reshow_album:{album_id}")])
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif command == 'vr': # view_artist
            artist_info = sp.artist(item_id)
            top_tracks = sp.artist_top_tracks(item_id)
            caption = f"🧑‍🎤 **Artist:** {artist_info['name']}\n\n**Top 5 Tracks:**\n"
            for track in top_tracks['tracks'][:5]:
                caption += f"- `{track['name']}`\n"
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data=f"s:rs:{original_track_id_or_album_id}")]]
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif command == 'reshow_album':
            album_info = sp.album(item_id)
            spotify_service = SpotifyService()
            caption, reply_markup = spotify_service.build_album_panel(album_info)
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.effective_chat.id, photo=album_info['images'][0]['url'],
                                         caption=caption, reply_markup=reply_markup, parse_mode='Markdown')

        elif command == 'c': # close
            await query.message.delete()

        elif command == 'rs': # reshow_track
            spotify_service = SpotifyService()
            await spotify_service.reshow_track_panel(item_id, query.message)

    except BadRequest as e:
        if "message is not modified" not in str(e):
            logging.error(f"Telegram BadRequest in spotify_handler: {e}")
    except Exception as e:
        logging.error(f"Error in spotify_handler: {e}")