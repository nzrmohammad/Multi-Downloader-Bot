# services/instagram.py
import re
import os
import asyncio
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from instagrapi import Client
from instagrapi.exceptions import MediaNotFound, UserNotFound

from services.base_service import BaseService
from core.user_manager import can_download
from core.settings import settings

logger = logging.getLogger(__name__)

INSTAGRAM_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/((?:p|reel|tv)/[a-zA-Z0-9_-]+|([a-zA-Z0-9_.-]+))"
)

class InstagramService(BaseService):
    _client = None

    def __init__(self):
        if not InstagramService._client:
            logger.info("Initializing Instagrapi client...")
            InstagramService._client = Client()
            self._load_session_and_proxy()

    def _load_session_and_proxy(self):
        try:
            proxy = "socks5h://127.0.0.1:2000"
            InstagramService._client.set_proxy(proxy)
            logger.info(f"Using SOCKS5 proxy for Instagrapi: {proxy}")

            if not settings.INSTAGRAM_USERNAME:
                raise Exception("INSTAGRAM_USERNAME not set in .env file.")
            
            session_file = Path(f"{settings.INSTAGRAM_USERNAME}.json")
            if session_file.exists():
                InstagramService._client.load_settings(session_file)
                InstagramService._client.get_timeline_feed()
                logger.info(f"✅ Instagrapi session loaded and validated from '{session_file}'.")
            else:
                raise Exception(f"Session file '{session_file}' not found.")

        except Exception as e:
            logger.error(f"Failed to initialize Instagrapi client: {e}", exc_info=True)
            InstagramService._client = None
            print(f"CRITICAL: Instagrapi client failed. Service will be disabled. Error: {e}")

    async def can_handle(self, url: str) -> bool:
        return InstagramService._client is not None and re.search(INSTAGRAM_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        match = re.search(INSTAGRAM_URL_PATTERN, url)
        if not match:
            await update.message.reply_text("❌ لینک اینستاگرام نامعتبر است.")
            return
        
        link_part = match.group(1).split('?')[0]
        is_profile = not link_part.startswith(('p/', 'reel/', 'tv/'))
        
        if is_profile:
            username = link_part.strip('/')
            await self.handle_profile_link(update, context, username)
        else:
            await self.handle_post_link(update, context, url)

    async def handle_post_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        msg = await update.message.reply_text("در حال پردازش لینک پست... 📲")
        download_path = None
        try:
            loop = asyncio.get_running_loop()
            media_pk = await loop.run_in_executor(None, lambda: self._client.media_pk_from_url(url))
            media_info = await loop.run_in_executor(None, lambda: self._client.media_info(media_pk))
            
            if media_info.video_url:
                await msg.edit_text("در حال دانلود ویدیو...")
                download_path = await loop.run_in_executor(None, lambda: self._client.video_download(media_pk, folder=Path("downloads")))
            else:
                await msg.edit_text("در حال دانلود تصویر...")
                download_path = await loop.run_in_executor(None, lambda: self._client.photo_download(media_pk, folder=Path("downloads")))

            post_caption = media_info.caption_text
            caption = (
                f"{post_caption}\n\n"
                f"❤️ `{media_info.like_count}`   💬 `{media_info.comment_count}`\n"
                f"👤 **ارسال کننده:** `{media_info.user.username}`\n"
                f"📅 **تاریخ:** `{media_info.taken_at.strftime('%Y-%m-%d')}`\n\n"
                f"[🔗 مشاهده در اینستاگرام]({url})"
            )
            if len(caption) > 1024: caption = caption[:1000] + "...`"
            
            await msg.edit_text("✅ دانلود کامل شد. در حال آپلود...")
            with open(download_path, 'rb') as file_to_send:
                if download_path.suffix == ".mp4":
                    await context.bot.send_video(chat_id=update.effective_chat.id, video=file_to_send, caption=caption, parse_mode='Markdown', supports_streaming=True)
                else:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_to_send, caption=caption, parse_mode='Markdown')
            await msg.delete()

        except MediaNotFound:
            await msg.edit_text("❌ این پست یافت نشد. ممکن است حذف شده یا خصوصی باشد.")
        except Exception as e:
            logger.error(f"Error downloading post: {e}", exc_info=True)
            await msg.edit_text(f"❌ خطایی در هنگام دانلود پست رخ داد: {e}")
        finally:
            if download_path and os.path.exists(download_path):
                os.remove(download_path)

    async def handle_profile_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
        msg = await update.message.reply_text(f"در حال دریافت اطلاعات پروفایل `{username}`...", parse_mode='Markdown')
        try:
            loop = asyncio.get_running_loop()
            user_info = await loop.run_in_executor(None, lambda: self._client.user_info_by_username(username))
            
            caption = (
                f"👤 **{user_info.full_name}** (`@{user_info.username}`)\n"
                f"**بیوگرافی:** {user_info.biography}\n\n"
                f"**پست‌ها:** `{user_info.media_count}`\n"
                f"**فالوور:** `{user_info.follower_count}`\n"
                f"**فالووینگ:** `{user_info.following_count}`"
            )
            
            keyboard_row = []
            user_stories = await loop.run_in_executor(None, lambda: self._client.user_stories(user_info.pk))
            if user_stories:
                keyboard_row.append(InlineKeyboardButton("📥 استوری‌ها", callback_data=f"ig_profile:stories:{user_info.pk}"))

            user_highlights = await loop.run_in_executor(None, lambda: self._client.user_highlights(user_info.pk))
            if user_highlights:
                keyboard_row.append(InlineKeyboardButton("🌟 هایلایت‌ها", callback_data=f"ig_profile:highlights:{user_info.pk}"))
            
            keyboard = [[InlineKeyboardButton("🖼️ عکس پروفایل", callback_data=f"ig_profile:pfp:{user_info.pk}")]]
            if keyboard_row:
                keyboard.append(keyboard_row)
            
            await msg.delete()
            photo_url = str(user_info.profile_pic_url_hd)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=photo_url, caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )

        except UserNotFound:
            await msg.edit_text(f"❌ پروفایل `{username}` یافت نشد.", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error fetching profile: {e}", exc_info=True)
            await msg.edit_text(f"❌ خطایی در دریافت اطلاعات پروفایل رخ داد: {e}")