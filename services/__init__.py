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
# --- سرویس‌های جدید ---
from .pornhub import PornhubService
from .twitter import TwitterService
from .facebook import FacebookService
from .reddit import RedditService
from .twitch import TwitchService
from .redtube import RedTubeService


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
    PornhubService(),
    TwitterService(),
    FacebookService(),
    RedditService(),
    TwitchService(),
    RedTubeService()
]