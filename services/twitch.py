# services/twitch_service.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.base_service import BaseService

TWITCH_URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?twitch\.tv/(?:videos/(\d+)|clips/([a-zA-Z0-9_-]+)|([a-zA-Z0-9_]+)/clip/([a-zA-Z0-9_-]+))")

class TwitchService(BaseService):
    async def can_handle(self, url: str) -> bool:
        return re.match(TWITCH_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک توییچ...")
        info = await self._extract_info_ydl(url)

        if not info:
            await msg.edit_text("❌ اطلاعات ویدیو دریافت نشد.")
            return

        video_id = info.get('id')
        title = info.get('title', 'Twitch Stream')
        uploader = info.get('uploader', 'N/A')
        thumbnail = info.get('thumbnail')
        is_clip = 'clip' in url or 'clips' in info.get('webpage_url', '')

        caption = (f"**🎮 ویدیوی توییچ**\n\n"
                   f"**{'کلیپ' if is_clip else 'استریم'}:** `{title}`\n"
                   f"**استریمر:** `{uploader}`")
        
        keyboard = [[InlineKeyboardButton("🎬 دانلود ویدیو", callback_data=f"dl:prepare:twitch:video_best:{video_id}")]]
        
        await msg.delete()
        if thumbnail:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=thumbnail, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )