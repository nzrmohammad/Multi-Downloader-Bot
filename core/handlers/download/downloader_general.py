# core/handlers/download/downloader_general.py

import os
import logging
import yt_dlp
import uuid
import time
import asyncio
from telegram.ext import ContextTypes
from yt_dlp.utils import DownloadError

import config
from core.settings import settings
from core.handlers import user_manager
from core.log_forwarder import forward_download_to_log_channel
from core.utils import create_progress_bar, edit_message_safe
from database.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def start_actual_download(query, user, dl_info, context):
    """منطق اصلی دانلود از سرویس‌های عمومی با استفاده از yt-dlp."""
    if not user_manager.can_download(user): # <--- افزودن پیشوند
        await edit_message_safe(query, "شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕", query.message.photo)
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
    }
    download_url = url_map.get(service, resource_id)

    last_update_time = [0]
    loop = asyncio.get_running_loop()
    file_size_limit = user_manager.get_file_size_limit(user) # <--- افزودن پیشوند

    async def progress_hook(d):
        current_time = time.time()
        if d['status'] == 'downloading' and current_time - last_update_time[0] > 2:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_bytes > file_size_limit:
                raise DownloadError(f"File size exceeds the {file_size_limit / 1024**3}GB limit for your plan.")

            if total_bytes > 0:
                progress = d['downloaded_bytes'] / total_bytes
                progress_bar = create_progress_bar(progress)
                downloaded_mb = d['downloaded_bytes'] / 1024 / 1024
                total_mb = total_bytes / 1024 / 1024
                text = (f"**در حال دانلود از سرور...**\n\n"
                        f"{progress_bar} {progress:.0%}\n\n"
                        f"`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`")
                await edit_message_safe(query, text, query.message.photo)
                last_update_time[0] = current_time

    await edit_message_safe(query, "✅ درخواست تایید شد. در حال اتصال به سرور...", query.message.photo)

    ydl_opts_base = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'legacy_server_connect': True,
        'progress_hooks': [lambda d: asyncio.run_coroutine_threadsafe(progress_hook(d), loop)],
        'outtmpl': f'downloads/%(title)s_{uuid.uuid4()}.%(ext)s',
        'proxy': config.get_random_proxy(),
        'socket_timeout': 300,
    }

    if settings.INSTAGRAM_PASSWORD and service == 'youtube':
        ydl_opts_base['cookiefile'] = "cookies.txt" 
        logger.info("Using YouTube cookies file for download.")

    filename = None
    try:
        if 'video' in quality_info:
            format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if '_' in quality_info and quality_info.split('_')[1] not in ['hd', 'best']:
                 format_id = quality_info.split('_')[1]
                 format_selector = f"bestvideo[format_id={format_id}]+bestaudio/best"
            ydl_opts = {**ydl_opts_base, 'format': format_selector}
        else: # Audio
            ydl_opts = {**ydl_opts_base, 'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}

        os.makedirs('downloads', exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(download_url, download=True)
            )
            original_filename = ydl.prepare_filename(info)
            if 'audio' in quality_info:
                filename = os.path.splitext(original_filename)[0] + '.mp3'
            else:
                filename = original_filename

        await edit_message_safe(query, "فایل شما دانلود شد. در حال آپلود به تلگرام... 🚀", query.message.photo)
        
        final_caption = info.get('title', 'Downloaded File')
        async with AsyncSessionLocal() as session:
            if 'audio' in quality_info:
                sent_message = await context.bot.send_audio(
                    chat_id=user.user_id, audio=open(filename, 'rb'), filename=os.path.basename(filename),
                    caption=final_caption, title=info.get('track'), performer=info.get('artist')
                )
            else:
                sent_message = await context.bot.send_video(
                    chat_id=user.user_id, video=open(filename, 'rb'), filename=os.path.basename(filename),
                    caption=final_caption, supports_streaming=True
                )
        
            await user_manager.increment_download_count(session, user) # <--- افزودن پیشوند
            await user_manager.log_activity(session, user, 'download', details=f"{service}:{quality_info}") # <--- افزودن پیشوند
        await forward_download_to_log_channel(context, user, sent_message, service, download_url)
        await query.message.delete()

    except DownloadError as e:
        logger.error(f"yt-dlp download error: {e}", exc_info=True)
        error_message = f"❌ دانلود ممکن نیست. محتوا ممکن است خصوصی، حذف شده یا برای منطقه شما در دسترس نباشد.\n`{e}`"
        await edit_message_safe(query, f"{original_caption}\n\n{error_message}", query.message.photo)
    except Exception as e:
        logger.error(f"Actual download error: {e}", exc_info=True)
        error_message = "❌ یک خطای پیش‌بینی نشده در هنگام دانلود رخ داد."
        await edit_message_safe(query, f"{original_caption}\n\n{error_message}", query.message.photo)
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)