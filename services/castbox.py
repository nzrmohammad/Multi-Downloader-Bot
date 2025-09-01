# services/castbox.py (نسخه نهایی با استایل اصلاح شده و کپشن کامل‌تر)

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
from core.user_manager import can_download
from core.log_forwarder import forward_download_to_log_channel

logger = logging.getLogger(__name__)

# الگوهای شناسایی لینک (بدون تغییر)
CASTBOX_EPISODE_URL_PATTERN = re.compile(r"https?://castbox\.fm/episode/.+-id(?P<id>\d+)")
CASTBOX_SHORT_URL_PATTERN = re.compile(r"https?://castbox\.fm/ep/(?P<id>\d+)")
CASTBOX_CHANNEL_URL_PATTERN = re.compile(r"https?://castbox\.fm/channel/(?:.*-)?id(?P<id>\d+)")

class CastboxService(BaseService):
    """
    سرویس کست‌باکس با قابلیت پشتیبانی از لینک مستقیم قسمت و لینک کانال.
    """
    
    def _extract_page_data(self, page_url: str) -> dict | None:
        """اطلاعات JSON را از سورس صفحه وب کست‌باکس استخراج می‌کند."""
        try:
            logger.info(f"Fetching page data for URL: {page_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            
            response = requests.get(page_url, timeout=15, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            script_content = soup.find('script', string=re.compile(r"window\.__INITIAL_STATE__"))
            
            if not script_content:
                logger.error("Could not find __INITIAL_STATE__ script tag.")
                return None

            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*\"(.*)\";", script_content.string)
            if not match:
                logger.error("Could not extract encoded JSON string.")
                return None
                
            data = json.loads(unquote(match.group(1)))
            logger.info("Successfully decoded and parsed initial state JSON.")
            return data

        except Exception as e:
            logger.error(f"Error in _extract_page_data: {e}", exc_info=True)
            return None

    async def can_handle(self, url: str) -> bool:
        """بررسی می‌کند که آیا لینک مربوط به قسمت یا کانال کست‌باکس است."""
        return any(re.match(pattern, url) for pattern in [
            CASTBOX_EPISODE_URL_PATTERN, 
            CASTBOX_SHORT_URL_PATTERN, 
            CASTBOX_CHANNEL_URL_PATTERN
        ])

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user, url: str):
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات... 🧐")

        is_channel = bool(re.match(CASTBOX_CHANNEL_URL_PATTERN, url))
        
        page_data = self._extract_page_data(url)
        if not page_data:
            await msg.edit_text("❌ اطلاعات از صفحه کست‌باکس دریافت نشد.")
            return

        if is_channel:
            await self.handle_channel_link(msg, page_data, context)
        else:
            await self.handle_episode_download(msg, page_data, user, context, url)

    async def handle_channel_link(self, msg, page_data, context):
        """لیست قسمت‌های یک کانال را به صورت صفحه‌بندی شده نمایش می‌دهد."""
        episodes = page_data.get('ch', {}).get('eps', [])
        channel_info = page_data.get('ch', {}).get('chInfo', {})
        channel_title = channel_info.get('title', 'کانال کست‌باکس')
        
        if not episodes:
            await msg.edit_text("❌ هیچ قسمتی در این کانال یافت نشد.")
            return

        context.bot_data[f"castbox_eps_{msg.chat_id}"] = episodes
        
        text = f"🎧 **{channel_title}**\n\nلطفاً قسمت مورد نظر برای دانلود را انتخاب کنید (صفحه ۱):"
        keyboard = self.build_episode_keyboard(episodes, chat_id=msg.chat_id, page=1)
        
        # --- FIX: افزودن parse_mode='Markdown' برای اعمال استایل Bold ---
        await msg.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    def build_episode_keyboard(self, episodes: list, chat_id: int, page: int = 1, per_page: int = 10) -> InlineKeyboardMarkup:
        """دکمه‌های صفحه‌بندی شده برای لیست قسمت‌ها را ایجاد می‌کند."""
        start = (page - 1) * per_page
        end = start + per_page
        
        buttons = []
        for ep in episodes[start:end]:
            buttons.append([InlineKeyboardButton(ep['title'], callback_data=f"castbox:dl:{ep['eid']}")])
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"castbox:page:{page - 1}:{chat_id}"))
        if end < len(episodes):
            nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"castbox:page:{page + 1}:{chat_id}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
            
        return InlineKeyboardMarkup(buttons)

    async def handle_episode_download(self, msg, page_data, user, context, url):
        """یک قسمت مشخص را دانلود و برای کاربر ارسال می‌کند."""
        episode_info = page_data.get('trackPlayItem', {}).get('playItem', {})
        if not episode_info:
            # اگر اطلاعات در مسیر اصلی نبود، از لیست قسمت‌ها جستجو کن
            episode_id_match = re.search(r'-id(?P<id>\d+)', url) or re.search(r'/ep/(?P<id>\d+)', url)
            if episode_id_match:
                target_eid = episode_id_match.group('id')
                all_episodes = page_data.get('ch', {}).get('eps', [])
                for ep in all_episodes:
                    if str(ep.get('eid')) == target_eid:
                        episode_info = ep
                        break

        if not episode_info or not episode_info.get('url'):
            await msg.edit_text("❌ اطلاعات این قسمت برای دانلود یافت نشد.")
            return

        audio_url = episode_info['url']
        episode_id = episode_info['eid']
        await msg.edit_text("لینک مستقیم پیدا شد! **در حال دانلود از سرور...**")
        
        temp_filename = f"downloads/castbox_{episode_id}.mp3"
        os.makedirs('downloads', exist_ok=True)
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            with requests.get(audio_url, stream=True, timeout=300, headers=headers) as r:
                r.raise_for_status(); total_size = int(r.headers.get('content-length', 0)); downloaded_size = 0; last_update_time = time.time()
                with open(temp_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        f.write(chunk); downloaded_size += len(chunk); current_time = time.time()
                        if current_time - last_update_time > 2 and total_size > 0:
                            progress = downloaded_size / total_size; progress_bar = self._create_progress_bar(progress); downloaded_mb = downloaded_size / 1024 / 1024; total_mb = total_size / 1024 / 1024
                            text = f"**در حال دانلود از سرور...**\n\n{progress_bar} {progress:.0%}\n\n`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`"
                            try: await msg.edit_text(text, parse_mode='Markdown')
                            except Exception: pass
                            last_update_time = current_time
            
            await msg.edit_text("دانلود کامل شد. **در حال آپلود برای شما...** 🚀")
            
            # --- FIX & ENHANCEMENT: کپشن جدید و کامل‌تر ---
            title = episode_info.get('title', 'پادکست')
            # برای گرفتن نام کانال، از اطلاعات کلی صفحه استفاده می‌کنیم
            artist = page_data.get('ch', {}).get('chInfo', {}).get('title', 'پادکست')
            duration_ms = episode_info.get('duration', 0)
            duration_str = time.strftime('%H:%M:%S', time.gmtime(duration_ms / 1000)) if duration_ms >= 3600000 else time.strftime('%M:%S', time.gmtime(duration_ms / 1000))
            file_size_mb = os.path.getsize(temp_filename) / 1024 / 1024
            
            # اضافه کردن تاریخ انتشار
            release_date_str = episode_info.get('release_date', '')
            release_date_formatted = ''
            if release_date_str:
                try:
                    # تبدیل تاریخ به فرمت خواناتر
                    release_date_formatted = f"\n🗓 **تاریخ انتشار:** `{release_date_str.split('T')[0]}`"
                except: pass

            # اضافه کردن توضیحات قسمت (و تمیز کردن تگ‌های HTML)
            description_html = episode_info.get('description', '')
            description_text = ''
            if description_html:
                # استفاده از BeautifulSoup برای حذف تگ‌های HTML
                soup = BeautifulSoup(description_html, 'html.parser')
                clean_desc = unescape(soup.get_text())
                # خلاصه کردن توضیحات طولانی
                description_text = f"\n\n📄 *{clean_desc[:200]}...*" if len(clean_desc) > 200 else f"\n\n📄 *{clean_desc}*"

            caption = (
                f"🎧 **{title}**\n"
                f"👤 **{artist}**\n"
                f"{release_date_formatted}\n"
                f"▪️ **کیفیت:** `MP3 - (استاندارد)`\n"
                f"▪️ **حجم:** `{file_size_mb:.2f} MB`\n"
                f"▪️ **مدت زمان:** `{duration_str}`"
                f"{description_text}"
            )
            # -----------------------------------------------------------

            with open(temp_filename, 'rb') as audio_file:
                sent_message = await context.bot.send_audio(
                    chat_id=msg.chat.id, audio=audio_file, caption=caption, title=title,
                    performer=artist, duration=int(duration_ms / 1000), filename=f"{title}.mp3",
                    parse_mode='Markdown'
                )
            await forward_download_to_log_channel(context, user, sent_message, "castbox", url)
            await msg.delete()
        except Exception as e:
            logger.error(f"Failed to download or send audio file: {e}", exc_info=True)
            await msg.edit_text("❌ در هنگام دانلود یا ارسال فایل صوتی مشکلی پیش آمد.")
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    def _create_progress_bar(self, progress: float) -> str:
        bar_length = 10; filled_length = int(bar_length * progress); bar = '▓' * filled_length + '░' * (bar_length - filled_length); return f"**[{bar}]**"