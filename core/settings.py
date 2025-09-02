# core/settings.py

import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

class Settings:
    """
    کلاس مرکزی برای مدیریت تمام تنظیمات برنامه با استفاده از type hinting.
    """
    # Telegram configurations
    BOT_TOKEN: str
    ADMIN_ID: int
    LOG_CHANNEL_ID: int | None

    # Spotify API configurations
    SPOTIPY_CLIENT_ID: str
    SPOTIPY_CLIENT_SECRET: str

    # Twitter Auth Cookie
    TWITTER_AUTH_TOKEN: str | None

    # Genius API Configuration
    GENIUS_ACCESS_TOKEN: str

    # Proxy Configuration
    PROXY_SOURCE_URL: str | None
    
    # --- FIX: افزودن تنظیمات جدید برای لاگین اتوماتیک ---
    YOUTUBE_COOKIES_FILE: str | None
    YOUTUBE_EMAIL: str | None
    YOUTUBE_PASSWORD: str | None

    def __init__(self):
        # --- اعتبارسنجی و بارگذاری متغیرهای ضروری ---
        bot_token = os.getenv("BOT_TOKEN")
        admin_id = os.getenv("ADMIN_ID")
        spotipy_client_id = os.getenv("SPOTIPY_CLIENT_ID")
        spotipy_client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        genius_access_token = os.getenv("GENIUS_ACCESS_TOKEN")

        if not all([bot_token, admin_id, spotipy_client_id, spotipy_client_secret, genius_access_token]):
            raise ValueError("یکی از متغیرهای محیطی ضروری (BOT_TOKEN, ADMIN_ID, SPOTIPY_...) تنظیم نشده است.")

        self.BOT_TOKEN = bot_token
        self.ADMIN_ID = int(admin_id)
        self.SPOTIPY_CLIENT_ID = spotipy_client_id
        self.SPOTIPY_CLIENT_SECRET = spotipy_client_secret
        self.GENIUS_ACCESS_TOKEN = genius_access_token

        # --- بارگذاری متغیرهای اختیاری ---
        log_channel_id = os.getenv("LOG_CHANNEL_ID")
        self.LOG_CHANNEL_ID = int(log_channel_id) if log_channel_id else None
        self.TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN")
        
        self.PROXY_SOURCE_URL = os.getenv("PROXY_SOURCE_URL", "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/main/http.txt")
        
        # --- FIX: خواندن متغیرهای جدید از فایل .env ---
        self.YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE")
        self.YOUTUBE_EMAIL = os.getenv("YOUTUBE_EMAIL")
        self.YOUTUBE_PASSWORD = os.getenv("YOUTUBE_PASSWORD")

# یک نمونه (instance) از کلاس تنظیمات ساخته می‌شود تا در کل پروژه از آن استفاده شود.
settings = Settings()