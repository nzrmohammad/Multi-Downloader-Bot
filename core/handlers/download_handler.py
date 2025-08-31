import os
import logging
import yt_dlp
import uuid
import time
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TRCK
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from core.user_manager import get_or_create_user, can_download, increment_download_count, log_activity
from .spotify_handler import sp
from core.log_forwarder import forward_download_to_log_channel
import zipfile
import shutil

# حافظه موقت برای ذخیره درخواست‌های دانلود قبل از تایید نهایی
download_requests = {}
logger = logging.getLogger(__name__) # <--- حل خطای logger

# --- تابع کمکی برای نوار پیشرفت ---
def _create_progress_bar(progress: float) -> str:
    """یک نوار پیشرفت متنی گرافیکی ایجاد می‌کند."""
    bar_length = 10
    filled_length = int(bar_length * progress)
    bar = '▓' * filled_length + '░' * (bar_length - filled_length)
    return f"**[{bar}]**"


# ✨ تابع جدید برای افزودن تگ‌های ID3
def _add_id3_tags(filename: str, info: dict):
    """تگ‌های متادیتا و کاور آرت را به فایل MP3 اضافه می‌کند."""
    try:
        audio = MP3(filename, ID3=ID3)
        # افزودن تگ‌های ساده
        if info.get('title'):
            audio.tags.add(TIT2(encoding=3, text=info['title']))
        if info.get('artist'):
            audio.tags.add(TPE1(encoding=3, text=info['artist']))
        if info.get('album'):
            audio.tags.add(TALB(encoding=3, text=info.get('album', 'N/A')))
        if info.get('track_number'):
            audio.tags.add(TRCK(encoding=3, text=str(info.get('track_number', 1))))

        # افزودن کاور آرت
        if info.get('thumbnail'):
            try:
                response = requests.get(info['thumbnail'], timeout=15)
                if response.status_code == 200:
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,  # 3 is for the front cover
                            desc='Cover',
                            data=response.content
                        )
                    )
            except Exception as e:
                logging.warning(f"Could not download or add thumbnail: {e}")
        
        audio.save()
        logging.info(f"Successfully added ID3 tags to {filename}")
    except Exception as e:
        logging.error(f"Failed to add ID3 tags to {filename}: {e}", exc_info=True)


