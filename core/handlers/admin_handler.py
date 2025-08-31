import asyncio
import logging
import random
import string
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
    get_users_paginated, find_user_by_id, set_user_plan, delete_user_by_id,
    get_all_user_ids, ban_user, unban_user, get_bot_stats,
    create_promo_code, get_all_promo_codes
)
from .service_manager import get_all_statuses, toggle_service_status
from .menu_handler import get_main_menu_keyboard
import config

logger = logging.getLogger(__name__)

# Stages
(
    ADMIN_MAIN, AWAITING_USER_ID, AWAITING_BROADCAST_MESSAGE,
    PROMO_MAIN, PROMO_AWAITING_CODE, PROMO_AWAITING_TIER,
    PROMO_AWAITING_DURATION, PROMO_AWAITING_USES
) = range(8)


# --- Menu Builders ---

async def build_admin_main_menu():
    """منوی اصلی پنل ادمین با طرح دو ستونی"""
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار ربات", callback_data="admin:stats"),
            InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin:users_main")
        ],
        [
            InlineKeyboardButton("🔧 مدیریت سرویس‌ها", callback_data="admin:manage_services"),
            InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin:broadcast_start")
        ],
        [InlineKeyboardButton("🎁 کدهای تخفیف", callback_data="admin:promo_main")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی ربات", callback_data="admin:exit_to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def build_user_management_panel(user):
    """منوی مدیریت کاربر با طرح دو ستونی"""
    if not user: return None, None
    ban_status_text = "✅ آزاد کردن" if user.is_banned else "🚫 مسدود کردن"
    ban_callback = f"admin:user_unban:{user.user_id}" if user.is_banned else f"admin:user_ban:{user.user_id}"
    text = (
        f"**👤 مدیریت کاربر:** `{user.user_id}` | **وضعیت:** `{'مسدود' if user.is_banned else 'فعال'}`\n"
        f"**نام کاربری:** @{user.username or 'N/A'}\n"
        f"**اشتراک:** `{user.subscription_tier}`\n"
        f"**انقضا:** `{user.subscription_expiry_date or 'N/A'}`"
    )
    keyboard = [
        [
            InlineKeyboardButton("🥈 ۳۰ روز نقره‌ای", callback_data=f"admin:user_extend_30_silver:{user.user_id}"),
            InlineKeyboardButton("🥇 ۱ سال طلایی", callback_data=f"admin:user_promote_gold:{user.user_id}"),
        ],
        [
            InlineKeyboardButton(ban_status_text, callback_data=ban_callback),
            InlineKeyboardButton("🗑 حذف کامل کاربر", callback_data=f"admin:user_delete_confirm:{user.user_id}")
        ],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)

async def build_service_management_menu():
    """منوی دو ستونی برای مدیریت سرویس‌ها"""
    statuses = get_all_statuses()
    keyboard = []
    sorted_statuses = sorted(statuses, key=lambda s: s.service_name)
    it = iter(sorted_statuses)
    for s1 in it:
        try:
            s2 = next(it)
            keyboard.append([
                InlineKeyboardButton(f"{'✅' if s1.is_enabled else '❌'} {s1.service_name.capitalize()}", callback_data=f"admin:toggle_service:{s1.service_name}"),
                InlineKeyboardButton(f"{'✅' if s2.is_enabled else '❌'} {s2.service_name.capitalize()}", callback_data=f"admin:toggle_service:{s2.service_name}")
            ])
        except StopIteration:
            keyboard.append([InlineKeyboardButton(f"{'✅' if s1.is_enabled else '❌'} {s1.service_name.capitalize()}", callback_data=f"admin:toggle_service:{s1.service_name}")])
            
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    return InlineKeyboardMarkup(keyboard)

# --- Entry & Main Router ---

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # اطمینان از اینکه کاربر ادمین است
    if query.from_user.id != config.ADMIN_ID:
        await query.answer("شما دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END
        
    admin_text = "👑 **پنل مدیریت**\n\nلطفا یک گزینه را انتخاب کنید:"
    await query.edit_message_text(text=admin_text, reply_markup=await build_admin_main_menu(), parse_mode="Markdown")
    return ADMIN_MAIN

async def admin_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    command = parts[1]

    if command == "main": 
        return await admin_entry(update, context)
    
    if command == "exit_to_main_menu":
        user = find_user_by_id(query.from_user.id)
        await query.edit_message_text(
            text="🤖 خوش آمدید!\n\nبرای شروع، یک لینک از سرویس‌های پشتیبانی شده ارسال کنید.", 
            reply_markup=get_main_menu_keyboard(user.user_id, user.language)
        )
        return ConversationHandler.END

    if command == "stats":
        stats = get_bot_stats()
        service_stats = "\n".join([f"▪️ **{s.capitalize()}:** `{c}`" for s, c in stats['service_counts'].items()]) if stats['service_counts'] else "آماری ثبت نشده."
        text = (f"**📊 آمار کلی ربات**\n\n"
                f"👥 **کل کاربران:** `{stats['total_users']}`\n"
                f"✨ **کاربران جدید امروز:** `{stats['new_users_today']}`\n"
                f"📥 **مجموع دانلودها:** `{stats['total_downloads']}`\n\n"
                f"**تفکیک دانلودها:**\n{service_stats}")
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]), parse_mode='Markdown')
        return ADMIN_MAIN

    if command == "manage_services":
        await query.edit_message_text("🔧 **مدیریت سرویس‌ها**", reply_markup=await build_service_management_menu(), parse_mode='Markdown')
        return ADMIN_MAIN
        
    if command == "toggle_service":
        toggle_service_status(parts[2])
        await query.edit_message_reply_markup(reply_markup=await build_service_management_menu())
        return ADMIN_MAIN

    if command == "users_main":
        keyboard = [
            [
                InlineKeyboardButton("📜 لیست همه کاربران", callback_data="admin:list_users:1"),
                InlineKeyboardButton("🔍 جستجوی کاربر با ID", callback_data="admin:search_user_prompt")
            ],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]
        ]
        await query.edit_message_text("👥 **مدیریت کاربران**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MAIN
    
    if command == "list_users":
        page = int(parts[2])
        users, total = get_users_paginated(page=page, per_page=10)
        text = f"👥 **لیست کاربران ({total} کل):**\n\n" + "".join([f"{'🚫' if u.is_banned else '✅'} `{u.user_id}` - @{u.username or 'N/A'}\n" for u in users])
        total_pages = (total + 9) // 10
        text += f"\nصفحه {page} از {total_pages}"
        nav = []
        if page > 1: nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:list_users:{page-1}"))
        if page < total_pages: nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"admin:list_users:{page+1}"))
        keyboard = [nav, [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MAIN
    if command == 'search_user_prompt':
        await query.edit_message_text("لطفاً ID عددی کاربر را برای مدیریت ارسال کنید.\nبرای لغو /cancel_admin را بفرستید.")
        return AWAITING_USER_ID
    if command in ('user_extend_30_silver', 'user_promote_gold', 'user_ban', 'user_unban', 'user_delete_confirm', 'user_delete_execute', 'user_manage_panel'):
        user_id = int(parts[2])
        if command == 'user_extend_30_silver': set_user_plan(user_id, 'silver', 30)
        if command == 'user_promote_gold': set_user_plan(user_id, 'gold', 365)
        if command == 'user_ban': ban_user(user_id)
        if command == 'user_unban': unban_user(user_id)
        if command == 'user_delete_confirm':
            kb = [[InlineKeyboardButton("🗑 بله، حذف کن", callback_data=f"admin:user_delete_execute:{user_id}")], [InlineKeyboardButton("⬅️ خیر", callback_data=f"admin:user_manage_panel:{user_id}")]]
            await query.edit_message_text(f"آیا از حذف کامل کاربر `{user_id}` مطمئن هستید؟ این عمل غیرقابل بازگشت است.", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
            return ADMIN_MAIN
        if command == 'user_delete_execute':
            delete_user_by_id(user_id)
            await query.edit_message_text(f"✅ کاربر `{user_id}` حذف شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]), parse_mode='Markdown')
            return ADMIN_MAIN
        
        user = find_user_by_id(user_id)
        text, reply_markup = await build_user_management_panel(user)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return ADMIN_MAIN

    # --- Broadcast ---
    if command == 'broadcast_start':
        keyboard = [[InlineKeyboardButton("❌ لغو", callback_data="admin:main")]]
        await query.edit_message_text(
            "لطفاً پیام خود را برای ارسال وارد کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_BROADCAST_MESSAGE

    # --- Promo Codes ---
    if command == 'promo_main': return await promo_main_menu(update, context)

    return ADMIN_MAIN

async def receive_user_id_for_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = int(update.message.text)
        user = find_user_by_id(user_id)
        await update.message.delete()
        text, reply_markup = await build_user_management_panel(user) if user else (f"کاربری با ID `{user_id}` یافت نشد.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]]))
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
    except (ValueError, KeyError):
        await update.message.reply_text("ورودی نامعتبر است.")
    return ADMIN_MAIN

# --- Broadcast Logic ---
async def broadcast_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['broadcast_message'] = update.message
    user_count = len(get_all_user_ids())
    keyboard = [[InlineKeyboardButton("✅ ارسال", callback_data="admin:broadcast_confirm_send")], [InlineKeyboardButton("❌ لغو", callback_data="admin:main")]]
    await update.message.reply_text(f"این پیام برای **{user_count}** کاربر ارسال خواهد شد. تایید می‌کنید؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_MAIN

async def broadcast_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text("⏳ در حال ارسال پیام‌ها...")
    message_to_send = context.user_data.pop('broadcast_message', None)
    if not message_to_send:
        await query.edit_message_text("خطا: پیامی یافت نشد.")
        return await admin_entry(update, context)

    user_ids = get_all_user_ids()
    successful, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=message_to_send.chat_id, message_id=message_to_send.message_id)
            successful += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)
    report = f"✅ **گزارش ارسال**\n\n▪️ موفق: {successful}\n▪️ ناموفق: {failed}"
    await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]]), parse_mode='Markdown')
    return ADMIN_MAIN

# --- Promo Code Logic ---

async def promo_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    codes = get_all_promo_codes()
    text = "🎁 **مدیریت کدهای تخفیف**\n\n"
    keyboard = [] # کیبورد به لیست خالی تغییر کرد

    if codes:
        #      ↓↓↓ منطق نمایش دکمه حذف در این قسمت اضافه شد ↓↓↓
        for c in codes:
            row_text = f"`{c.code}` | {c.tier} | {c.uses_count}/{c.max_uses}"
            # یک ردیف دکمه برای هر کد ایجاد می‌شود
            keyboard.append([
                InlineKeyboardButton(row_text, callback_data="admin:promo_noop"), # دکمه متنی که کاری انجام نمی‌دهد
                InlineKeyboardButton("🗑", callback_data=f"admin:promo_delete_confirm:{c.id}")
            ])
    else:
        text += "هیچ کد تخفیفی ساخته نشده است."
    
    # دکمه‌های ساخت و بازگشت به کیبورد اضافه می‌شوند
    keyboard.append([InlineKeyboardButton("➕ ساخت کد جدید", callback_data="promo:create_start")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PROMO_MAIN

async def promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data['promo'] = {}
    
    keyboard = [
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:promo_main")]
    ]
    
    text_to_send = f"یک نام برای کد وارد کنید (حروف انگلیسی و اعداد)، یا از کد پیشنهادی زیر استفاده کنید:\n`{random_code}`"
    
    await query.edit_message_text(
        text=text_to_send,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
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
        promo = context.user_data['promo']
        
        new_code = create_promo_code(
            code=promo['code'],
            tier=promo['tier'],
            duration_days=promo['duration'], # Changed from duration
            max_uses=promo['uses']
        )
        
        if new_code:
            await update.message.reply_text(f"✅ کد `{new_code.code}` با موفقیت ساخته شد.")
        else:
            await update.message.reply_text(f"❌ کد `{promo['code']}` قبلاً وجود داشته است.")
            
        context.user_data.pop('promo', None)
        
        # Send a new message with the updated promo code list
        codes = get_all_promo_codes()
        text = "🎁 **مدیریت کدهای تخفیف**\n\n"
        if codes:
            text += "\n".join([f"`{c.code}` | {c.tier} | {c.uses_count}/{c.max_uses} استفاده شده" for c in codes])
        else:
            text += "هیچ کد تخفیفی ساخته نشده است."
        
        keyboard = [
            [InlineKeyboardButton("➕ ساخت کد جدید", callback_data="promo:create_start")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return PROMO_MAIN

    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return PROMO_AWAITING_USES

# --- Fallback ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("عملیات لغو شد.")
    # Create a fake update to re-enter the main admin menu
    query = CallbackQuery(id=str(update.update_id), from_user=update.effective_user, chat_instance="admin_conv", data="admin:main")
    fake_update = Update(update_id=update.update_id, callback_query=query)
    # We need to send a new message because we can't edit the one that triggered the cancellation
    await context.bot.send_message(chat_id=update.effective_chat.id, text="بازگشت به پنل مدیریت...", reply_markup=await build_admin_main_menu())
    return ADMIN_MAIN

# --- ConversationHandler ---
admin_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_entry, pattern='^admin:main$')],
    states={
        ADMIN_MAIN: [CallbackQueryHandler(admin_router, pattern='^admin:.*')],
        AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id_for_management)],
        AWAITING_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_receive_message)],
        PROMO_MAIN: [
            CallbackQueryHandler(promo_create_start, pattern='^promo:create_start$'),
            CallbackQueryHandler(admin_router, pattern='^admin:main$')
        ],
        PROMO_AWAITING_CODE: [
            # این خط جدید، مشکل دکمه بازگشت را حل می‌کند
            CallbackQueryHandler(promo_main_menu, pattern='^admin:promo_main$'), 
            MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_code)
        ],
        PROMO_AWAITING_TIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_tier)],
        PROMO_AWAITING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_duration)],
        PROMO_AWAITING_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_uses)],
    },
    # فال‌بک حذف شد چون دیگر به آن نیازی نیست
    fallbacks=[],
    allow_reentry=True
)