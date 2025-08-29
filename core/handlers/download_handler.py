import os
import logging
import yt_dlp
import uuid
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from core.user_manager import get_or_create_user, can_download, increment_download_count, log_activity
from database.database import SessionLocal
from database.models import FileCache
from .spotify_handler import sp

# This is a temporary storage for download info before confirmation
download_requests = {}

# --- Helper function for progress bar ---
def _create_progress_bar(progress: float) -> str:
    """Creates a textual progress bar."""
    bar_length = 10
    filled_length = int(bar_length * progress)
    bar = '▓' * filled_length + '░' * (bar_length - filled_length)
    return f"**[{bar}]**"

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_or_create_user(update)
    parts = query.data.split(':')
    service = parts[0]
    command = parts[1]

    if command == 'd': # Request to download from Spotify
        item_id = parts[2]
        try:
            track_info = sp.track(item_id)
            artist = track_info['artists'][0]['name']
            title = track_info['name']
            duration_ms = track_info['duration_ms']
            estimated_size_mb = (duration_ms / 1000) * 192 / 8 / 1024
            text = f"**{artist} - {title}**\n\n" \
                   f"Estimated Size: ~{estimated_size_mb:.1f} MB"
            request_key = str(uuid.uuid4())
            download_requests[request_key] = {'service': 'spotify', 'quality': 'audio', 'resource_id': item_id, 'user_id': user.user_id}
            keyboard = [
                [InlineKeyboardButton("✅ Checkout", callback_data=f"dl:confirm:{request_key}"),
                 InlineKeyboardButton("❌ Cancel", callback_data="dl:cancel")],
                [InlineKeyboardButton("⭐️ Change Quality", callback_data=f"dl:quality:{request_key}")]
            ]
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else:
                await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Error preparing download confirmation: {e}")
            await query.message.edit_text("خطا در آماده‌سازی دانلود.")

    elif command == 'confirm': # Confirmation for Spotify download
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
        
    else: # Direct download request for YouTube/SoundCloud
        dl_info = {'service': service, 'quality': command, 'resource_id': parts[2], 'user_id': user.user_id}
        await start_actual_download(query, user, dl_info, context)

async def start_actual_download(query, user, dl_info, context):
    """
    Handles the actual download process with a progress bar for yt-dlp.
    """
    service = dl_info['service']
    quality = dl_info['quality']
    resource_id = dl_info['resource_id']
    
    if service == 'yt':
        download_url = f"https://www.youtube.com/watch?v={resource_id}"
    elif service == 'sc':
        download_url = resource_id # For soundcloud, the ID is enough
    elif service == 'spotify':
        track_info = sp.track(resource_id)
        search_query = f"{track_info['artists'][0]['name']} - {track_info['name']} official audio"
        download_url = f"ytsearch1:{search_query}"
    else:
        await query.message.edit_text("سرویس دانلود پشتیبانی نمی‌شود.")
        return

    last_update_time = 0
    
    async def progress_hook(d):
        nonlocal last_update_time
        if d['status'] == 'downloading':
            current_time = time.time()
            if current_time - last_update_time > 2:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total_bytes > 0:
                    progress = d['downloaded_bytes'] / total_bytes
                    progress_bar = _create_progress_bar(progress)
                    downloaded_mb = d['downloaded_bytes'] / 1024 / 1024
                    total_mb = total_bytes / 1024 / 1024
                    text = (f"**در حال دانلود از سرور...**\n\n"
                            f"{progress_bar} {progress:.0%}\n\n"
                            f"`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`")
                    try:
                        await query.message.edit_caption(caption=text, parse_mode='Markdown')
                    except BadRequest:
                        await query.message.edit_text(text, parse_mode='Markdown')
                    last_update_time = current_time
    
    try:
        await query.message.edit_caption(caption="✅ درخواست تایید شد. در حال اتصال به سرور...")
    except BadRequest:
        await query.message.edit_text(text="✅ درخواست تایید شد. در حال اتصال به سرور...")
    
    ydl_opts_base = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0'},
        'progress_hooks': [progress_hook],
    }
    
    filename = None
    try:
        ydl_opts = {**ydl_opts_base, 'format': 'bestaudio/best', 
                    'outtmpl': f'%(title)s_{resource_id}.%(ext)s', 
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(download_url, download=True)
            if '_type' in info and info['_type'] == 'playlist':
                info = info['entries'][0]

            original_filename = ydl.prepare_filename(info)
            filename = os.path.splitext(original_filename)[0] + '.mp3'
        
        try:
            await query.message.edit_caption(caption="فایل شما دانلود شد. در حال آپلود به تلگرام... 🚀")
        except BadRequest:
            await query.message.edit_text("فایل شما دانلود شد. در حال آپلود به تلگرام... 🚀")
        
        with open(filename, 'rb') as file_to_send:
            final_track_info = sp.track(resource_id) if service == 'spotify' else info
            
            title = final_track_info.get('title') or final_track_info.get('name')
            artist = final_track_info.get('uploader') or (final_track_info.get('artists') and final_track_info['artists'][0]['name'])
            duration = final_track_info.get('duration', 0)
            duration_str = time.strftime('%M:%S', time.gmtime(duration))
            filesize_mb = os.path.getsize(filename) / 1024 / 1024
            quality_abr = final_track_info.get('abr', 128)

            caption = (
                f"🎧 **{title}**\n"
                f"👤 **{artist}**\n\n"
                f"▪️ **کیفیت:** `MP3 - ~{quality_abr}kbps`\n"
                f"▪️ **حجم:** `{filesize_mb:.2f} MB`\n"
                f"▪️ **مدت زمان:** `{duration_str}`"
            )

            await context.bot.send_audio(
                chat_id=user.user_id,
                audio=file_to_send,
                caption=caption,
                title=title,
                performer=artist,
                duration=int(duration),
                parse_mode='Markdown'
            )

        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download', details=f"{service}:{quality}:{resource_id}")
        await query.message.delete()

    except Exception as e:
        logging.error(f"Actual download error: {e}", exc_info=True)
        error_message = "❌ متاسفانه در هنگام دانلود مشکلی پیش آمد."
        try:
            await query.message.edit_caption(caption=error_message)
        except BadRequest:
            await query.message.edit_text(error_message)
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)