# services/castbox.py

import re
import json
import logging
import time
import os
from urllib.parse import unquote
import requests
from telegram import Update
from telegram.ext import ContextTypes
from bs4 import BeautifulSoup

from services.base_service import BaseService
from core.user_manager import get_or_create_user, can_download
from core.log_forwarder import forward_download_to_log_channel

logger = logging.getLogger(__name__)

CASTBOX_FULL_URL_PATTERN = re.compile(r"https?://castbox\.fm/episode/(?:.+?)-(?P<id>\w+)")
CASTBOX_SHORT_URL_PATTERN = re.compile(r"https?://castbox\.fm/ep/(?P<id>\d+)")

class CastboxService(BaseService):
    """
    Final working version for Castbox.
    It directly extracts the audio URL and metadata from the embedded JSON in the HTML source,
    downloads the file with a progress bar, and sends it with a detailed caption.
    """

    def _find_episode_info(self, page_url: str, episode_id_to_find: str) -> dict | None:
        """Finds the episode's direct audio URL and other metadata from the embedded JSON."""
        try:
            logger.info(f"Attempting to find episode info for URL: {page_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            
            response = requests.get(page_url, timeout=15, headers=headers)
            response.raise_for_status()
            logger.info("Successfully fetched Castbox page.")

            soup = BeautifulSoup(response.text, 'html.parser')
            script_content = soup.find('script', string=re.compile(r"window\.__INITIAL_STATE__"))
            
            if not script_content:
                logger.error("Could not find the __INITIAL_STATE__ script tag.")
                return None

            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*\"(.*)\";", script_content.string)
            if not match:
                logger.error("Could not extract the encoded JSON string from the script.")
                return None
                
            data = json.loads(unquote(match.group(1)))
            logger.info("Successfully decoded and parsed the initial state JSON.")
            
            all_episodes = []
            play_item = data.get('trackPlayItem', {}).get('playItem', {})
            if play_item:
                all_episodes.append(play_item)
            all_episodes.extend(data.get('eps', []))

            for episode in all_episodes:
                if str(episode.get('eid')) == episode_id_to_find:
                    logger.info(f"Found episode info for EID: {episode_id_to_find}")
                    return {
                        'audio_url': episode.get('url'),
                        'title': episode.get('title'),
                        'duration': episode.get('duration', 0),
                        'size': episode.get('size', 0),
                        'artist': episode.get('channel', {}).get('title', 'Unknown Artist')
                    }

            logger.warning(f"Could not find episode with EID {episode_id_to_find} in the JSON data.")
            return None

        except Exception as e:
            logger.error(f"An error occurred in _find_episode_info: {e}", exc_info=True)
            return None

    def _create_progress_bar(self, progress: float) -> str:
        """Creates a textual progress bar."""
        bar_length = 10
        filled_length = int(bar_length * progress)
        bar = '▓' * filled_length + '░' * (bar_length - filled_length)
        return f"**[{bar}]**"

    async def can_handle(self, url: str) -> bool:
        return re.match(CASTBOX_FULL_URL_PATTERN, url) is not None or \
               re.match(CASTBOX_SHORT_URL_PATTERN, url) is not None

    async def process(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        user = get_or_create_user(update)
        if not can_download(user):
            await update.message.reply_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
            return

        episode_id = None
        if match := re.match(CASTBOX_FULL_URL_PATTERN, url) or re.match(CASTBOX_SHORT_URL_PATTERN, url):
            episode_id = match.group('id')

        if not episode_id:
            await update.message.reply_text("خطا در تجزیه لینک کست‌باکس.")
            return

        msg = await update.message.reply_text("در حال استخراج اطلاعات... 🧐")

        episode_info = self._find_episode_info(url, episode_id)
        
        if not episode_info or not episode_info.get('audio_url'):
            await msg.edit_text("❌ اطلاعات این قسمت یافت نشد.")
            return

        audio_url = episode_info['audio_url']
        await msg.edit_text("لینک مستقیم پیدا شد! **در حال دانلود از سرور...**")
        
        temp_filename = f"downloads/castbox_{episode_id}.mp3"
        os.makedirs('downloads', exist_ok=True)
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            with requests.get(audio_url, headers=headers, stream=True, timeout=300) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded_size = 0
                last_update_time = time.time()
                
                with open(temp_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512): # 512KB chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_update_time > 2 and total_size > 0:
                            progress = downloaded_size / total_size
                            progress_bar = self._create_progress_bar(progress)
                            downloaded_mb = downloaded_size / 1024 / 1024
                            total_mb = total_size / 1024 / 1024
                            text = (
                                f"**در حال دانلود فایل از سرور...**\n\n"
                                f"{progress_bar} {progress:.0%}\n\n"
                                f"`{downloaded_mb:.1f} MB / {total_mb:.1f} MB`"
                            )
                            try:
                                await msg.edit_text(text, parse_mode='Markdown')
                            except Exception:
                                pass # Ignore if message not modified
                            last_update_time = current_time
            
            await msg.edit_text("دانلود کامل شد. **در حال آپلود برای شما...** 🚀")
            
            title = episode_info.get('title', 'پادکست')
            artist = episode_info.get('artist', 'پادکست')
            duration_ms = episode_info.get('duration', 0)
            duration_str = time.strftime('%M:%S', time.gmtime(duration_ms / 1000))
            file_size_mb = os.path.getsize(temp_filename) / 1024 / 1024
            
            caption = (
                f"🎧 **{title}**\n"
                f"👤 **{artist}**\n\n"
                f"▪️ **کیفیت:** `MP3 - (استاندارد)`\n"
                f"▪️ **حجم:** `{file_size_mb:.2f} MB`\n"
                f"▪️ **مدت زمان:** `{duration_str}`"
            )

            with open(temp_filename, 'rb') as audio_file:
                sent_message = await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=audio_file,
                    caption=caption,
                    title=title,
                    performer=artist,
                    duration=int(duration_ms / 1000),
                    filename=f"{title}.mp3",
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