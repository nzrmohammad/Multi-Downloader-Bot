import os
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import (
    get_or_create_user, can_download, increment_download_count, 
    log_activity, get_users_paginated, set_user_quality_setting
)
from database.database import SessionLocal
from database.models import FileCache
import config

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Keyboards ---

def get_main_menu_keyboard(user_id):
    """Returns the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔗 راهنمای ارسال لینک", callback_data="menu:help_link")],
        [InlineKeyboardButton("⭐ وضعیت و خرید اشتراک", callback_data="menu:subscriptions")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings:main")],
        [InlineKeyboardButton("💬 پشتیبانی", callback_data="menu:support")],
    ]
    if user_id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="menu:main")]])

# --- Main Handler Router ---

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    prefix = data[0]

    if prefix == 'menu':
        await handle_menu_callback(update, context)
    elif prefix == 'admin':
        await handle_admin_callback(update, context)
    elif prefix == 'settings':
        await handle_settings_callback(update, context)
    elif prefix in ['yt', 'sc', 'spotify']:
        await handle_download_callback(update, context)
    else:
        user_id = update.effective_user.id
        await query.edit_message_text("دستور ناشناخته است.", reply_markup=get_main_menu_keyboard(user_id))


# --- Menu & Subscription Logic ---
# (This part remains the same as the previous version)
async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    command = query.data.split(':')[1]

    if command == 'main':
        main_text = "🤖 به ربات دانلودر خوش آمدید!\n\nلطفا یکی از گزینه‌های زیر را انتخاب کنید:"
        await query.edit_message_text(text=main_text, reply_markup=get_main_menu_keyboard(user.user_id))

    elif command == 'help_link':
        help_text = "برای دانلود، کافی است لینک مورد نظر خود را از سرویس‌های پشتیبانی‌شده ارسال کنید."
        await query.edit_message_text(text=help_text, reply_markup=get_back_to_menu_keyboard())

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

    elif command == 'support':
        support_text = "برای خرید اشتراک یا راهنمایی با ادمین در ارتباط باشید: @YourAdminUsername"
        await query.edit_message_text(text=support_text, reply_markup=get_back_to_menu_keyboard())

# --- Settings Logic ---

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
            [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="menu:main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif command == 'platform':
        platform = parts[2]
        if platform == 'yt':
            text = "کیفیت پیش‌فرض برای **یوتیوب** را انتخاب کنید:"
            keyboard = [
                [InlineKeyboardButton("🎵 فقط صدا (MP3)", callback_data="settings:set:yt:audio")],
                [InlineKeyboardButton("🎬 ویدیو 720p", callback_data="settings:set:yt:video_720")],
                [InlineKeyboardButton("⬅️ بازگشت به تنظیمات", callback_data="settings:main")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        # Add other platforms like Spotify if needed

    elif command == 'set':
        platform = parts[2]
        quality = parts[3]
        set_user_quality_setting(user.user_id, platform, quality)
        
        # Refresh user object to get new settings
        user = get_or_create_user(update)

        await query.answer(f"تنظیمات با موفقیت ذخیره شد: {quality}")
        
        # Go back to the main settings menu to show the updated value
        text = "⚙️ **تنظیمات**\n\nتنظیمات شما به‌روز شد."
        keyboard = [
            [InlineKeyboardButton(f"یوتیوب ({user.settings_yt_quality})", callback_data="settings:platform:yt")],
            [InlineKeyboardButton(f"اسپاتیفای ({user.settings_spotify_quality})", callback_data="settings:platform:spotify")],
            [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="menu:main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- Admin Panel Callback Logic ---

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all callbacks related to the admin panel."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Double-check if the user is the admin
    if user_id != config.ADMIN_ID:
        await query.edit_message_text("شما دسترسی به این بخش را ندارید.", reply_markup=get_main_menu_keyboard(user_id))
        return

    command_parts = query.data.split(':')
    command = command_parts[1]

    if command == 'main':
        admin_text = "👑 به پنل مدیریت خوش آمدید. لطفا یک گزینه را انتخاب کنید:"
        keyboard = [
            [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin:list_users:1")],
            [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="menu:main")]
        ]
        await query.edit_message_text(text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif command == 'list_users':
        page = int(command_parts[2])
        users, total_users = get_users_paginated(page=page, per_page=10)
        
        text = "👥 **لیست کاربران ربات:**\n\n"
        for user in users:
            status_emoji = "⭐" if user.subscription_tier != 'free' else "🆓"
            text += f"{status_emoji} `{user.user_id}` - @{user.username or 'N/A'}\n"
        
        total_pages = (total_users + 9) // 10
        text += f"\nصفحه {page} از {total_pages}"
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:list_users:{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:list_users:{page+1}"))
        
        keyboard = [
            nav_buttons,
            [InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت", callback_data="admin:main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# --- Download Callback Logic ---

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the entire download process initiated from a callback button."""
    query = update.callback_query
    user = get_or_create_user(update)
    
    # ... (previous code)
    
    # --- رفع خطا: اضافه کردن هدر برای جلوگیری از خطای 403 ---
    ydl_opts_base = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }

    # ... (previous code)
    
    filename = None
    try:
        data = query.data.split(':')
        service, quality, resource_id = data

        if not can_download(user):
            await query.edit_message_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕", reply_markup=get_back_to_menu_keyboard())
            return

        if service == 'yt':
            url = f"https://www.youtube.com/watch?v={resource_id}"
        else:
            url = 'http://' + resource_id

        db = SessionLocal()
        cached_file = db.query(FileCache).filter(FileCache.original_url == url).first()
        db.close()

        if cached_file:
            # ... (cache logic remains the same)
            return

        await query.edit_message_text("در حال دانلود... لطفاً صبر کنید (این فرآیند ممکن است کمی طول بکشد).")
        
        if quality == 'audio':
            ydl_opts = {**ydl_opts_base, 'format': 'bestaudio/best', 'outtmpl': f'%(title)s_{resource_id}.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]}
        else:
            resolution = quality.split('_')[1]
            ydl_opts = {**ydl_opts_base, 'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]', 'outtmpl': f'%(title)s_{resource_id}.%(ext)s'}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_filename = ydl.prepare_filename(info)
            filename = os.path.splitext(original_filename)[0] + '.mp3' if quality == 'audio' else original_filename

        with open(filename, 'rb') as file_to_send:
            if quality == 'audio':
                sent_message = await context.bot.send_audio(chat_id=user.user_id, audio=file_to_send, title=info.get('title', 'Audio File'))
                file_id, file_type, file_size = sent_message.audio.file_id, 'audio', sent_message.audio.file_size
            else:
                sent_message = await context.bot.send_video(chat_id=user.user_id, video=file_to_send, caption=info.get('title', 'Video File'))
                file_id, file_type, file_size = sent_message.video.file_id, 'video', sent_message.video.file_size
        
        db = SessionLocal()
        db.add(FileCache(original_url=url, file_id=file_id, file_type=file_type, file_size=file_size))
        db.commit()
        db.close()
        
        increment_download_count(user.user_id)
        log_activity(user.user_id, 'download', details=f"{service}:{quality}")
        await query.edit_message_text("✅ دانلود شما با موفقیت انجام و ارسال شد.")

    except Exception as e:
        logging.error(f"Direct download error: {e}")
        await query.edit_message_text("❌ متاسفانه در هنگام دانلود مشکلی پیش آمد. لطفاً دوباره تلاش کنید.", reply_markup=get_back_to_menu_keyboard())
    
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)