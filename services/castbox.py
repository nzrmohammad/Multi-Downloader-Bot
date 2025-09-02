# services/castbox.py
import re
import json
import logging
import time
import os
from urllib.parse import unquote
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bs4 import BeautifulSoup
from html import unescape

from services.base_service import BaseService
from core.handlers.user_manager import can_download
from core.log_forwarder import forward_download_to_log_channel

logger = logging.getLogger(__name__)

# الگوهای شناسایی لینک
CASTBOX_EPISODE_URL_PATTERN = re.compile(r"https?://castbox\.fm/episode/.+-id(?P<id>\d+)")
CASTBOX_SHORT_URL_PATTERN = re.compile(r"https?://castbox\.fm/ep/(?P<id>\d+)")
CASTBOX_CHANNEL_URL_PATTERN = re.compile(r"https?://castbox\.fm/channel/(?:.*-)?id(?P<id>\d+)")

# تعریف حد حجم تلگرام برای آپلود توسط ربات
TELEGRAM_BOT_UPLOAD_LIMIT = 49 * 1024 * 1024

class CastboxService(BaseService):
    
    def _sanitize_filename(self, text: str) -> str:
        """کاراکترهای غیرمجاز را از نام فایل حذف کرده و طول آن را محدود می‌کند."""
        sanitized = re.sub(r'[\\/*?:"<>|]', "", text)
        return sanitized[:100]

    def _extract_page_data(self, page_url: str) -> dict | None:
        """اطلاعات JSON را از سورس صفحه وب کست‌باکس استخراج می‌کند."""
        try:
            logger.info(f"Fetching page data for URL: {page_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(page_url, timeout=15, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            script_content = soup.find('script', string=re.compile(r"window\.__INITIAL_STATE__"))
            if not script_content: return None
            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*\"(.*)\";", script_content.string)
            if not match: return None
            return json.loads(unquote(match.group(1)))
        except Exception as e:
            logger.error(f"Error in _extract_page_data: {e}", exc_info=True)
            return None

    async def can_handle(self, url: str) -> bool:
        """بررسی می‌کند که آیا لینک مربوط به کست‌باکس است یا خیر."""
        return any(re.match(pattern, url) for pattern in [CASTBOX_EPISODE_URL_PATTERN, CASTBOX_SHORT_URL_PATTERN, CASTBOX_CHANNEL_URL_PATTERN])

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str, message_to_edit=None):
        """لینک‌های کست‌باکس را پردازش می‌کند."""
        if not can_download(user):
            await (message_to_edit or update.message).reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = message_to_edit or await update.message.reply_text("در حال استخراج اطلاعات... 🧐")
        
        page_data = self._extract_page_data(url)
        if not page_data:
            await msg.edit_text("❌ اطلاعات از صفحه کست‌باکس دریافت نشد.")
            return

        if bool(re.match(CASTBOX_CHANNEL_URL_PATTERN, url)):
            await self.handle_channel_link(msg, page_data, context)
        else:
            await self.handle_episode_download(msg, page_data, user, context, url)

    async def handle_channel_link(self, msg, page_data, context):
        """لیست قسمت‌های یک کانال را نمایش می‌دهد."""
        episodes = page_data.get('ch', {}).get('eps', [])
        channel_title = page_data.get('ch', {}).get('chInfo', {}).get('title', 'کانال کست‌باکس')
        if not episodes:
            await msg.edit_text("❌ هیچ قسمتی در این کانال یافت نشد.")
            return

        context.bot_data[f"castbox_eps_{msg.chat_id}"] = episodes
        text = f"🎧 **{channel_title}**\n\nلطفاً قسمت مورد نظر برای دانلود را انتخاب کنید (صفحه ۱):"
        keyboard = self.build_episode_keyboard(episodes, chat_id=msg.chat.id, page=1)
        await msg.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    def build_episode_keyboard(self, episodes: list, chat_id: int, page: int = 1, per_page: int = 10) -> InlineKeyboardMarkup:
        """دکمه‌های صفحه‌بندی شده برای لیست قسمت‌ها را ایجاد می‌کند."""
        start, end = (page - 1) * per_page, page * per_page
        buttons = [[InlineKeyboardButton(ep['title'], callback_data=f"castbox:dl:{ep['eid']}")] for ep in episodes[start:end]]
        nav_buttons = []
        if page > 1: nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"castbox:page:{page - 1}:{chat_id}"))
        if end < len(episodes): nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"castbox:page:{page + 1}:{chat_id}"))
        if nav_buttons: buttons.append(nav_buttons)
        return InlineKeyboardMarkup(buttons)

    async def handle_episode_download(self, msg, page_data, user, context, url):
        """یک قسمت مشخص را دانلود و مدیریت می‌کند."""
        episode_info = page_data.get('trackPlayItem', {}).get('playItem', {})
        if not episode_info:
            match = re.search(r'-id(?P<id>\d+)|/ep/(?P<id>\d+)', url)
            if match:
                target_eid = next(filter(None, match.groups()))
                episode_info = next((ep for ep in page_data.get('ch', {}).get('eps', []) if str(ep.get('eid')) == target_eid), None)

        if not episode_info or not episode_info.get('url'):
            await msg.edit_text("❌ اطلاعات این قسمت برای دانلود یافت نشد.")
            return

        audio_url = episode_info['url']
        temp_filename = "" 
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            head_response = requests.head(audio_url, headers=headers, allow_redirects=True, timeout=15)
            file_size = int(head_response.headers.get('content-length', 0))

            title_raw = episode_info.get('title', 'پادکست')
            artist_raw = page_data.get('ch', {}).get('chInfo', {}).get('title', 'پادکست')
            
            duration_ms = episode_info.get('duration', 0)
            duration_str = time.strftime('%H:%M:%S', time.gmtime(duration_ms / 1000)) if duration_ms >= 3600000 else time.strftime('%M:%S', time.gmtime(duration_ms / 1000))
            release_date_formatted = episode_info.get('release_date', '').split('T')[0]
            
            channel_id = page_data.get('ch', {}).get('chInfo', {}).get('id')
            channel_url = f"https://castbox.fm/channel/id{channel_id}" if channel_id else "#"
            episode_url = url
            
            caption = (
                f"🎧 **{title_raw}**\n"
                f"👤 **پادکست:** {artist_raw}\n\n"
                f"🗓 **تاریخ انتشار:** `{release_date_formatted}`\n"
                f"▪️ **حجم:** `{file_size / 1024 / 1024:.2f} MB`\n"
                f"▪️ **مدت زمان:** `{duration_str}`\n\n"
                f"🔗 [لینک کانال]({channel_url}) | [لینک اپیزود]({episode_url})"
            )

            if file_size > TELEGRAM_BOT_UPLOAD_LIMIT:
                await msg.edit_text(
                    text=caption,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📥 دانلود مستقیم (فایل حجیم)", url=audio_url)]]),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await msg.edit_text("در حال دانلود از سرور...", parse_mode='Markdown')
                clean_filename = f"{self._sanitize_filename(artist_raw)} - {self._sanitize_filename(title_raw)}.mp3"
                temp_filename = f"downloads/{clean_filename}"
                os.makedirs('downloads', exist_ok=True)
                
                with requests.get(audio_url, stream=True, timeout=300, headers=headers) as r:
                    r.raise_for_status()
                    with open(temp_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            f.write(chunk)
                
                await msg.edit_text("دانلود کامل شد. در حال آپلود...", parse_mode='Markdown')
                with open(temp_filename, 'rb') as audio_file:
                    # --- FIX: پارامتر ناسازگار از اینجا حذف شد ---
                    await context.bot.send_audio(
                        chat_id=msg.chat.id, audio=audio_file, caption=caption, title=title_raw,
                        performer=artist_raw, duration=int(duration_ms / 1000), filename=clean_filename,
                        parse_mode='Markdown' 
                    )
                await msg.delete()

        except Exception as e:
            logger.error(f"Failed to download or send audio file: {e}", exc_info=True)
            await msg.edit_text(f"❌ در هنگام دانلود یا ارسال فایل صوتی مشکلی پیش آمد: {e}")
        finally:
            if temp_filename and os.path.exists(temp_filename):
                os.remove(temp_filename)