async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تمام درخواست‌های دانلود از طریق دکمه‌ها را مدیریت می‌کند.
    """
    query = update.callback_query
    await query.answer()

    user = get_or_create_user(update)
    parts = query.data.split(':')
    
    prefix = parts[0]
    command = parts[1]

    # --- مرحله ۱: آماده‌سازی برای تایید نهایی ---
    if command == 'prepare':
        # data format: dl:prepare:service_name:quality_info:resource_id
        service = parts[2]
        quality_info = parts[3]
        resource_id = parts[4]

        # ایجاد یک کلید یکتا برای این درخواست
        request_key = str(uuid.uuid4())
        download_requests[request_key] = {
            'service': service,
            'quality': quality_info,
            'resource_id': resource_id,
            'user_id': user.user_id,
            'original_message_caption': query.message.caption or query.message.text
        }

        keyboard = [
            [InlineKeyboardButton("✅ بله، دانلود کن", callback_data=f"dl:confirm:{request_key}")],
            [InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")]
        ]
        
        text = "آیا برای شروع دانلود آماده‌اید؟"
        try:
            if query.message.photo:
                await query.message.edit_caption(caption=f"{query.message.caption}\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else:
                await query.message.edit_text(text=f"{query.message.text}\n\n{text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except BadRequest as e:
            logging.warning(f"Could not edit message for confirmation: {e}")

    # --- مرحله ۲: دریافت تاییدیه و شروع دانلود ---
    elif command == 'confirm':
        request_key = parts[2]
        if request_key not in download_requests or download_requests[request_key]['user_id'] != user.user_id:
            await query.message.edit_text("این درخواست نامعتبر یا منقضی شده است.")
            return
        
        dl_info = download_requests.pop(request_key)
        await start_actual_download(query, user, dl_info, context)

    # --- لغو عملیات ---
    elif command == 'cancel':
        await query.message.delete()


# core/handlers/download_handler.py

import os
import logging
import yt_dlp
import uuid
import time
import requests
import asyncio  # <-- جدید: برای مدیریت کارهای async
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TRCK
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from core.user_manager import get_or_create_user, can_download, increment_download_count, log_activity
from .spotify_handler import sp
from core.log_forwarder import forward_download_to_log_channel

# حافظه موقت برای ذخیره درخواست‌های دانلود قبل از تایید نهایی
download_requests = {}


def _create_progress_bar(progress: float) -> str:
    """یک نوار پیشرفت متنی گرافیکی ایجاد می‌کند."""
    bar_length = 10
    filled_length = int(bar_length * progress)
    bar = '▓' * filled_length + '░' * (bar_length - filled_length)
    return f"**[{bar}]**"


def _add_id3_tags(filename: str, info: dict):
    """تگ‌های متادیتا و کاور آرت را به فایل MP3 اضافه می‌کند."""
    try:
        audio = MP3(filename, ID3=ID3)
        if info.get('track'):
            audio.tags.add(TIT2(encoding=3, text=info['track']))
        if info.get('artist'):
            audio.tags.add(TPE1(encoding=3, text=info['artist']))
        if info.get('album'):
            audio.tags.add(TALB(encoding=3, text=info.get('album', 'N/A')))
        if info.get('track_number'):
            audio.tags.add(TRCK(encoding=3, text=str(info.get('track_number', 1))))

        if info.get('thumbnail'):
            try:
                response = requests.get(info['thumbnail'], timeout=15)
                if response.status_code == 200:
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,  # 3 is for the front cover
                            desc='Cover',
                            data=response.content
                        )
                    )
            except Exception as e:
                logging.warning(f"Could not download or add thumbnail: {e}")
        audio.save()
        logging.info(f"Successfully added ID3 tags to {filename}")
    except Exception as e:
        logging.error(f"Failed to add ID3 tags to {filename}: {e}", exc_info=True)


async def _edit_message_safe(query, text, is_photo, reply_markup=None):
    """یک تابع کمکی برای ویرایش پیام که خطای 'message is not modified' را نادیده می‌گیرد."""
    try:
        if is_photo:
            await query.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.message.edit_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
    except BadRequest as e:
        if "message is not modified" not in str(e):
            logging.warning(f"Could not edit message: {e}")


async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تمام درخواست‌های دانلود از طریق دکمه‌ها را مدیریت می‌کند.
    """
    query = update.callback_query
    await query.answer()

    user = get_or_create_user(update)
    parts = query.data.split(':')
    
    command = parts[1]

    if command == 'prepare':
        service = parts[2]
        quality_info = parts[3]
        resource_id = parts[4]
        request_key = str(uuid.uuid4())
        download_requests[request_key] = {
            'service': service, 'quality': quality_info, 'resource_id': resource_id,
            'user_id': user.user_id, 'original_message_caption': query.message.caption or query.message.text
        }
        keyboard = [
            [InlineKeyboardButton("✅ بله، دانلود کن", callback_data=f"dl:confirm:{request_key}")],
            [InlineKeyboardButton("❌ لغو", callback_data="dl:cancel")]
        ]
        text = "آیا برای شروع دانلود آماده‌اید؟"
        await _edit_message_safe(query, f"{query.message.caption or query.message.text}\n\n{text}", query.message.photo, InlineKeyboardMarkup(keyboard))

    elif command == 'confirm':
        request_key = parts[2]
        if request_key not in download_requests or download_requests[request_key]['user_id'] != user.user_id:
            await query.message.edit_text("این درخواست نامعتبر یا منقضی شده است.")
            return
        dl_info = download_requests.pop(request_key)
        await start_actual_download(query, user, dl_info, context)

    elif command == 'cancel':
        await query.message.delete()


