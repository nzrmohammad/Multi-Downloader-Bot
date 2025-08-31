import os
from dotenv import load_dotenv

load_dotenv()

# Telegram configurations
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
SENSITIVE_SERVICES = os.getenv("SENSITIVE_SERVICES", "").split(',')
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID")) if os.getenv("LOG_CHANNEL_ID") else None

# Spotify API configurations
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# Twitter Auth Cookie
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN")

# --- Genius API Configuration Re-added ---
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")

# Validate essential configurations
if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN and ADMIN_ID must be set in the .env file!")
if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set!")
# The following check is now re-added
if not GENIUS_ACCESS_TOKEN:
    raise ValueError("GENIUS_ACCESS_TOKEN must be set!")