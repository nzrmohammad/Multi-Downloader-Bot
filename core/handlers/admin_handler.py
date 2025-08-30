# core/handlers/admin_handler.py

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from core.user_manager import (
    get_users_paginated,
    find_user_by_id,
    set_user_plan,
    delete_user_by_id,
    get_all_user_ids,
)
from .service_manager import get_all_statuses, toggle_service_status
import config

logger = logging.getLogger(__name__)

# مراحل مکالمه برای ادمین
(
    ADMIN_MAIN,
    AWAITING_USER_ID,
    AWAITING_BROADCAST_MESSAGE,
    AWAITING_BROADCAST_CONFIRMATION,
) = range(4)


# --- توابع سازنده منو ---
async def build_service_management_menu():
    """منوی دکمه‌های مدیریت سرویس‌ها را می‌سازد."""
    statuses = get_all_statuses()
    keyboard = []
    # سرویس‌ها را بر اساس نام مرتب می‌کنیم تا منو همیشه یکسان باشد
    for service in sorted(statuses, key=lambda s: s.service_name):
        status_emoji = "✅" if service.is_enabled else "❌"
        button_text = f"{status_emoji} {service.service_name.capitalize()}"
        callback_data = f"admin:toggle_service:{service.service_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)


async def build_user_management_panel(user):
    """منوی مدیریت برای یک کاربر خاص را می‌سازد."""
    if not user:
        return None, None

    text = (
        f"**👤 مدیریت کاربر:** `{user.user_id}`\n"
        f"**نام کاربری:** @{user.username or 'N/A'}\n"
        f"**اشتراک:** `{user.subscription_tier}`\n"
        f"**انقضا:** `{user.subscription_expiry_date or 'N/A'}`\n"
        f"**مجموع دانلودها:** `{user.total_downloads}`"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕ تمدید ۳۰ روز", callback_data=f"admin:user_extend_30:{user.user_id}"),
            InlineKeyboardButton("⭐️ ارتقاء به طلایی", callback_data=f"admin:user_promote_gold:{user.user_id}"),
        ],
        [InlineKeyboardButton("🗑 حذف کامل کاربر",callback_data=f"admin:user_delete_confirm:{user.user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت به پنل مدیریت", callback_data="admin:main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نقطه ورود به پنل مدیریت و نمایش منوی اصلی ادمین."""
    query = update.callback_query
    user = query.from_user

    if user.id != config.ADMIN_ID:
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    admin_text = "👑 **پنل مدیریت**\n\nلطفا یک گزینه را انتخاب کنید:"
    keyboard = [
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin:list_users:1")],
        [InlineKeyboardButton("🔧 مدیریت سرویس‌ها", callback_data="admin:manage_services")],
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:search_user_prompt")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin:broadcast_start")],
        [InlineKeyboardButton("⬅️ خروج از پنل", callback_data="admin:exit")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # چون ورود همیشه با دکمه است، پیام را ویرایش می‌کنیم
    await query.edit_message_text(text=admin_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    return ADMIN_MAIN

async def admin_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی تمام دکمه‌های داخل پنل مدیریت."""
    query = update.callback_query
    await query.answer()
    
    command_parts = query.data.split(":")
    command = command_parts[1]

    # --- ناوبری اصلی ---
    if command == "main":
        return await admin_entry(update, context)
    if command == "exit":
        await query.edit_message_text("شما از پنل مدیریت خارج شدید. برای ورود مجدد از منوی اصلی اقدام کنید.")
        return ConversationHandler.END

    # --- مدیریت سرویس‌ها ---
    if command == "manage_services":
        text = "🔧 **مدیریت سرویس‌ها**\n\nوضعیت سرویس مورد نظر را تغییر دهید:"
        await query.edit_message_text(text=text, reply_markup=await build_service_management_menu(), parse_mode='Markdown')
        return ADMIN_MAIN
    if command == "toggle_service":
        service_name = command_parts[2]
        toggle_service_status(service_name)
        await query.edit_message_reply_markup(reply_markup=await build_service_management_menu())
        return ADMIN_MAIN

    # --- مدیریت کاربران ---
    if command == "list_users":
        page = int(command_parts[2])
        users, total_users = get_users_paginated(page=page, per_page=10)
        text = f"👥 **لیست کاربران ({total_users} کل):**\n\n"
        for user in users:
            status_emoji = "⭐" if user.subscription_tier != 'free' else "🆓"
            text += f"{status_emoji} `{user.user_id}` - @{user.username or 'N/A'}\n"
        total_pages = (total_users + 9) // 10
        text += f"\nصفحه {page} از {total_pages}"
        nav_buttons = []
        if page > 1: nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:list_users:{page-1}"))
        if page < total_pages: nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:list_users:{page+1}"))
        keyboard = [nav_buttons, [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MAIN

    if command == 'search_user_prompt':
        prompt_message = await query.edit_message_text("لطفاً ID عددی کاربر مورد نظر را برای جستجو ارسال کنید. برای لغو /cancel_admin را ارسال کنید.")
        context.user_data['admin_prompt_message_id'] = prompt_message.message_id
        return AWAITING_USER_ID
        
    if command == 'user_extend_30':
        user_id_to_manage = int(command_parts[2])
        set_user_plan(user_id_to_manage, 'silver', 30)
        user = find_user_by_id(user_id_to_manage)
        text, reply_markup = await build_user_management_panel(user)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer("✅ اشتراک کاربر برای ۳۰ روز تمدید شد.")
        return ADMIN_MAIN

    if command == 'user_promote_gold':
        user_id_to_manage = int(command_parts[2])
        set_user_plan(user_id_to_manage, 'gold', 365)
        user = find_user_by_id(user_id_to_manage)
        text, reply_markup = await build_user_management_panel(user)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer("✅ کاربر به پلن طلایی ارتقا یافت.")
        return ADMIN_MAIN
        
    if command == 'user_delete_confirm':
        user_id_to_manage = int(command_parts[2])
        keyboard = [
            [InlineKeyboardButton(" بله، حذف کن 🗑", callback_data=f"admin:user_delete_execute:{user_id_to_manage}")],
            [InlineKeyboardButton(" خیر، بازگرد ⬅️", callback_data=f"admin:user_manage_panel:{user_id_to_manage}")]
        ]
        await query.edit_message_text(f"آیا از حذف کامل کاربر `{user_id_to_manage}` مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MAIN
    
    if command == 'user_delete_execute':
        user_id_to_manage = int(command_parts[2])
        delete_user_by_id(user_id_to_manage)
        await query.edit_message_text(f"✅ کاربر `{user_id_to_manage}` با موفقیت حذف شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
        return ADMIN_MAIN

    if command == 'user_manage_panel':
        user_id_to_manage = int(command_parts[2])
        user = find_user_by_id(user_id_to_manage)
        text, reply_markup = await build_user_management_panel(user)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return ADMIN_MAIN

    # --- پیام همگانی ---
    if command == 'broadcast_start':
        await query.edit_message_text("لطفاً پیام خود را برای ارسال وارد کنید.\n\nبرای لغو /cancel_admin را ارسال کنید.")
        return AWAITING_BROADCAST_MESSAGE
        
    if command == 'broadcast_confirm_send':
        return await broadcast_execute(update, context)
        
    return ADMIN_MAIN


async def receive_user_id_for_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = int(update.message.text)
        user = find_user_by_id(user_id)
        
        if 'admin_prompt_message_id' in context.user_data:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data.pop('admin_prompt_message_id'))
        await update.message.delete()
        
        if user:
            text, reply_markup = await build_user_management_panel(user)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"کاربری با ID `{user_id}` یافت نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
            
    except (ValueError, KeyError):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ورودی نامعتبر است.")
        
    return ADMIN_MAIN


async def broadcast_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پیام ادمین را دریافت کرده و برای تایید نمایش می‌دهد."""
    context.user_data['broadcast_message'] = update.message
    user_count = len(get_all_user_ids())
    
    keyboard = [
        [InlineKeyboardButton("✅ بله، ارسال کن", callback_data="admin:broadcast_confirm_send")],
        [InlineKeyboardButton("❌ خیر، لغو کن", callback_data="admin:main")]
    ]
    await update.message.reply_text(f"این پیام برای **{user_count}** کاربر ارسال خواهد شد. آیا تایید می‌کنید؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_MAIN

async def broadcast_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پیام را به تمام کاربران ارسال می‌کند."""
    query = update.callback_query
    await query.edit_message_text("⏳ در حال ارسال پیام‌ها...")
    
    message_to_send = context.user_data.pop('broadcast_message', None)
    if not message_to_send:
        await query.edit_message_text("خطا: پیامی برای ارسال یافت نشد.")
        return ADMIN_MAIN

    user_ids = get_all_user_ids()
    successful_sends, failed_sends = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=message_to_send.chat_id, message_id=message_to_send.message_id)
            successful_sends += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {user_id}: {e}")
            failed_sends += 1
        await asyncio.sleep(0.1)

    report_text = (
        f"✅ **گزارش ارسال**\n\n"
        f"▪️ موفق: {successful_sends}\n"
        f"▪️ ناموفق (کاربران مسدود کرده): {failed_sends}"
    )
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت به پنل", callback_data="admin:main")]]
    await query.edit_message_text(report_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_MAIN

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """هر نوع مکالمه ادمین را لغو می‌کند."""
    context.user_data.clear()
    await update.message.reply_text("عملیات لغو شد.")
    # چون نمی‌دانیم در چه پیامی هستیم، نمی‌توانیم آن را ویرایش کنیم.
    # به کاربر می‌گوییم که دوباره از منوی اصلی وارد شود.
    await update.message.reply_text("برای ورود مجدد به پنل، از منوی اصلی اقدام کنید.")
    return ConversationHandler.END


# --- ConversationHandler نهایی ---
admin_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_entry, pattern='^admin:main$')],
    states={
        ADMIN_MAIN: [CallbackQueryHandler(admin_router, pattern='^admin:.*')],
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id_for_management)],
        AWAITING_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_receive_message)],
    },
    fallbacks=[CommandHandler('cancel_admin', cancel_conversation)],
    allow_reentry=True
)