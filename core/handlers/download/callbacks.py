# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/download/callbacks.py

import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .downloader import start_actual_download, handle_playlist_zip_download

# Global dictionaries to manage download state
download_requests = {}
cancelled_tasks = {}

# FIX: Added 'user' parameter to the function definition
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
        # The _edit_message_safe function should be imported here if it's in a utils file
        # For now, we assume it's available or call the direct method
        await query.message.edit_caption(
            caption=f"{query.message.caption or query.message.text}\n\n{text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif command == 'confirm':
        request_key = parts[2]
        if request_key not in download_requests or download_requests[request_key]['user_id'] != user.user_id:
            await query.message.edit_text("این درخواست نامعتبر یا منقضی شده است.")
            return
            
        cancelled_tasks[request_key] = False
        dl_info = download_requests.pop(request_key)
        await start_actual_download(query, user, dl_info, context, request_key)

    elif command == 'cancel':
        if len(parts) > 2:
            request_key = parts[2]
            cancelled_tasks[request_key] = True
        await query.message.delete()

async def handle_playlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await handle_playlist_zip_download(update, context, user)