import os
import yt_dlp
from celery import Celery
from telegram import Bot
from database.database import SessionLocal
from database.models import FileCache
from core.user_manager import increment_download_count, log_activity
import config

# --- Celery and Bot Initialization ---

# Initialize Celery and connect it to the Redis broker.
# The broker URL 'redis://redis:6379/0' assumes you are using Docker Compose,
# where 'redis' is the service name of the Redis container.
celery_app = Celery('tasks', broker='redis://redis:6379/0')

# Create a Telegram Bot instance to send messages from within the Celery worker.
bot = Bot(token=config.BOT_TOKEN)


# --- Main Download Task ---

@celery_app.task
def download_task(user_id, url, quality, service, resource_id):
    """
    This Celery task runs in a separate worker process to handle file downloads.
    It downloads the requested media, sends it to the user, caches the file,
    updates user stats, and cleans up the downloaded file.
    """
    filename = None  # Initialize filename to None to ensure it's always defined for the finally block.
    
    try:
        # --- Step 1: Determine the full download URL ---
        if service == 'yt':
            download_url = f"https://www.youtube.com/watch?v={resource_id}"
        elif service == 'sc':
            download_url = f"https://soundcloud.com/tracks/{resource_id}"
        # For services like Deezer, the full URL is already passed in 'url'
        else:
            download_url = url

        # --- Step 2: Configure yt-dlp download options based on requested quality ---
        # A unique filename is created using the resource_id to prevent conflicts between simultaneous downloads.
        if quality == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'%(title)s_{resource_id}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
            }
        else:
            resolution = quality.split('_')[1]
            ydl_opts = {
                'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]',
                'outtmpl': f'%(title)s_{resource_id}.%(ext)s',
                'quiet': True,
            }
        
        # --- Step 3: Download the file using yt-dlp ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(download_url, download=True)
            original_filename = ydl.prepare_filename(info)
            # Ensure the final filename has the correct extension (e.g., .mp3 for audio).
            filename = os.path.splitext(original_filename)[0] + '.mp3' if quality == 'audio' else original_filename

        # --- Step 4: Send the file to the user and get its file_id for caching ---
        with open(filename, 'rb') as file_to_send:
            if quality == 'audio':
                sent_message = bot.send_audio(chat_id=user_id, audio=file_to_send, title=info.get('title'))
                file_id = sent_message.audio.file_id
                file_type = 'audio'
                file_size = sent_message.audio.file_size
            else:
                sent_message = bot.send_video(chat_id=user_id, video=file_to_send, caption=info.get('title'))
                file_id = sent_message.video.file_id
                file_type = 'video'
                file_size = sent_message.video.file_size
        
        # --- Step 5: Save the file info to the cache database ---
        db = SessionLocal()
        new_cache_entry = FileCache(
            original_url=download_url,
            file_id=file_id,
            file_type=file_type,
            file_size=file_size
        )
        db.add(new_cache_entry)
        db.commit()
        db.close()
        
        # --- Step 6: Update user statistics and notify them of success ---
        increment_download_count(user_id)
        log_activity(user_id, 'download', details=service)
        bot.send_message(chat_id=user_id, text="✅ Your download is complete!")

    except Exception as e:
        # --- Error Handling: Notify the user if something goes wrong ---
        print(f"Error in download task for user {user_id}: {e}")
        bot.send_message(chat_id=user_id, text="❌ An unexpected error occurred during your download. Please try again.")
    
    finally:
        # --- Cleanup: Always delete the file from the server after processing ---
        if filename and os.path.exists(filename):
            os.remove(filename)
            print(f"Cleaned up file: {filename}")