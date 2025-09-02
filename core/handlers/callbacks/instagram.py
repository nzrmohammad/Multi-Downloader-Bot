# core/handlers/callbacks/instagram_callback.py
import logging
import os
from pathlib import Path
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from pydantic_core import ValidationError
from services.instagram import InstagramService

logger = logging.getLogger(__name__)

async def handle_instagram_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':')
    action = parts[1]
    user_pk = parts[2]
    
    client = InstagramService._client
    if not client:
        await query.message.reply_text("❌ سرویس اینستاگرام در حال حاضر در دسترس نیست.")
        return

    loop = asyncio.get_running_loop()
    download_paths = []
    try:
        if action == 'pfp':
            await query.message.reply_text("در حال دانلود عکس پروفایل با بالاترین کیفیت...")
            user_info = await loop.run_in_executor(None, lambda: client.user_info(user_pk))
            path = await loop.run_in_executor(None, lambda: client.photo_download_by_url(str(user_info.profile_pic_url_hd), folder="downloads"))
            download_paths.append(path)

        elif action == 'stories':
            await query.message.reply_text("در حال دانلود استوری‌ها...")
            stories = await loop.run_in_executor(None, lambda: client.user_stories(user_pk))
            for story in stories:
                path = await loop.run_in_executor(None, lambda: client.story_download(story.pk, folder="downloads"))
                download_paths.append(path)
        
        elif action == 'highlights':
            await query.message.reply_text("در حال دانلود هایلایت‌ها... (این فرآیند ممکن است زمان‌بر باشد)")
            highlights = await loop.run_in_executor(None, lambda: client.user_highlights(user_pk))
            for highlight in highlights:
                highlight_info = await loop.run_in_executor(None, lambda: client.highlight_info(highlight.pk))
                for story in highlight_info.items:
                    path = await loop.run_in_executor(None, lambda: client.story_download(story.pk, folder="downloads"))
                    download_paths.append(path)

        if not download_paths:
            await query.message.reply_text("هیچ محتوایی برای دانلود یافت نشد.")
            return

        await query.message.reply_text(f"✅ دانلود {len(download_paths)} فایل کامل شد. در حال آپلود...")
        for path in download_paths:
            with open(path, 'rb') as file_to_send:
                if Path(path).suffix == ".mp4":
                    await context.bot.send_video(chat_id=query.message.chat_id, video=file_to_send)
                else:
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_to_send)
    
    except ValidationError as e:
        logger.error(f"Pydantic validation error during Instagram download: {e}", exc_info=True)
        await query.message.reply_text("❌ دانلود ناموفق بود. اینستاگرام ساختار داده‌های خود را تغییر داده و کتابخانه نیاز به آپدیت دارد.")
    except Exception as e:
        logger.error(f"Error during Instagram profile download: {e}", exc_info=True)
        await query.message.reply_text(f"❌ خطایی در هنگام دانلود رخ داد: {e}")
    finally:
        for path in download_paths:
            if os.path.exists(path):
                os.remove(path)