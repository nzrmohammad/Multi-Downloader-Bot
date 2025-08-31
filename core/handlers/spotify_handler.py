# core/handlers/spotify_handler.py

import logging
import spotipy
import requests
from requests.adapters import HTTPAdapter, Retry
from musicxmatch_api import MusixMatchAPI
from spotipy.oauth2 import SpotifyClientCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import config
from core.settings import settings 
from services.spotify import SpotifyService 

def create_spotify_session() -> spotipy.Spotify:
    """
    یک نمونه Spotipy با یک session سفارشی ایجاد می‌کند که شامل چرخش پراکسی و تلاش مجدد است.
    """
    session = requests.Session()
    
    proxy = config.get_random_proxy()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    auth_manager = SpotifyClientCredentials(
        client_id=settings.SPOTIPY_CLIENT_ID, 
        client_secret=settings.SPOTIPY_CLIENT_SECRET
        # FIX: The 'session' argument is removed from here as it's not a valid parameter.
    )
    
    # FIX: The custom 'session' is correctly passed to the main Spotify client here.
    return spotipy.Spotify(
        auth_manager=auth_manager,
        requests_timeout=15,
        retries=3,
        session=session
    )

sp = create_spotify_session()
mxm_api = MusixMatchAPI() 

async def handle_spotify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """تمام درخواست‌های مربوط به اسپاتیفای را مدیریت می‌کند."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    command = parts[1]
    item_id = parts[2] if len(parts) > 2 else None
    original_item_id = parts[3] if len(parts) > 3 else None

    try:
        if command == 'ly':
            track_info = sp.track(item_id)
            song_title = track_info['name']
            artist_name = track_info['artists'][0]['name']

            keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"s:rs:{item_id}")]]
            await query.edit_message_caption(caption=f"در حال جستجوی متن آهنگ '{song_title}'...")

            lyrics = None
            try:
                search_query = f"{artist_name} {song_title}"
                search_result = mxm_api.search_tracks(search_query)
                
                if search_result['message']['header']['status_code'] == 200 and search_result['message']['body']['track_list']:
                    track_id = search_result['message']['body']['track_list'][0]['track']['track_id']
                    lyrics_result = mxm_api.get_track_lyrics(track_id=track_id)
                    if lyrics_result['message']['header']['status_code'] == 200:
                        lyrics_body = lyrics_result['message']['body']['lyrics']['lyrics_body']
                        lyrics = lyrics_body.split("*******")[0].strip()
            except Exception as e:
                logging.error(f"Musixmatch API error for '{song_title}': {e}")
                lyrics = None

            if lyrics:
                full_lyrics_message = f"📜 **متن آهنگ {song_title}**:\n\n{lyrics}"
                if len(full_lyrics_message) > 4096:
                    full_lyrics_message = full_lyrics_message[:4090] + "\n[...]"
                
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=full_lyrics_message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_caption(caption="متاسفانه متن این آهنگ پیدا نشد.", reply_markup=InlineKeyboardMarkup(keyboard))

        elif command == 'va':
            album_id = item_id
            spotify_service = SpotifyService()
            album_info = sp.album(album_id)
            caption, reply_markup = spotify_service.build_album_panel(album_info)
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=album_info['images'][0]['url'],
                                         caption=caption, reply_markup=reply_markup, parse_mode='Markdown')

        elif command == 'vat':
            album_id = item_id
            page = int(original_item_id)
            album_info = sp.album(album_id)
            offset = (page - 1) * 10
            tracks_result = sp.album_tracks(album_id, limit=10, offset=offset)
            caption = f"💿 **{album_info['name']}** - آهنگ‌ها ({offset+1} - {offset+len(tracks_result['items'])}):"
            keyboard = []
            for track in tracks_result['items']:
                keyboard.append([InlineKeyboardButton(f"🎧 {track['name']}", callback_data=f"dl:prepare:spotify:audio:{track['id']}")])

            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"s:vat:{album_id}:{page-1}"))
            if tracks_result['next']:
                nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"s:vat:{album_id}:{page+1}"))
            
            if nav_buttons: keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton("⬅️ بازگشت به آلبوم", callback_data=f"s:reshow_album:{album_id}")])
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif command == 'vr':
            artist_id = item_id
            track_id_for_back_button = original_item_id
            artist_info = sp.artist(artist_id)
            top_tracks = sp.artist_top_tracks(artist_id)
            
            caption = f"🧑‍🎤 **هنرمند:** {artist_info['name']}\n\n**۵ آهنگ برتر:**\n"
            caption += "\n".join([f"- `{track['name']}`" for track in top_tracks['tracks'][:5]])

            keyboard = [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"s:rs:{track_id_for_back_button}")]]
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif command == 'reshow_album':
            album_info = sp.album(item_id)
            spotify_service = SpotifyService()
            caption, reply_markup = spotify_service.build_album_panel(album_info)
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=album_info['images'][0]['url'],
                                         caption=caption, reply_markup=reply_markup, parse_mode='Markdown')

        elif command == 'c':
            await query.message.delete()

        elif command == 'rs':
            spotify_service = SpotifyService()
            track_info = sp.track(item_id)
            caption, reply_markup = spotify_service.build_track_panel(track_info)
            try:
                await query.message.delete()
            except Exception:
                pass 
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=track_info['album']['images'][0]['url'],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except BadRequest as e:
        if "message is not modified" not in str(e):
            logging.warning(f"Telegram BadRequest in spotify_handler: {e}")
    except Exception as e:
        logging.error(f"Error in spotify_handler: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=query.message.chat_id, text="❌ خطایی رخ داد. لطفا دوباره تلاش کنید.")
        except Exception as inner_e:
            logging.error(f"Could not send error message to user: {inner_e}")