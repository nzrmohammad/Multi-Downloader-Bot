from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import get_or_create_user, set_user_quality_setting
import config

# --- Keyboards ---

def get_main_menu_keyboard(user_id):
    """Returns the main menu inline keyboard with a two-column layout."""
    keyboard = [
        # دو ستون در یک ردیف
        [
            InlineKeyboardButton("⭐ اشتراک‌ها", callback_data="menu:subscriptions"),
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings:main")
        ],
        # یک ستون در ردیف بعدی
        [InlineKeyboardButton("🔗 راهنمای لینک و پشتیبانی", callback_data="menu:help_support")],
    ]
    if user_id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="menu:main")]])

# --- Handlers ---

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    command = query.data.split(':')[1]

    if command == 'main':
        main_text = "🤖 به ربات دانلودر خوش آمدید!\n\nلطفا یکی از گزینه‌های زیر را انتخاب کنید:"
        await query.edit_message_text(text=main_text, reply_markup=get_main_menu_keyboard(user.user_id))

    elif command == 'help_support':
        help_text = (
            "**راهنمای ارسال لینک:**\n"
            "برای دانلود، کافی است لینک مورد نظر خود را از سرویس‌های پشتیبانی‌شده ارسال کنید.\n\n"
            "**پشتیبانی:**\n"
            "برای خرید اشتراک یا راهنمایی با ادمین در ارتباط باشید: @YourAdminUsername"
        )
        await query.edit_message_text(text=help_text, reply_markup=get_back_to_menu_keyboard(), parse_mode='Markdown')

    elif command == 'subscriptions':
        status_text = (
            f"**وضعیت فعلی شما:** اشتراک `{user.subscription_tier.capitalize()}`\n\n"
            "**لیست اشتراک‌های موجود:**\n"
            "**🥈 نقره‌ای:** ۳۰ دانلود روزانه\n"
            "**🥇 طلایی:** دانلود نامحدود + پلی‌لیست یوتیوب\n"
            "**💎 پلاتینیوم:** تمام امکانات طلایی + پلی‌لیست اسپاتیفای\n\n"
            "برای خرید با پشتیبانی در ارتباط باشید."
        )
        await query.edit_message_text(text=status_text, reply_markup=get_back_to_menu_keyboard(), parse_mode='Markdown')

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    parts = query.data.split(':')
    command = parts[1]

    if command == 'main':
        text = "⚙️ **تنظیمات**\n\nدر این بخش می‌توانید کیفیت دانلود پیش‌فرض برای هر سرویس را مشخص کنید."
        keyboard = [
            [InlineKeyboardButton(f"یوتیوب ({user.settings_yt_quality})", callback_data="settings:platform:yt")],
            [InlineKeyboardButton(f"اسپاتیفای ({user.settings_spotify_quality})", callback_data="settings:platform:spotify")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="menu:main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif command == 'platform':
        platform = parts[2]
        if platform == 'yt':
            text = "کیفیت پیش‌فرض برای **یوتیوب** را انتخاب کنید:"
            keyboard = [
                [InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data="settings:set:yt:audio")],
                [InlineKeyboardButton("🎬 ویدیو 720p", callback_data="settings:set:yt:video_720")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="settings:main")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif command == 'set':
        platform = parts[2]
        quality = parts[3]
        set_user_quality_setting(user.user_id, platform, quality)
        user = get_or_create_user(update)
        await query.answer(f"تنظیمات با موفقیت ذخیره شد: {quality}")
        
        text = "⚙️ **تنظیمات**\n\nتنظیمات شما به‌روز شد."
        keyboard = [
            [InlineKeyboardButton(f"یوتیوب ({user.settings_yt_quality})", callback_data="settings:platform:yt")],
            [InlineKeyboardButton(f"اسپاتیفای ({user.settings_spotify_quality})", callback_data="settings:platform:spotify")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="menu:main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')