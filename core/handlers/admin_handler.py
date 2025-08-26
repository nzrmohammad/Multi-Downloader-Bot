from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.user_manager import get_users_paginated
from .menu_handler import get_main_menu_keyboard # برای دکمه بازگشت به منوی اصلی
import config

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

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
        
        keyboard = [nav_buttons, [InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت", callback_data="admin:main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')