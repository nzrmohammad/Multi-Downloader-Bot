import os
import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes
from core.user_manager import get_or_create_user, can_download, increment_download_count, log_activity
from database.database import SessionLocal
from database.models import FileCache

# Note: We are NOT importing from tasks.py anymore

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    # --- This is the new, direct download logic ---
    user = get_or_create_user(update)
    data = query.data.split(':')
    service, quality, resource_id = data

    if not can_download(user):
        await query.edit_message_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
        return

    # Determine URL based on service
    if service == 'yt':
        url = f"https://www.youtube.com/watch?v={resource_id}"
    elif service == 'sc':
        url = f"https://soundcloud.com/tracks/{resource_id}"
    else:
        url = 'http://' + resource_id

    # Check cache first
    db = SessionLocal()
    cached_file = db.query(FileCache).filter(FileCache.original_url == url).first()
    db.close()
    
    if cached_file:
        await query.edit_message_text("✅ فایل از آرشیو پیدا شد. در حال ارسال...")
        if cached_file.file_type == 'audio':
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=cached_file.file_id)
        else:
            await context.bot.send_video(chat_id=query.message.chat_id, video=cached_file.file_id)
        increment_download_count(user.user_id)
        await query.message.delete()
        return

    # --- Direct Download Logic (moved from tasks.py) ---
    await query.edit_message_text("در حال دانلود مستقیم... لطفاً صبر کنید (ربات ممکن است موقتا پاسخگو نباشد).")
    filename = None
    try:
        if quality == 'audio':
            ydl_opts = {'format': 'bestaudio/best', 'outtmpl': f'%(title)s_{resource_id}.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}
        else:
            resolution = quality.split('_')[1]
            ydl_opts = {'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]', 'outtmpl': f'%(title)s_{resource_id}.%(ext)s'}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_filename = ydl.prepare_filename(info)
            filename = os.path.splitext(original_filename)[0] + '.mp3' if quality == 'audio' else original_filename

        if quality == 'audio':
            sent_message = await context.bot.send_audio(chat_id=user.user_id, audio=open(filename, 'rb'), title=info.get('title'))
            file_id, file_type, file_size = sent_message.audio.file_id, 'audio', sent_message.audio.file_size
        else:
            sent_message = await context.bot.send_video(chat_id=user.user_id, video=open(filename, 'rb'), caption=info.get('title'))
            file_id, file_type, file_size = sent_message.video.file_id, 'video', sent_message.video.file_size
        
        db = SessionLocal()
        db.add(FileCache(original_url=url, file_id=file_id, file_type=file_type, file_size=file_size))
        db.commit()
        db.close()
        
        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download', details=service)
        await query.edit_message_text("✅ دانلود شما با موفقیت انجام شد.")

    except Exception as e:
        print(f"Direct download error: {e}")
        await query.edit_message_text("❌ متاسفانه در هنگام دانلود مشکلی پیش آمد.")
    
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)