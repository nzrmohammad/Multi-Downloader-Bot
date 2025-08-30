# services/__init__.py

from .youtube import YoutubeService
from .spotify import SpotifyService
from .castbox import CastboxService
from .soundcloud import SoundCloudService
from .instagram import InstagramService
from .tiktok import TikTokService
from .vimeo import VimeoService
from .dailymotion import DailymotionService
from .bandcamp import BandcampService
# from .pornhub import PornhubService # <-- هر زمان آماده شد، این سرویس را اضافه کنید

# لیست مرکزی و نهایی سرویس‌ها
SERVICES = [
    YoutubeService(),
    SpotifyService(),
    CastboxService(),
    SoundCloudService(),
    InstagramService(),
    TikTokService(),
    VimeoService(),
    DailymotionService(),
    BandcampService(),
    # PornhubService(),
]