async def start_actual_download(query, user, dl_info, context):
    """
    فرآیند اصلی دانلود را با نوار پیشرفت و افزودن تگ‌های ID3 مدیریت می‌کند.
    """
    if not can_download(user):
        await _edit_message_safe(query, "شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕", query.message.photo)
        return

    service = dl_info.get('service')
    quality_info = dl_info['quality']
    resource_id = dl_info['resource_id']
    original_caption = dl_info.get('original_message_caption', '')
    
    url_map = {
        'youtube': f"https://www.youtube.com/watch?v={resource_id}",
        'twitter': f"https://twitter.com/anyuser/status/{resource_id}",
        'facebook': f"https://www.facebook.com/watch/?v={resource_id}",
        'reddit': f"https://www.reddit.com/comments/{resource_id}",
        'twitch': f"https://www.twitch.tv/videos/{resource_id}" if resource_id.isdigit() else f"https://www.twitch.tv/clips/{resource_id}",
        'pornhub': f"https://www.pornhub.com/view_video.php?viewkey={resource_id}",
        'redtube': f"https://www.redtube.com/{resource_id}",
        'deezer': resource_id 
    }
    download_url = url_map.get(service, resource_id)

    if service == 'spotify':
        track_info = sp.track(resource_id)
        search_query = f"{track_info['artists'][0]['name']} - {track_info['name']} official audio"
        download_url = f"ytsearch1:{search_query}"

    last_update_time = [0]
    
    # **تغییر اصلی**: حلقه رویداد را قبل از شروع دانلود می‌گیریم
    loop = asyncio.get_running_loop()

    # **تغییر اصلی**: تابع hook حالا حلقه را به عنوان آرگومان دریافت می‌کند
    def progress_hook(d, progress_loop):
        current_time = time.time()
        if d['status'] == 'downloading' and current_time - last_update_time[0] > 2:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_bytes > 0:
                progress = d['downloaded_bytes'] / total_bytes
                progress_bar = _create_progress_bar(progress)
                downloaded_mb = d['downloaded_bytes'] / 1024 / 1024
                total_mb = total_bytes / 1024 / 1024
                text = (f"**در حال دانلود از سرور...**\n\n"
                        f"{progress_bar} {progress:.0%}\n\n"
                        f"`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`")
                
                # **تغییر اصلی**: از حلقه‌ای که به تابع پاس داده شده برای اجرای امن کوروتین استفاده می‌کنیم
                asyncio.run_coroutine_threadsafe(
                    _edit_message_safe(query, text, query.message.photo),
                    progress_loop
                )
                last_update_time[0] = current_time

    await _edit_message_safe(query, "✅ درخواست تایید شد. در حال اتصال به سرور...", query.message.photo)
    
    ydl_opts_base = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'legacy_server_connect': True,
        # **تغییر اصلی**: حلقه را با استفاده از lambda به hook پاس می‌دهیم
        'progress_hooks': [lambda d: progress_hook(d, loop)],
        'outtmpl': f'downloads/%(title)s_{uuid.uuid4()}.%(ext)s'
    }
    filename = None
    try:
        if 'video' in quality_info:
            format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if '_' in quality_info and quality_info.split('_')[1] != 'hd':
                 format_id = quality_info.split('_')[1]
                 format_selector = f"{format_id}+bestaudio/best"
            ydl_opts = {**ydl_opts_base, 'format': format_selector}
        else: # Audio
            ydl_opts = {**ydl_opts_base, 'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}

        os.makedirs('downloads', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # **تغییر اصلی**: اجرای دانلود در یک executor جداگانه تا event loop اصلی بلاک نشود
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(download_url, download=True)
            )
            original_filename = ydl.prepare_filename(info)
            if 'audio' in quality_info:
                filename = os.path.splitext(original_filename)[0] + '.mp3'
                # اجرای تگ‌گذاری نیز در executor جداگانه بهتر است تا برنامه مسدود نشود
                await loop.run_in_executor(None, _add_id3_tags, filename, info)
            else:
                filename = original_filename

        await _edit_message_safe(query, "فایل شما دانلود شد. در حال آپلود به تلگرام... 🚀", query.message.photo)
        
        with open(filename, 'rb') as file_to_send:
            final_caption = info.get('title', 'Downloaded File')
            if 'audio' in quality_info:
                sent_message = await context.bot.send_audio(
                    chat_id=user.user_id, audio=file_to_send, filename=os.path.basename(filename),
                    caption=final_caption, title=info.get('track'), performer=info.get('artist')
                )
            else:
                sent_message = await context.bot.send_video(
                    chat_id=user.user_id, video=file_to_send, filename=os.path.basename(filename),
                    caption=final_caption, supports_streaming=True
                )
        
        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download', details=f"{service}:{quality_info}")
        await forward_download_to_log_channel(context, user, sent_message, service, download_url)
        await query.message.delete()

    except Exception as e:
        logging.error(f"Actual download error: {e}", exc_info=True)
        error_message = f"❌ متاسفانه در هنگام دانلود مشکلی پیش آمد."
        await _edit_message_safe(query, f"{original_caption}\n\n{error_message}", query.message.photo)
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

async def handle_playlist_zip_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """یک پلی‌لیست کامل را به صورت فایل ZIP صوتی دانلود و ارسال می‌کند."""
    query = update.callback_query
    await query.answer()
    
    user = get_or_create_user(update)
    if not can_download(user) or user.subscription_tier not in ['gold', 'platinum', 'diamond']:
        await query.edit_message_text("برای این کار به اشتراک طلایی یا الماسی نیاز دارید.")
        return

    playlist_id = query.data.split(':')[2]
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    download_path = os.path.join('downloads', str(uuid.uuid4()))
    os.makedirs(download_path, exist_ok=True)
    
    await query.edit_message_text(f"در حال آماده‌سازی برای دانلود پلی‌لیست...\nاین فرآیند ممکن است بسیار زمان‌بر باشد.")

    zip_filepath = None # اطمینان از تعریف متغیر
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'quiet': True,
            'ignoreerrors': True,
        }

        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(playlist_url, download=True)
            )
        
        playlist_title = info.get('title', playlist_id)
        # جایگزینی کاراکترهای نامعتبر در نام فایل
        safe_playlist_title = "".join([c for c in playlist_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        zip_filename = f"{safe_playlist_title}.zip"
        zip_filepath = os.path.join('downloads', zip_filename)

        downloaded_count = len([entry for entry in info.get('entries', []) if entry])
        await query.edit_message_text(f"دانلود {downloaded_count} فایل کامل شد. در حال فشرده‌سازی...")

        # ساخت فایل ZIP در یک thread جداگانه
        def create_zip():
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(download_path):
                    for file in files:
                        zipf.write(os.path.join(root, file), arcname=file)
        await loop.run_in_executor(None, create_zip)

        await query.edit_message_text("فایل فشرده شد. در حال آپلود...")

        with open(zip_filepath, 'rb') as zf:
            await context.bot.send_document(
                chat_id=user.user_id,
                document=zf,
                filename=zip_filename,
                caption=f"📦 پلی‌لیست صوتی: {playlist_title}"
            )
        
        await query.message.delete()
        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download_playlist', details=f"youtube_zip:{playlist_id}")
        await forward_download_to_log_channel(context, user, query.message, "youtube_zip", playlist_url)

    except Exception as e:
        logger.error(f"Error creating playlist zip for {playlist_id}: {e}", exc_info=True)
        await query.edit_message_text("❌ خطایی در هنگام ساخت فایل ZIP رخ داد.")
    finally:
        if os.path.exists(download_path):
            shutil.rmtree(download_path)
        if zip_filepath and os.path.exists(zip_filepath):
            os.remove(zip_filepath)