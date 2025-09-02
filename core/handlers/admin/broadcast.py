# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/broadcast.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.database import AsyncSessionLocal
from core.handlers import user_manager
from . import states

async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت پیام برای ارسال همگانی."""
    context.user_data['broadcast_message'] = update.message
    async with AsyncSessionLocal() as session:
        user_count = len(await user_manager.get_all_user_ids(session))
    keyboard = [[InlineKeyboardButton("✅ ارسال", callback_data="admin:broadcast_confirm")], [InlineKeyboardButton("❌ لغو", callback_data="admin:main")]]
    await update.message.reply_text(f"این پیام برای **{user_count}** کاربر ارسال خواهد شد. تایید می‌کنید؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return states.ADMIN_MAIN

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """اجرای ارسال پیام همگانی."""
    query = update.callback_query
    await query.edit_message_text("⏳ در حال ارسال پیام‌ها...")
    message = context.user_data.pop('broadcast_message', None)
    if not message:
        await query.edit_message_text("خطا: پیامی یافت نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
        return states.ADMIN_MAIN

    async with AsyncSessionLocal() as session:
        user_ids = await user_manager.get_all_user_ids(session)
    
    successful, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=message.chat_id, message_id=message.message_id)
            successful += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)
    
    await query.edit_message_text(f"✅ **ارسال تمام شد**\n\n▪️ موفق: {successful}\n▪️ ناموفق: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
    return states.ADMIN_MAIN