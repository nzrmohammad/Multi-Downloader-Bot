# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/user_management.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

from database.database import AsyncSessionLocal
from core import user_manager
from .ui import build_user_management_panel
from . import states

logger = logging.getLogger(__name__)

async def user_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی دستورات مربوط به مدیریت کاربران."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    command = parts[1]
    
    async with AsyncSessionLocal() as session:
        if command == "list":
            page = int(parts[2])
            users, total = await user_manager.get_users_paginated(session, page=page)
            text = f"👥 **لیست کاربران ({total} کل):**\n\n" + "".join([f"{'🚫' if u.is_banned else '✅'} `{u.user_id}` - @{u.username or 'N/A'}\n" for u in users])
            total_pages = (total + 9) // 10
            nav = []
            if page > 1: nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:user_list:{page-1}"))
            if page < total_pages: nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:user_list:{page+1}"))
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([nav, [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]))
        
        elif command == "message_prompt":
            user_id = int(parts[2])
            context.user_data['target_user_id'] = user_id
            await query.edit_message_text(f"لطفاً پیام خود را برای کاربر `{user_id}` وارد کنید. برای لغو /cancel را بفرستید.")
            return states.AWAITING_MESSAGE_TO_USER

        else: # Actions on a specific user
            user_id = int(parts[2])
            user = await user_manager.find_user_by_id(session, user_id)
            if command == 'extend_silver': await user_manager.set_user_plan(session, user, 'silver', 30)
            elif command == 'promote_gold': await user_manager.set_user_plan(session, user, 'gold', 365)
            elif command == 'ban': await user_manager.ban_user(session, user_id)
            elif command == 'unban': await user_manager.unban_user(session, user_id)
            elif command == 'delete_confirm':
                kb = [[InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f"admin:user_delete_execute:{user_id}")], [InlineKeyboardButton("⬅️ خیر", callback_data=f"admin:user_panel:{user_id}")]]
                await query.edit_message_text(f"آیا از حذف کامل کاربر `{user_id}` مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
                return states.ADMIN_MAIN
            elif command == 'delete_execute':
                await user_manager.delete_user_by_id(session, user_id)
                await query.edit_message_text(f"✅ کاربر `{user_id}` حذف شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]))
                return states.ADMIN_MAIN

            # Refresh user object after changes
            await session.refresh(user)
            text, reply_markup = await build_user_management_panel(session, user)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return states.ADMIN_MAIN

async def search_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """درخواست آیدی کاربر برای جستجو."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً ID عددی کاربر را برای مدیریت ارسال کنید. برای لغو /cancel را بفرستید.")
    return states.AWAITING_USER_ID

async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت آیدی کاربر و نمایش پنل مدیریت."""
    try:
        user_id = int(update.message.text)
        async with AsyncSessionLocal() as session:
            user = await user_manager.find_user_by_id(session, user_id)
            await update.message.delete()
            text, reply_markup = await build_user_management_panel(session, user)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
    except (ValueError, KeyError):
        await update.message.reply_text("ورودی نامعتبر است.")
    return states.ADMIN_MAIN

async def receive_message_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پیام را از ادمین دریافت و برای کاربر مورد نظر ارسال می‌کند."""
    target_user_id = context.user_data.pop('target_user_id', None)
    if not target_user_id:
        await update.message.reply_text("خطا: کاربر هدف مشخص نیست. لطفاً دوباره تلاش کنید.")
        return states.ADMIN_MAIN

    try:
        await context.bot.copy_message(chat_id=target_user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        await update.message.reply_text(f"✅ پیام با موفقیت برای کاربر `{target_user_id}` ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ ارسال پیام با خطا مواجه شد: {e}")
        logger.error(f"Failed to send message to {target_user_id}: {e}")

    async with AsyncSessionLocal() as session:
        user = await user_manager.find_user_by_id(session, target_user_id)
        text, reply_markup = await build_user_management_panel(session, user)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
        
    return states.ADMIN_MAIN