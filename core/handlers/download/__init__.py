# core/handlers/download/__init__.py

# این فایل می‌تواند خالی باشد یا برای import کردن توابع اصلی استفاده شود.
# در اینجا ماژول‌ها را برای دسترسی آسان‌تر وارد می‌کنیم.

from .callbacks import handle_download_callback, handle_playlist_callback
from .downloader_general import start_actual_download
from .downloader_playlist import handle_playlist_zip_download
from .downloader_spotify import handle_spotify_download