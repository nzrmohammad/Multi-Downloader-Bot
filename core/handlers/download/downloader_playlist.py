# core/handlers/download/downloader_playlist.py
import os
import logging
import uuid
import asyncio
import shutil
import yt_dlp
from telegram import Update  # <--- این خط اضافه شد
from telegram.ext import ContextTypes

import config
from core import user_manager
from database.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def handle_playlist_zip_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پلی‌لیست‌ها را به صورت فایل فشرده (ZIP) دانلود می‌کند."""
    query = update.callback_query
    await query.answer()
    
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        if not user_manager.can_download(user) or user.subscription_tier not in ['gold', 'diamond']:
            await query.edit_message_text("برای این کار به اشتراک طلایی یا الماسی نیاز دارید.")
            return

    playlist_id = query.data.split(':')[2]
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    download_path = os.path.join('downloads', str(uuid.uuid4()))
    os.makedirs(download_path, exist_ok=True)
    
    await query.edit_message_text("در حال آماده‌سازی برای دانلود پلی‌لیست...")

    zip_filepath = None
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'quiet': True,
            'ignoreerrors': True,
            'proxy': config.get_random_proxy(),
        }

        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(playlist_url, download=True)
            )
        
        playlist_title = info.get('title', playlist_id)
        safe_playlist_title = "".join([c for c in playlist_title if c.isalnum() or c==' ']).rstrip()
        zip_filename = f"{safe_playlist_title}.zip"
        zip_filepath = os.path.join('downloads', safe_playlist_title)

        downloaded_count = len([entry for entry in info.get('entries', []) if entry])
        await query.edit_message_text(f"دانلود {downloaded_count} فایل کامل شد. در حال فشرده‌سازی...")

        await loop.run_in_executor(
            None, lambda: shutil.make_archive(zip_filepath, 'zip', download_path)
        )
        
        zip_filepath_final = f"{zip_filepath}.zip"

        await query.edit_message_text("فایل فشرده شد. در حال آپلود...")

        with open(zip_filepath_final, 'rb') as zf:
            await context.bot.send_document(
                chat_id=user.user_id,
                document=zf,
                filename=zip_filename,
                caption=f"📦 پلی‌لیست صوتی: {playlist_title}"
            )
        
        await query.message.delete()
        async with AsyncSessionLocal() as session:
            user_to_update = await session.get(type(user), user.user_id)
            await user_manager.increment_download_count(session, user_to_update)
            await user_manager.log_activity(session, user_to_update, 'download_playlist', details=f"youtube_zip:{playlist_id}")

    except Exception as e:
        logger.error(f"Error creating playlist zip: {e}", exc_info=True)
        await query.edit_message_text("❌ خطایی در هنگام ساخت فایل ZIP رخ داد.")
    finally:
        if os.path.exists(download_path):
            shutil.rmtree(download_path)
        if zip_filepath and os.path.exists(f"{zip_filepath}.zip"):
            os.remove(f"{zip_filepath}.zip")