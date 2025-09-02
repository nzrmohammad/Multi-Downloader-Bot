# core/handlers/menu_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database import AsyncSessionLocal
from core.handlers.user_manager import get_download_stats, set_user_quality_setting, User
import config
from .locales import get_text
from .service_manager import get_all_statuses
from core.settings import settings

# --- Keyboards ---

def get_main_menu_keyboard(user_id, lang='en'):
    """منوی اصلی دو ستونی جدید را به همراه دکمه پنل مدیریت (در صورت لزوم) برمی‌گرداند."""
    keyboard = [
        [
            InlineKeyboardButton(get_text('menu_help', lang), callback_data="menu:help_link"),
            InlineKeyboardButton(get_text('menu_services', lang), callback_data="services:show")
        ],
        [
            InlineKeyboardButton(get_text('menu_account', lang), callback_data="account:main"),
            InlineKeyboardButton(get_text('menu_settings', lang), callback_data="settings:main")
        ],
        [InlineKeyboardButton(get_text('menu_about', lang), callback_data="about:main")],
    ]
    if user_id == settings.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    query = update.callback_query
    lang = user.language
    command = query.data.split(':')[1]

    if command == 'main':
        main_text = get_text('welcome', lang)
        await query.edit_message_text(text=main_text, reply_markup=get_main_menu_keyboard(user.user_id, lang))
    
    elif command == 'help_link':
        help_text = "برای دانلود، کافی است لینک مورد نظر خود را از سرویس‌های پشتیبانی‌شده ارسال کنید."
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]]
        await query.edit_message_text(text=help_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_service_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    """وضعیت سرویس‌ها و دسترسی کاربر به آن‌ها را نمایش می‌دهد."""
    query = update.callback_query
    lang = user.language
    
    premium_services = ['pornhub', 'redtube', 'twitch']

    # FIX: Removed the 'session' argument from the call
    statuses = await get_all_statuses()
    
    status_text = get_text('services_title', lang)
    if statuses:
        for s in sorted(statuses, key=lambda s: s.service_name):
            emoji = "✅" if s.is_enabled else "❌"
            access_emoji = ""
            
            if s.service_name.lower() in premium_services and user.subscription_tier == 'free':
                access_emoji = "🔒"
            
            status_text += f"{emoji} **{s.service_name.capitalize()}** {access_emoji}\n"
        
        status_text += "\n" + get_text('service_legend', lang)
    else:
        status_text += get_text('no_services', lang)

    keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]]
    
    await query.edit_message_text(
        text=status_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def handle_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    query = update.callback_query
    lang = user.language

    tier_limits = {
        'free': 5, 'bronze': 30, 'silver': 100,
        'gold': float('inf'), 'diamond': float('inf')
    }
    limit = tier_limits.get(user.subscription_tier, 0)
    
    if limit == float('inf'):
        daily_usage_text = "نامحدود"
    else:
        remaining = limit - user.daily_downloads
        daily_usage_text = f"{user.daily_downloads} / {limit} (<b>{remaining}</b> باقی‌مانده)"

    stats = get_download_stats(user)
    stats_text = ""
    if stats:
        sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)
        for service, count in sorted_stats:
            stats_text += f"▪️ <b>{service.capitalize()}:</b> <code>{count}</code>\n"
    else:
        stats_text = "شما هنوز دانلودی نداشته‌اید."

    account_text = (
        f"⭐️ <b>حساب کاربری شما</b> ⭐️\n\n"
        f"💎 <b>نوع اشتراک:</b> <code>{user.subscription_tier.capitalize()}</code>\n"
        f"📥 <b>دانلودهای امروز:</b> {daily_usage_text}\n"
        f"📈 <b>مجموع دانلودها:</b> <code>{user.total_downloads}</code>\n\n"
        f"<b>آمار تفکیک شده دانلودها:</b>\n{stats_text}"
    )

    keyboard = [
        [InlineKeyboardButton("🎁 ثبت کد تخفیف", callback_data="promo:start_redeem")],
        [InlineKeyboardButton("💎 مشاهده و ارتقاء پلن‌ها", callback_data="plans:show")],
        [InlineKeyboardButton(get_text('back_button', lang), callback_data="menu:main")]
    ]
    
    await query.edit_message_text(text=account_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    """منوی تنظیمات را مدیریت می‌کند."""
    query = update.callback_query
    lang = user.language
    command = query.data.split(':')[1]

    if command == 'main':
        text = get_text('settings_main_text', lang)
        keyboard = [
            [InlineKeyboardButton(f"یوتیوب ({user.settings_yt_quality})", callback_data="settings:platform:yt")],
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

    elif command == 'platform':
        platform = query.data.split(':')[2]
        if platform == 'yt':
            text = "کیفیت پیش‌فرض برای دانلود از **یوتیوب** را انتخاب کنید:"
            keyboard = [
                [
                    InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data="settings:set:yt:audio"),
                    InlineKeyboardButton("🎬 ویدیو (720p)", callback_data="settings:set:yt:video_720")
                ],
                [InlineKeyboardButton(get_text('back_button', lang), callback_data="settings:main")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif command == 'set':
        platform = query.data.split(':')[2]
        quality = query.data.split(':')[3]
        async with AsyncSessionLocal() as session:
            await set_user_quality_setting(session, user, platform, quality)
        
        await query.answer(f"کیفیت پیش‌فرض برای {platform.upper()} به {quality} تغییر کرد.")
        
        # Refresh the user object to show updated settings
        user_id = update.effective_user.id
        async with AsyncSessionLocal() as session:
            refreshed_user = await session.get(User, user_id)
        
        await handle_settings_callback(update, context, refreshed_user)


async def handle_about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    query = update.callback_query
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
    await query.edit_message_text(text=about_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')