import asyncio
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from core import user_manager
from database import database
from database.models import User, Ticket
from core.callback_handler import main_callback_handler
from services import youtube, spotify, soundcloud, deezer

# --- Logging Setup ---
# Set up basic logging and quiet down the noisy libraries
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# --- Service Dispatcher ---
SERVICES = [
    youtube.YoutubeService(),
    spotify.SpotifyService(),

]

async def dispatch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming links and dispatches them to the correct service."""
    # (Implementation for this function remains the same as before)
    pass

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Implementation for this function remains the same as before)
    pass
# ... (All your other command handlers like admin_command, settings_command, etc.)

# --- Scheduler Job ---
async def check_expiring_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    """Sends notifications for subscriptions that are about to expire."""
    # (Implementation for this function remains the same as before)
    pass

# --- Main Application Runner ---
async def main() -> None:
    """Initializes the database, sets up the application, and starts all components."""
    # Create the database tables if they don't exist
    database.create_db()
    
    # Build the application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Add all command and message handlers
    application.add_handler(CommandHandler("start", start_command))
    # ... (Add all your other handlers here)
    application.add_handler(CallbackQueryHandler(main_callback_handler))

    # --- THE FIX IS HERE ---
    # Initialize the scheduler separately
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    # Add the job to the scheduler, passing the bot instance correctly
    scheduler.add_job(check_expiring_subscriptions, 'cron', hour=9, minute=0, args=[application.bot])
    # Start the scheduler
    scheduler.start()

    print("Bot and scheduler are running. Starting polling...")

    # This runs the bot's polling loop. Since the scheduler is already started and
    # running on the same asyncio loop, they will work together concurrently.
    await application.run_polling()

if __name__ == "__main__":
    try:
        # Run the main async function
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped gracefully.")