from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import get_or_create_user
import config
from .locales import get_text
from datetime import datetime

# The get_main_menu_keyboard function remains the same as before
def get_main_menu_keyboard(user_id, lang='en'):
    keyboard = [
        [
            InlineKeyboardButton(get_text('main_menu_button_updates', lang), callback_data="menu:updates"),
            InlineKeyboardButton(get_text('main_menu_button_support', lang), callback_data="menu:support")
        ],
        [
            InlineKeyboardButton(get_text('main_menu_button_about', lang), callback_data="about:main"),
            InlineKeyboardButton(get_text('main_menu_button_help', lang), callback_data="menu:help"),
            InlineKeyboardButton(get_text('main_menu_button_stats', lang), callback_data="stats:main")
        ],
        [
            InlineKeyboardButton(get_text('main_menu_button_share', lang), callback_data="menu:share"),
            InlineKeyboardButton(get_text('main_menu_button_rate', lang), callback_data="menu:rate"),
            InlineKeyboardButton(get_text('main_menu_button_donate', lang), callback_data="menu:donate")
        ],
        [
            InlineKeyboardButton(get_text('main_menu_button_premium', lang), callback_data="menu:premium"),
            InlineKeyboardButton(get_text('main_menu_button_account', lang), callback_data="menu:account")
        ],
        [
            InlineKeyboardButton(get_text('main_menu_button_settings', lang), callback_data="settings:main")
        ],
        [
            InlineKeyboardButton(get_text('main_menu_button_owner', lang), url="https://t.me/YourUsername")
        ]
    ]
    if user_id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    command = query.data.split(':')[1]
    lang = user.language

    if command == 'main':
        main_text = get_text('welcome', lang)
        await query.edit_message_text(text=main_text, reply_markup=get_main_menu_keyboard(user.user_id, lang))


async def handle_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    command = query.data.split(':')[1]
    lang = user.language

    if command == 'main':
        keyboard = [
            [
                InlineKeyboardButton(get_text('about_menu_button_developer', lang), callback_data="about:developer"),
                InlineKeyboardButton(get_text('about_menu_button_the_bot', lang), callback_data="about:bot")
            ],
            [
                InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")
            ]
        ]
        await query.edit_message_text(text=get_text('about_menu_title', lang), reply_markup=InlineKeyboardMarkup(keyboard))
    elif command == 'bot':
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="about:main")]]
        await query.edit_message_text(text=get_text('bot_info', lang), reply_markup=InlineKeyboardMarkup(keyboard))
    elif command == 'developer':
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="about:main")]]
        await query.edit_message_text(text=get_text('developer_info', lang), reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    parts = query.data.split(':')
    command = parts[1]
    lang = user.language

    if command == 'main':
        keyboard = [
            # Add a button for each service you want to show stats for
            [InlineKeyboardButton(get_text('main_menu_button_spotify', lang), callback_data="stats:spotify")],
            # You can add a YouTube button here later:
            # [InlineKeyboardButton("📊 YouTube Stats", callback_data="stats:youtube")],
            [InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]
        ]
        await query.edit_message_text(
            text=get_text('stats_menu_title', lang),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif command == 'spotify':
        # This is where you would fetch the actual stats for the user
        # For now, we'll just display the static text from locales
        stats_text = get_text('spotify_stats_content', lang)
        
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="stats:main")]]
        
        await query.edit_message_text(
            text=f"**{get_text('main_menu_button_spotify', lang)}**\n\n{stats_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    # You can add another elif for 'youtube' when you're ready


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    command = query.data.split(':')[1]
    lang = user.language

    if command == 'main':
        keyboard = [
            [InlineKeyboardButton(get_text('settings_menu_button_language', lang), callback_data="settings:lang")],
            [InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]
        ]
        await query.edit_message_text(text=get_text('settings_menu_title', lang), reply_markup=InlineKeyboardMarkup(keyboard))

    elif command == 'lang':
        keyboard = [
            [
                InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en"),
                InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang:fa")
            ],
            [InlineKeyboardButton(get_text('back_button', lang), callback_data="settings:main")]
        ]
        await query.edit_message_text(text=get_text('language_selection', lang), reply_markup=InlineKeyboardMarkup(keyboard))