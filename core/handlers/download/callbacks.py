# core/handlers/download/callbacks.py

import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# توابع دانلود از ماژول‌های جدید وارد می‌شوند
from .downloader_general import start_actual_download
from .downloader_playlist import handle_playlist_zip_download
from .downloader_spotify import handle_spotify_download

# Global dictionaries to manage download state
download_requests = {}
cancelled_tasks = {}

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()

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
        
        # استفاده از تابع کمکی برای ویرایش پیام
        from core.utils import edit_message_safe
        await edit_message_safe(query, f"{query.message.caption or query.message.text}\n\n{text}", query.message.photo, InlineKeyboardMarkup(keyboard))

    elif command == 'confirm':
        request_key = parts[2]
        if request_key not in download_requests or download_requests[request_key]['user_id'] != user.user_id:
            await query.message.edit_text("این درخواست نامعتبر یا منقضی شده است.")
            return
            
        cancelled_tasks[request_key] = False
        dl_info = download_requests.pop(request_key)
        
        # مسیریابی به تابع دانلود مناسب
        if dl_info.get('service') == 'spotify':
            await handle_spotify_download(query, user, dl_info['resource_id'], context, dl_info.get('original_message_caption', ''))
        else:
            await start_actual_download(query, user, dl_info, context)


    elif command == 'cancel':
        if len(parts) > 2:
            request_key = parts[2]
            cancelled_tasks[request_key] = True
        await query.message.delete()

async def handle_playlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    # این تابع به ماژول دانلود پلی‌لیست منتقل شده است
    await handle_playlist_zip_download(update, context, user)