# core/log_forwarder.py
from telegram import Update
from telegram.ext import ContextTypes
from core.settings import settings
from core.handlers.user_manager import User

async def forward_download_to_log_channel(context: ContextTypes.DEFAULT_TYPE, user: User, sent_message, service_name, url):
    """فایل دانلود شده را به کانال لاگ ارسال می‌کند."""
    if not settings.LOG_CHANNEL_ID:
        return

    caption = (
        f"**📥 گزارش دانلود**\n\n"
        f"**کاربر:** `{user.user_id}` (@{user.username or 'N/A'})\n" # <-- FIX: Changed user.id to user.user_id
        f"**سرویس:** `{service_name.capitalize()}`\n"
        f"**لینک اصلی:** `{url}`"
    )

    try:
        if sent_message.audio:
            await context.bot.send_audio(
                chat_id=settings.LOG_CHANNEL_ID,
                audio=sent_message.audio.file_id,
                caption=caption,
                parse_mode='Markdown'
            )
        elif sent_message.video:
            await context.bot.send_video(
                chat_id=settings.LOG_CHANNEL_ID,
                video=sent_message.video.file_id,
                caption=caption,
                parse_mode='Markdown'
            )
    except Exception as e:
        # Avoid crashing the main process if logging fails
        print(f"Failed to forward download to log channel: {e}")