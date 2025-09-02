# core/utils.py
import logging
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

def create_progress_bar(progress: float) -> str:
    """یک نوار پیشرفت متنی برای نمایش وضعیت دانلود ایجاد می‌کند."""
    bar_length = 10
    filled_length = int(bar_length * progress)
    bar = '▓' * filled_length + '░' * (bar_length - filled_length)
    return f"**[{bar}]**"

async def edit_message_safe(query, text, is_photo, reply_markup=None):
    """
    یک پیام را با در نظر گرفتن خطا ویرایش می‌کند.
    اگر پیام عکس‌دار باشد caption و در غیر این صورت text را ویرایش می‌کند.
    """
    try:
        if is_photo:
            await query.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.message.edit_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
    except BadRequest as e:
        # خطای "message is not modified" را نادیده می‌گیرد چون مهم نیست
        if "message is not modified" not in str(e):
            logger.warning(f"Could not edit message: {e}")