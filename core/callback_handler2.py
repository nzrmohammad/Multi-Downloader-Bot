import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import get_or_create_user, can_download, increment_download_count, get_users_paginated, set_user_plan
from database.database import SessionLocal
from database.models import FileCache, Ticket
from tasks import download_task

# --- Constants ---
USERS_PER_PAGE = 10

# --- Main Callback Handler ---

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    prefix = data[0]

    if prefix in ['yt', 'sc', 'deezer']:
        await handle_download_callback(update, context)
    elif prefix == 'admin':
        await handle_admin_callback(update, context)
    elif prefix == 'user':
        await handle_user_callback(update, context)
    elif prefix == 'reply':
        await handle_reply_callback(update, context)

# --- Download Callback Logic ---

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_or_create_user(update)
    data = query.data.split(':')
    service, quality, resource_id = data
    
    if not can_download(user):
        await query.edit_message_text("شما به حد مجاز دانلود روزانه خود رسیده‌اید. 😕")
        return

    # Check cache
    db = SessionLocal()
    cached_file = db.query(FileCache).filter(FileCache.original_url.like(f"%{resource_id}%")).first()
    db.close()
    
    if cached_file:
        await query.edit_message_text("✅ فایل از آرشیو پیدا شد. در حال ارسال...")
        if cached_file.file_type == 'audio':
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=cached_file.file_id)
        else:
            await context.bot.send_video(chat_id=query.message.chat_id, video=cached_file.file_id)
        increment_download_count(user.user_id)
        await query.message.delete()
        return

    # Enqueue download task
    await query.edit_message_text("✅ درخواست شما در صف دانلود قرار گرفت. به محض آماده شدن، فایل برایتان ارسال خواهد شد.")
    download_task.delay(user.user_id, 'http://' + resource_id, quality, service, resource_id)
    
# --- Admin Panel Logic ---

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split(':')
    command = data[1]

    if command == 'main_menu':
        await query.edit_message_text("بازگشت به منوی اصلی ادمین.")
        await context.bot.send_message(chat_id=query.message.chat_id, text="لطفا از دستور /admin برای باز کردن منو استفاده کنید.")
    
    elif command == 'list_users':
        page = int(data[2])
        users, total_users = get_users_paginated(page=page, per_page=USERS_PER_PAGE)
        
        text = "👥 **لیست کاربران ربات:**\n\n"
        for user in users:
            status_emoji = "⭐" if user.subscription_tier != 'free' else "🆓"
            text += f"{status_emoji} `{user.user_id}` @{user.username or 'N/A'}\n"
        
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        text += f"\nصفحه {page} از {total_pages}"
        
        keyboard_nav = []
        if page > 1:
            keyboard_nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:list_users:{page-1}"))
        if page < total_pages:
            keyboard_nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:list_users:{page+1}"))
        
        keyboard = [keyboard_nav, [InlineKeyboardButton("بازگشت به منو", callback_data="admin:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    # ... (other admin command logic like search_user, broadcast, etc.)

# --- User Panel Logic ---

async def handle_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split(':')
    command = data[1]

    if command == 'close_panel':
        await query.message.delete()
    elif command == 'subscribe':
        await context.bot.send_message(chat_id=query.message.chat_id, text="برای تمدید اشتراک از دستور /subscribe استفاده کنید.")

# --- Ticket Reply Logic ---

async def handle_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # ... (logic to reply to a specific ticket)
    pass