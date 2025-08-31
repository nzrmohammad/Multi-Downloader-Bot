# core/handlers/admin_handler.py

import asyncio
import logging
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)

from database.database import AsyncSessionLocal
from core.settings import settings
from core.user_manager import (
    find_user_by_id, set_user_plan, delete_user_by_id, get_all_user_ids,
    ban_user, unban_user, get_bot_stats, get_users_paginated,
    create_promo_code, get_all_promo_codes, delete_promo_code
)
from .service_manager import get_all_statuses, toggle_service_status
from .menu_handler import get_main_menu_keyboard

logger = logging.getLogger(__name__)

# Stages for ConversationHandler
(
    ADMIN_MAIN, AWAITING_USER_ID, AWAITING_BROADCAST_MESSAGE,
    PROMO_MAIN, PROMO_AWAITING_CODE, PROMO_AWAITING_TIER,
    PROMO_AWAITING_DURATION, PROMO_AWAITING_USES
) = range(8)


# --- Menu Builders ---

async def build_admin_main_menu():
    """منوی اصلی پنل ادمین را ایجاد می‌کند."""
    keyboard = [
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin:stats"), InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin:users_main")],
        [InlineKeyboardButton("🔧 مدیریت سرویس‌ها", callback_data="admin:manage_services"), InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin:broadcast_start")],
        [InlineKeyboardButton("🎁 کدهای تخفیف", callback_data="admin:promo_main")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی ربات", callback_data="admin:exit_to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def build_user_management_panel(user):
    """منوی مدیریت یک کاربر خاص را ایجاد می‌کند."""
    if not user:
        return "**خطا:** کاربر یافت نشد.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]])
        
    ban_text = "✅ آزاد کردن" if user.is_banned else "🚫 مسدود کردن"
    ban_callback = f"admin:user_unban:{user.user_id}" if user.is_banned else f"admin:user_ban:{user.user_id}"
    text = (
        f"**👤 مدیریت کاربر:** `{user.user_id}` | **وضعیت:** `{'مسدود' if user.is_banned else 'فعال'}`\n"
        f"**نام کاربری:** @{user.username or 'N/A'}\n"
        f"**اشتراک:** `{user.subscription_tier}` (انقضا: `{user.subscription_expiry_date or 'N/A'}`)"
    )
    keyboard = [
        [InlineKeyboardButton("🥈 ۳۰ روز نقره‌ای", callback_data=f"admin:user_extend_silver:{user.user_id}"), InlineKeyboardButton("🥇 ۱ سال طلایی", callback_data=f"admin:user_promote_gold:{user.user_id}")],
        [InlineKeyboardButton(ban_text, callback_data=ban_callback), InlineKeyboardButton("🗑 حذف کامل", callback_data=f"admin:user_delete_confirm:{user.user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)

async def build_service_management_menu():
    """منوی مدیریت سرویس‌ها را با اطلاعات از دیتابیس ایجاد می‌کند."""
    statuses = await get_all_statuses()
    keyboard = []
    it = iter(sorted(statuses, key=lambda s: s.service_name))
    for s1 in it:
        s2 = next(it, None)
        row = [InlineKeyboardButton(f"{'✅' if s1.is_enabled else '❌'} {s1.service_name.capitalize()}", callback_data=f"admin:toggle_service:{s1.service_name}")]
        if s2:
            row.append(InlineKeyboardButton(f"{'✅' if s2.is_enabled else '❌'} {s2.service_name.capitalize()}", callback_data=f"admin:toggle_service:{s2.service_name}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

# --- Entry Point ---

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نقطه ورود به پنل مدیریت."""
    query = update.callback_query
    if query.from_user.id != settings.ADMIN_ID:
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END
    await query.edit_message_text("👑 **پنل مدیریت**", reply_markup=await build_admin_main_menu(), parse_mode="Markdown")
    return ADMIN_MAIN

# --- State Handlers & Routers ---

async def main_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی اصلی دستورات از منوی اصلی ادمین."""
    query = update.callback_query
    await query.answer()
    command = query.data.split(":")[1]

    async with AsyncSessionLocal() as session:
        if command == "exit_to_main_menu":
            user = await find_user_by_id(session, query.from_user.id)
            await query.edit_message_text("🤖 خوش آمدید!", reply_markup=get_main_menu_keyboard(user.user_id, user.language))
            return ConversationHandler.END

        elif command == "stats":
            stats = await get_bot_stats(session)
            service_stats = "\n".join([f"▪️ **{s.capitalize()}:** `{c}`" for s, c in stats['service_counts'].items()]) or "آماری ثبت نشده."
            text = (f"**📊 آمار کلی ربات**\n\n👥 **کل کاربران:** `{stats['total_users']}`\n"
                    f"✨ **کاربران جدید امروز:** `{stats['new_users_today']}`\n"
                    f"📥 **مجموع دانلودها:** `{stats['total_downloads']}`\n\n"
                    f"**تفکیک دانلودها:**\n{service_stats}")
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]), parse_mode='Markdown')

        elif command == "manage_services":
            await query.edit_message_text("🔧 **مدیریت سرویس‌ها**", reply_markup=await build_service_management_menu())

        elif command == "users_main":
            keyboard = [[InlineKeyboardButton("📜 لیست کاربران", callback_data="admin:users_list:1"), InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin:users_search_prompt")],
                        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]
            await query.edit_message_text("👥 **مدیریت کاربران**", reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif command == "promo_main":
            return await promo_main_menu(update, context)

        elif command == "broadcast_start":
            await query.edit_message_text("لطفاً پیام خود را برای ارسال وارد کنید. برای لغو /cancel را بفرستید.")
            return AWAITING_BROADCAST_MESSAGE
            
    return ADMIN_MAIN

async def user_management_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی دستورات مربوط به مدیریت کاربران."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    command, value = parts[1], parts[2]
    
    async with AsyncSessionLocal() as session:
        if command == "list":
            page = int(value)
            users, total = await get_users_paginated(session, page=page)
            text = f"👥 **لیست کاربران ({total} کل):**\n\n" + "".join([f"{'🚫' if u.is_banned else '✅'} `{u.user_id}` - @{u.username or 'N/A'}\n" for u in users])
            total_pages = (total + 9) // 10
            nav = []
            if page > 1: nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:users_list:{page-1}"))
            if page < total_pages: nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:users_list:{page+1}"))
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([nav, [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]))
        
        else: # Actions on a specific user
            user_id = int(value)
            if command == 'extend_silver': await set_user_plan(session, user_id, 'silver', 30)
            elif command == 'promote_gold': await set_user_plan(session, user_id, 'gold', 365)
            elif command == 'ban': await ban_user(session, user_id)
            elif command == 'unban': await unban_user(session, user_id)
            elif command == 'delete_confirm':
                kb = [[InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f"admin:users_delete_execute:{user_id}")], [InlineKeyboardButton("⬅️ خیر", callback_data=f"admin:users_panel:{user_id}")]]
                await query.edit_message_text(f"آیا از حذف کامل کاربر `{user_id}` مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
                return ADMIN_MAIN
            elif command == 'delete_execute':
                await delete_user_by_id(session, user_id)
                await query.edit_message_text(f"✅ کاربر `{user_id}` حذف شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]))
                return ADMIN_MAIN

            user = await find_user_by_id(session, user_id)
            text, reply_markup = await build_user_management_panel(user)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    return ADMIN_MAIN

async def service_management_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """مسیردهی دستورات مربوط به مدیریت سرویس‌ها."""
    query = update.callback_query
    await query.answer()
    service_name = query.data.split(":")[2]
    await toggle_service_status(service_name)
    await query.edit_message_reply_markup(reply_markup=await build_service_management_menu())
    return ADMIN_MAIN
    
async def search_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """درخواست آیدی کاربر برای جستجو."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً ID عددی کاربر را برای مدیریت ارسال کنید. برای لغو /cancel را بفرستید.")
    return AWAITING_USER_ID

async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت آیدی کاربر و نمایش پنل مدیریت."""
    try:
        user_id = int(update.message.text)
        async with AsyncSessionLocal() as session:
            user = await find_user_by_id(session, user_id)
            await update.message.delete()
            text, reply_markup = await build_user_management_panel(user)
            # A new message is sent because we deleted the user's message
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
    except (ValueError, KeyError):
        await update.message.reply_text("ورودی نامعتبر است.")
    return ADMIN_MAIN

async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت پیام برای ارسال همگانی."""
    context.user_data['broadcast_message'] = update.message
    async with AsyncSessionLocal() as session:
        user_count = len(await get_all_user_ids(session))
    keyboard = [[InlineKeyboardButton("✅ ارسال", callback_data="admin:broadcast_confirm")], [InlineKeyboardButton("❌ لغو", callback_data="admin:main")]]
    await update.message.reply_text(f"این پیام برای **{user_count}** کاربر ارسال خواهد شد. تایید می‌کنید؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_MAIN

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """اجرای ارسال پیام همگانی."""
    query = update.callback_query
    await query.edit_message_text("⏳ در حال ارسال پیام‌ها...")
    message = context.user_data.pop('broadcast_message', None)
    if not message:
        await query.edit_message_text("خطا: پیامی یافت نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
        return ADMIN_MAIN

    async with AsyncSessionLocal() as session:
        user_ids = await get_all_user_ids(session)
    
    successful, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=message.chat_id, message_id=message.message_id)
            successful += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)
    
    await query.edit_message_text(f"✅ **ارسال تمام شد**\n\n▪️ موفق: {successful}\n▪️ ناموفق: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]))
    return ADMIN_MAIN

async def promo_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نمایش منوی اصلی مدیریت کدهای تخفیف."""
    query = update.callback_query
    async with AsyncSessionLocal() as session:
        codes = await get_all_promo_codes(session)
    text = "🎁 **مدیریت کدهای تخفیف**\n\n"
    keyboard = [[InlineKeyboardButton(f"`{c.code}` | {c.tier} | {c.uses_count}/{c.max_uses}", callback_data="admin:promo_noop"), 
                 InlineKeyboardButton("🗑", callback_data=f"admin:promo_delete:{c.id}")] for c in codes] if codes else []
    
    keyboard.append([InlineKeyboardButton("➕ ساخت کد جدید", callback_data="admin:promo_create_start")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PROMO_MAIN

async def promo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حذف یک کد تخفیف."""
    query = update.callback_query
    code_id = int(query.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await delete_promo_code(session, code_id)
    await query.answer("کد با موفقیت حذف شد.")
    return await promo_main_menu(update, context)

async def promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند ساخت کد تخفیف."""
    query = update.callback_query
    random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data['promo'] = {}
    await query.edit_message_text(f"نام کد را وارد کنید (یا از کد پیشنهادی استفاده کنید):\n`{random_code}`", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لغو", callback_data="admin:promo_main")]]), 
                                  parse_mode='Markdown')
    return PROMO_AWAITING_CODE

async def promo_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['promo']['code'] = update.message.text.upper()
    await update.message.reply_text("نوع اشتراک را وارد کنید (silver, gold, diamond):")
    return PROMO_AWAITING_TIER

async def promo_receive_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tier = update.message.text.lower()
    if tier not in ['silver', 'gold', 'diamond']:
        await update.message.reply_text("نوع اشتراک نامعتبر است. لطفاً یکی از موارد silver, gold, diamond را وارد کنید.")
        return PROMO_AWAITING_TIER
    context.user_data['promo']['tier'] = tier
    await update.message.reply_text("مدت زمان اشتراک به روز را وارد کنید (مثلا: 30):")
    return PROMO_AWAITING_DURATION

async def promo_receive_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['promo']['duration'] = int(update.message.text)
        await update.message.reply_text("تعداد دفعات قابل استفاده را وارد کنید (مثلا: 1):")
        return PROMO_AWAITING_USES
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return PROMO_AWAITING_DURATION

async def promo_receive_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['promo']['uses'] = int(update.message.text)
        promo = context.user_data.pop('promo')
        
        async with AsyncSessionLocal() as session:
            new_code = await create_promo_code(session, code=promo['code'], tier=promo['tier'], duration_days=promo['duration'], max_uses=promo['uses'])
        
        if new_code:
            await update.message.reply_text(f"✅ کد `{new_code.code}` با موفقیت ساخته شد.")
        else:
            await update.message.reply_text(f"❌ کد `{promo['code']}` قبلاً وجود داشته است.")
        
        # Go back to main admin menu by sending a new message with the main menu keyboard
        await update.message.reply_text("بازگشت به پنل مدیریت...", reply_markup=await build_admin_main_menu())
        return ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return PROMO_AWAITING_USES

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("عملیات لغو شد. بازگشت به پنل مدیریت...", reply_markup=await build_admin_main_menu())
    context.user_data.clear()
    return ADMIN_MAIN

# --- ConversationHandler ---
admin_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_entry, pattern='^admin:main$')],
    states={
        ADMIN_MAIN: [
            CallbackQueryHandler(main_router, pattern='^admin:(exit_to_main_menu|stats|manage_services|users_main|broadcast_start|promo_main)$'),
            CallbackQueryHandler(user_management_router, pattern='^admin:users_.*'),
            CallbackQueryHandler(service_management_router, pattern='^admin:toggle_service:.*'),
            CallbackQueryHandler(execute_broadcast, pattern='^admin:broadcast_confirm$'),
            CallbackQueryHandler(search_user_prompt, pattern='^admin:users_search_prompt$'),
        ],
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        AWAITING_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_broadcast_message)],
        PROMO_MAIN: [
            CallbackQueryHandler(promo_main_menu, pattern='^admin:promo_main$'),
            CallbackQueryHandler(promo_delete, pattern='^admin:promo_delete:.*'),
            CallbackQueryHandler(promo_create_start, pattern='^admin:promo_create_start$'),
            CallbackQueryHandler(main_router, pattern='^admin:main$')
        ],
        PROMO_AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_code)],
        PROMO_AWAITING_TIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_tier)],
        PROMO_AWAITING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_duration)],
        PROMO_AWAITING_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_uses)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)