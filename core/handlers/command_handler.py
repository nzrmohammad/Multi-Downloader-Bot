# core/handlers/command_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database import AsyncSessionLocal
from core.handlers import user_manager
from .menu_handler import get_main_menu_keyboard
from .plans_handler import show_plans
from .locales import get_text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and offers language selection if they are new."""
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)

    # If the user is new, their language will be the default 'fa'.
    # We can prompt them to select a language.
    if user.total_downloads == 0: # A simple way to check for a new user
        keyboard = [
            [
                InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en"),
                InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang:fa")
            ]
        ]
        await update.message.reply_text(
            "Please select your language / لطفا زبان خود را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        start_message = get_text('welcome', user.language)
        await update.message.reply_text(
            start_message,
            reply_markup=get_main_menu_keyboard(user.user_id, user.language)
        )

async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /plans command."""
    await show_plans(update, context)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline queries. (Placeholder for now)"""
    # This function can be expanded later to provide inline search results.
    query = update.inline_query.query
    if not query:
        return
    results = []
    await context.bot.answer_inline_query(update.inline_query.id, results)