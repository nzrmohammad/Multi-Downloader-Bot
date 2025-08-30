from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import get_or_create_user, get_download_stats
import config
from .locales import get_text

# --- Keyboards ---

def get_main_menu_keyboard(user_id, lang='en'):
    """Returns the new, cleaner main menu with emojis from locales."""
    keyboard = [
        [InlineKeyboardButton(get_text('menu_help', lang), callback_data="menu:help_link")],
        [InlineKeyboardButton(get_text('menu_account', lang), callback_data="account:main")],
        [InlineKeyboardButton(get_text('menu_settings', lang), callback_data="settings:main")],
        [InlineKeyboardButton(get_text('menu_about', lang), callback_data="about:main")],
    ]
    if user_id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    lang = user.language
    command = query.data.split(':')[1]

    if command == 'main':
        main_text = get_text('welcome', lang)
        await query.edit_message_text(text=main_text, reply_markup=get_main_menu_keyboard(user.user_id, lang))
    
    elif command == 'help_link':
        help_text = "برای دانلود، کافی است لینک مورد نظر خود را از سرویس‌های پشتیبانی‌شده ارسال کنید."
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]]
        await query.edit_message_text(text=help_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    lang = user.language

    # Build the stats text
    stats = get_download_stats(user.user_id)
    stats_text = ""
    if stats:
        for service, count in stats.items():
            stats_text += f"▪️ **{service.capitalize()}:** `{count}`\n"
    else:
        stats_text = "شما هنوز دانلودی نداشته‌اید."

    account_text = (
        f"**⭐️ حساب کاربری شما**\n\n"
        f"**اشتراک فعلی:** `{user.subscription_tier.capitalize()}`\n"
        f"**مجموع دانلودها:** `{user.total_downloads}`\n\n"
        f"**آمار دانلود بر اساس سرویس:**\n{stats_text}\n\n"
        f"برای ارتقاء اشتراک و افزایش محدودیت‌ها، با پشتیبانی در تماس باشید."
    )

    keyboard = [
        [InlineKeyboardButton("💎 مشاهده تمام پلن‌ها", callback_data="plans:show")],
        [InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]
    ]
    await query.edit_message_text(text=account_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    lang = user.language
    command = query.data.split(':')[1]

    if command == 'main':
        text = get_text('settings_main_text', lang)
        keyboard = [
            [InlineKeyboardButton(get_text('settings_language', lang), callback_data="settings:lang")],
            [InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif command == 'lang':
        text = get_text('settings_language_select', lang)
        keyboard = [
            [
                InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en"),
                InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang:fa")
            ],
            [InlineKeyboardButton(get_text('back_button', lang), callback_data="settings:main")]
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    lang = user.language
    
    about_text = (
        "**ℹ️ درباره ربات**\n\n"
        "این ربات برای دانلود آسان محتوا از سرویس‌های مختلف ساخته شده است.\n\n"
        "▪️ **پشتیبانی:** @YourAdminUsername\n"
        "▪️ **کانال آپدیت‌ها:** @YourChannelUsername\n\n"
        "برای حمایت مالی از پروژه و کمک به پایدار ماندن سرورها می‌توانید از طریق لینک زیر اقدام کنید."
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 حمایت مالی", url="https://your-donation-link.com")],
        [InlineKeyboardButton("⬅️ " + get_text('back_button', lang), callback_data="menu:main")]
    ]
    await query.edit_message_text(text=about_text, reply_markup=InlineKeyboardMarkup(keyboard))