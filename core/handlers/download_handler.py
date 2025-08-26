import os
import logging
import yt_dlp
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from core.user_manager import get_or_create_user, can_download, increment_download_count, log_activity
from database.database import SessionLocal
from database.models import FileCache
from .spotify_handler import sp # Import spotipy instance to get track info

# This is a temporary storage for download info before confirmation
download_requests = {}

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_or_create_user(update)
    parts = query.data.split(':')
    service = parts[0]
    command = parts[1]

    if command == 'd': # Request to download
        item_id = parts[2]
        
        try:
            track_info = sp.track(item_id)
            artist = track_info['artists'][0]['name']
            title = track_info['name']
            duration_ms = track_info['duration_ms']
            
            # For simplicity, we assume audio quality and estimate size
            # A more accurate way would be to get info from yt-dlp first
            estimated_size_mb = (duration_ms / 1000) * 192 / 8 / 1024
            
            text = f"**{artist} - {title}**\n\n" \
                   f"Estimated Size: ~{estimated_size_mb:.1f} MB"
            
            # Generate a unique key for this specific request
            request_key = str(uuid.uuid4())
            download_requests[request_key] = {'service': service, 'quality': 'audio', 'resource_id': item_id, 'user_id': user.user_id}
            
            keyboard = [
                [InlineKeyboardButton("✅ Checkout", callback_data=f"dl:confirm:{request_key}"),
                 InlineKeyboardButton("❌ Cancel", callback_data="dl:cancel")],
                [InlineKeyboardButton("⭐️ Change Quality", callback_data=f"dl:quality:{request_key}")]
            ]
            
            # If the original message was a photo with caption (from spotify panel)
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else: # If it was a text message (from album track list)
                await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error preparing download confirmation: {e}")
            await query.message.edit_text("خطا در آماده‌سازی دانلود.")

    elif command == 'confirm':
        request_key = parts[2]
        if request_key not in download_requests or download_requests[request_key]['user_id'] != user.user_id:
            await query.edit_message_caption("این درخواست نامعتبر یا منقضی شده است.")
            return
            
        dl_info = download_requests.pop(request_key)
        await start_actual_download(query, user, dl_info, context)

    elif command == 'cancel':
        await query.message.delete()

    elif command == 'quality':
        await query.answer("این قابلیت در حال توسعه است.", show_alert=True)

async def start_actual_download(query, user, dl_info, context):
    await query.edit_message_caption(caption="✅ درخواست تایید شد. در حال دانلود از سرور...")

    service = dl_info['service']
    quality = dl_info['quality']
    resource_id = dl_info['resource_id']
    
    # We always search on YouTube to download
    track_info = sp.track(resource_id)
    search_query = f"{track_info['artists'][0]['name']} - {track_info['name']} official audio"

    ydl_opts_base = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }
    
    filename = None
    try:
        ydl_opts = {**ydl_opts_base, 'format': 'bestaudio/best', 
                    'outtmpl': f'%(title)s_{resource_id}.%(ext)s', 
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search and download the first result
            info = ydl.extract_info(f"ytsearch:{search_query}", download=True)['entries'][0]
            original_filename = ydl.prepare_filename(info)
            filename = os.path.splitext(original_filename)[0] + '.mp3'

        await query.edit_message_caption(caption="فایل شما با موفقیت دانلود شد. در حال آپلود به تلگرام...")
        
        with open(filename, 'rb') as file_to_send:
            await context.bot.send_audio(
                chat_id=user.user_id,
                audio=file_to_send,
                title=track_info.get('name'),
                performer=track_info['artists'][0]['name'],
                thumbnail=open(filename, 'rb') # Placeholder, need to download thumbnail separately
            )

        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download', details=f"spotify:{quality}:{resource_id}")
        await query.message.delete()

    except Exception as e:
        logging.error(f"Actual download error: {e}")
        await query.edit_message_caption(caption="❌ متاسفانه در هنگام دانلود مشکلی پیش آمد.")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)