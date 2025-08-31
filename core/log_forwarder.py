# core/log_forwarder.py
from telegram import Update
from telegram.ext import ContextTypes
import config

async def forward_download_to_log_channel(context: ContextTypes.DEFAULT_TYPE, user, sent_message, service_name, url):
    """فایل دانلود شده را به کانال لاگ ارسال می‌کند."""
    if not config.LOG_CHANNEL_ID:
        return

    caption = (
        f"**📥 گزارش دانلود**\n\n"
        f"**کاربر:** `{user.id}` (@{user.username or 'N/A'})\n"
        f"**سرویس:** `{service_name.capitalize()}`\n"
        f"**لینک اصلی:** `{url}`"
    )

    # از file_id برای ارسال مجدد فایل استفاده می‌کنیم که سریع‌تر است
    if sent_message.audio:
        await context.bot.send_audio(
            chat_id=config.LOG_CHANNEL_ID,
            audio=sent_message.audio.file_id,
            caption=caption,
            parse_mode='Markdown'
        )
    elif sent_message.video:
        await context.bot.send_video(
            chat_id=config.LOG_CHANNEL_ID,
            video=sent_message.video.file_id,
            caption=caption,
            parse_mode='Markdown'
        )