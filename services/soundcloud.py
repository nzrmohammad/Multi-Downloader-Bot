# services/soundcloud.py

import re
import json
import logging
import time
import requests
from telegram import Update
from telegram.ext import ContextTypes

from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download

logger = logging.getLogger(__name__)

SOUNDCLOUD_URL_PATTERN = re.compile(r"https?://soundcloud\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)")

class SoundCloudService(BaseService):
    """
    Final working version for SoundCloud downloader.
    This version adds the necessary headers to the final stream request to avoid 403 errors.
    """
    _client_id = None
    _last_client_id_fetch = 0

    def _get_client_id(self) -> str | None:
        # This function is now working correctly and remains unchanged.
        if self._client_id and (time.time() - self._last_client_id_fetch < 3600):
            return self._client_id
        logger.info("Attempting to fetch new SoundCloud client_id...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            main_page_res = requests.get("https://soundcloud.com", headers=headers, timeout=10)
            main_page_res.raise_for_status()
            script_urls = re.findall(r'<script crossorigin src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"></script>', main_page_res.text)
            if not script_urls:
                logger.error("Could not find any JavaScript asset URLs on the SoundCloud homepage.")
                return None
            for script_url in reversed(script_urls):
                try:
                    script_content_res = requests.get(script_url, headers=headers, timeout=10)
                    script_content_res.raise_for_status()
                    match = re.search(r',client_id:"([a-zA-Z0-9_]+)"', script_content_res.text)
                    if match:
                        self._client_id = match.group(1)
                        self._last_client_id_fetch = time.time()
                        logger.info(f"SUCCESS: Extracted client_id '{self._client_id}' from {script_url}")
                        return self._client_id
                except requests.RequestException:
                    continue
            logger.error("Searched all JS files but could not find a client_id.")
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch SoundCloud homepage to get client_id: {e}")
            return None

    def _create_progress_bar(self, progress: float) -> str:
        bar_length = 10
        filled_length = int(bar_length * progress)
        bar = '▓' * filled_length + '░' * (bar_length - filled_length)
        return f"**[{bar}]**"

    async def can_handle(self, url: str) -> bool:
        return re.match(SOUNDCLOUD_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        msg = await update.message.reply_text("در حال اتصال به API ساندکلاد...")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        client_id = self._get_client_id()
        if not client_id:
            await msg.edit_text("❌ خطا: امکان دریافت کلید دسترسی از ساندکلاد وجود ندارد.")
            return

        try:
            clean_url = url.split('?')[0]
            resolve_url = f"https://api-v2.soundcloud.com/resolve?url={clean_url}&client_id={client_id}"
            meta_res = requests.get(resolve_url, headers=headers, timeout=10)
            meta_res.raise_for_status()
            track_data = meta_res.json()

            title = track_data.get('title', 'Unknown Title')
            artist = track_data.get('user', {}).get('username', 'Unknown Artist')
            duration_ms = track_data.get('duration', 0)
            duration_str = time.strftime('%M:%S', time.gmtime(duration_ms / 1000))

            audio_url = None
            quality = "استاندارد"
            for transcoding in track_data.get('media', {}).get('transcodings', []):
                if transcoding.get('format', {}).get('protocol') == 'progressive':
                    stream_api_url = f"{transcoding['url']}?client_id={client_id}"
                    stream_res = requests.get(stream_api_url, headers=headers, timeout=10)
                    stream_res.raise_for_status()
                    audio_url = stream_res.json().get('url')
                    if "hq" in transcoding.get('quality', ''):
                        quality = "بالا (HQ)"
                    if audio_url:
                        break
            
            if not audio_url:
                await msg.edit_text("❌ لینک دانلود مستقیم برای این آهنگ یافت نشد.")
                return

            await msg.edit_text("لینک مستقیم پیدا شد! **در حال دانلود از سرور...**")

            audio_response = requests.get(audio_url, stream=True, timeout=60)
            audio_response.raise_for_status()
            
            total_size = int(audio_response.headers.get('content-length', 0))
            audio_content = bytearray()

            downloaded_size = 0
            last_update_time = time.time()
            for chunk in audio_response.iter_content(chunk_size=1024 * 512):
                audio_content.extend(chunk)
                downloaded_size += len(chunk)
                current_time = time.time()
                if current_time - last_update_time > 2:
                    if total_size > 0:
                        progress = downloaded_size / total_size
                        progress_bar = self._create_progress_bar(progress)
                        downloaded_mb = downloaded_size / 1024 / 1024
                        total_mb = total_size / 1024 / 1024
                        text = (f"**در حال دانلود از سرور...**\n\n"
                                f"{progress_bar} {progress:.0%}\n\n"
                                f"`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`")
                        try:
                            await msg.edit_text(text, parse_mode='Markdown')
                        except Exception:
                            pass
                        last_update_time = current_time
            
            await msg.edit_text("دانلود کامل شد. **در حال آپلود برای شما...** 🚀")

            # --- قالب جدید کپشن ---
            file_size_mb = len(audio_content) / 1024 / 1024
            caption = (
                f"🎧 **{title}**\n"
                f"👤 **{artist}**\n\n"
                f"▪️ **کیفیت:** `MP3 - {quality}`\n"
                f"▪️ **حجم:** `{file_size_mb:.2f} MB`\n"
                f"▪️ **مدت زمان:** `{duration_str}`"
            )

            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=bytes(audio_content),
                caption=caption, # <-- استفاده از کپشن جدید
                title=title,
                performer=artist,
                duration=int(duration_ms / 1000),
                filename=f"{title}.mp3",
                parse_mode='Markdown'
            )
            await msg.delete()

        except Exception as e:
            logger.error(f"Failed during SoundCloud API process: {e}", exc_info=True)
            await msg.edit_text("❌ در هنگام پردازش لینک ساندکلاد مشکلی پیش آمد.")