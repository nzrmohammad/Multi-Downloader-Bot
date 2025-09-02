# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/callbacks.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.database import AsyncSessionLocal
from core.handlers import user_manager
from core.settings import settings
from core.handlers.menu_handler import get_main_menu_keyboard
from .ui import build_admin_main_menu
from .promo_codes import promo_main_menu

# Import states from __init__.py
from . import states

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نقطه ورود به پنل مدیریت."""
    query = update.callback_query
    if query.from_user.id != settings.ADMIN_ID:
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("👑 **پنل مدیریت**", reply_markup=await build_admin_main_menu(), parse_mode="Markdown")
    return states.ADMIN_MAIN

async def main_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی اصلی دستورات از منوی اصلی ادمین."""
    query = update.callback_query
    await query.answer()
    command = query.data.split(":")[1]

    async with AsyncSessionLocal() as session:
        if command == "exit_to_main_menu":
            user = await user_manager.find_user_by_id(session, query.from_user.id)
            await query.edit_message_text("🤖 خوش آمدید!", reply_markup=get_main_menu_keyboard(user.user_id, user.language))
            return ConversationHandler.END

        elif command == "stats":
            stats = await user_manager.get_bot_stats(session)
            service_stats = "\n".join([f"▪️ **{s.capitalize()}:** `{c}`" for s, c in stats['service_counts'].items()]) or "آماری ثبت نشده."
            text = (f"**📊 آمار کلی ربات**\n\n👥 **کل کاربران:** `{stats['total_users']}`\n"
                    f"✨ **کاربران جدید امروز:** `{stats['new_users_today']}`\n"
                    f"📥 **مجموع دانلودها:** `{stats['total_downloads']}`\n\n"
                    f"**تفکیک دانلودها:**\n{service_stats}")
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]), parse_mode='Markdown')
            return states.ADMIN_MAIN

        elif command == "users_main":
            keyboard = [[InlineKeyboardButton("📜 لیست کاربران", callback_data="admin:user_list:1"), InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:user_search_prompt")],
                        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]
            await query.edit_message_text("👥 **مدیریت کاربران**", reply_markup=InlineKeyboardMarkup(keyboard))
            return states.ADMIN_MAIN
            
        elif command == "promo_main":
            return await promo_main_menu(update, context)

        elif command == "broadcast_start":
            await query.edit_message_text("لطفاً پیام خود را برای ارسال وارد کنید. برای لغو /cancel را بفرستید.")
            return states.AWAITING_BROADCAST_MESSAGE
            
    return states.ADMIN_MAIN

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("عملیات لغو شد. بازگشت به پنل مدیریت...", reply_markup=await build_admin_main_menu())
    context.user_data.clear()
    return states.ADMIN_MAIN