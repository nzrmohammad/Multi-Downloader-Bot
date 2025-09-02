# core/handlers/download/downloader_spotify.py
import os
import logging
import uuid
import time
import asyncio
import shutil
import subprocess
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from telegram.ext import ContextTypes

import config
from core.settings import settings
from core import user_manager # <--- تغییر در این خط
from core.log_forwarder import forward_download_to_log_channel
from core.utils import edit_message_safe
from database.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def handle_spotify_download(query, user, track_id, context, original_caption):
    """
    یک آهنگ اسپاتیفای را با استفاده از آخرین نسخه spotdl دانلود می‌کند.
    """
    if not user_manager.can_download(user): # <--- افزودن پیشوند
        await edit_message_safe(query, "شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕", query.message.photo)
        return
        
    await edit_message_safe(query, "✅ درخواست تایید شد. در حال اتصال به سرورهای موسیقی...", query.message.photo)

    download_path = f"downloads/{uuid.uuid4()}"
    os.makedirs(download_path, exist_ok=True)
    filename = None
    
    try:
        auth_manager = SpotifyClientCredentials(
            client_id=settings.SPOTIPY_CLIENT_ID,
            client_secret=settings.SPOTIPY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        track_info = sp.track(track_id)
        
        title = track_info['name']
        artists = ', '.join([artist['name'] for artist in track_info['artists']])
        album_name = track_info['album']['name']
        release_date = track_info['album']['release_date']
        duration_ms = track_info['duration_ms']
        
        safe_title = "".join([c for c in title if c.isalnum() or c in " ._"]).rstrip()
        safe_artists = "".join([c for c in artists if c.isalnum() or c in " ._"]).rstrip()
        clean_filename_base = f"{safe_artists} - {safe_title}"
        
        spotify_url = f"https://open.spotify.com/track/{track_id}"

        command = [
            "spotdl", "download", spotify_url,
            "--output", f"{download_path}/{clean_filename_base}.{{output-ext}}",
            "--log-level", "ERROR",
            "--headless",
            "--no-cache"
        ]
        
        proxy = config.get_random_proxy()
        if proxy:
            command.extend(["--proxy", proxy])

        if settings.INSTAGRAM_PASSWORD and os.path.exists("cookies.txt"):
            command.extend(["--cookie", "cookies.txt"])

        loop = asyncio.get_running_loop()
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        )

        if process.returncode != 0:
            logger.error(f"spotdl failed. stderr: {process.stderr}")
            raise Exception("سرویس‌دهنده موسیقی قادر به پردازش این لینک نیست.")

        downloaded_files = os.listdir(download_path)
        if not downloaded_files:
            raise Exception("فایل خروجی توسط spotdl ایجاد نشد.")
        
        filename = os.path.join(download_path, downloaded_files[0])
        
        await edit_message_safe(query, "فایل با بالاترین کیفیت دانلود شد. در حال آپلود... 🚀", query.message.photo)
        
        file_size_mb = os.path.getsize(filename) / 1024 / 1024
        duration_str = time.strftime('%M:%S', time.gmtime(duration_ms / 1000))
        
        final_caption = (
            f"🎧 **{title}**\n👤 **{artists}**\n\n"
            f"💽 **آلبوم:** `{album_name}`\n🗓 **تاریخ انتشار:** `{release_date}`\n"
            f"▪️ **حجم:** `{file_size_mb:.2f} MB`\n▪️ **مدت زمان:** `{duration_str}`"
        )

        async with AsyncSessionLocal() as session:
            with open(filename, 'rb') as file_to_send:
                sent_message = await context.bot.send_audio(
                    chat_id=user.user_id, audio=file_to_send,
                    filename=f"{clean_filename_base}.mp3", caption=final_caption,
                    title=title, performer=artists, duration=int(duration_ms / 1000),
                    parse_mode='Markdown'
                )
            await user_manager.increment_download_count(session, user) # <--- افزودن پیشوند
            await user_manager.log_activity(session, user, 'download', details="spotify:audio_hq") # <--- افزودن پیشوند
        
        await forward_download_to_log_channel(context, user, sent_message, "spotify_hq", spotify_url)
        await query.message.delete()

    except Exception as e:
        logger.error(f"خطا در دانلود از اسپاتیفای: {e}", exc_info=True)
        error_message = f"❌ خطای پیش‌بینی نشده در دانلود از اسپاتیفای.\n`{e}`"
        await edit_message_safe(query, f"{original_caption}\n\n{error_message}", query.message.photo)
    finally:
        if os.path.exists(download_path):
            shutil.rmtree(download_path)