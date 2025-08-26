import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram configurations
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

# Spotify API configurations
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# Deezer configuration
DEEZER_ARL = os.getenv("DEEZER_ARL")


# Validate essential configurations
if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN and ADMIN_ID must be set in the .env file!")