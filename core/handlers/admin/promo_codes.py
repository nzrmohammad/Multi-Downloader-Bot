# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/promo_codes.py

import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.database import AsyncSessionLocal
from core.handlers import user_manager
from . import states
from .ui import build_admin_main_menu

async def promo_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نمایش منوی اصلی مدیریت کدهای تخفیف."""
    query = update.callback_query
    async with AsyncSessionLocal() as session:
        codes = await user_manager.get_all_promo_codes(session)
    text = "🎁 **مدیریت کدهای تخفیف**\n\n"
    keyboard = [[InlineKeyboardButton(f"`{c.code}` | {c.tier} | {c.uses_count}/{c.max_uses}", callback_data="admin:promo_noop"), 
                 InlineKeyboardButton("🗑", callback_data=f"admin:promo_delete:{c.id}")] for c in codes] if codes else []
    
    keyboard.append([InlineKeyboardButton("➕ ساخت کد جدید", callback_data="admin:promo_create_start")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return states.PROMO_MAIN

async def promo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حذف یک کد تخفیف."""
    query = update.callback_query
    code_id = int(query.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await user_manager.delete_promo_code(session, code_id)
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
    return states.PROMO_AWAITING_CODE

async def promo_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['promo']['code'] = update.message.text.upper()
    await update.message.reply_text("نوع اشتراک را وارد کنید (silver, gold, diamond):")
    return states.PROMO_AWAITING_TIER

async def promo_receive_tier(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tier = update.message.text.lower()
    if tier not in ['silver', 'gold', 'diamond']:
        await update.message.reply_text("نوع اشتراک نامعتبر است. لطفاً یکی از موارد silver, gold, diamond را وارد کنید.")
        return states.PROMO_AWAITING_TIER
    context.user_data['promo']['tier'] = tier
    await update.message.reply_text("مدت زمان اشتراک به روز را وارد کنید (مثلا: 30):")
    return states.PROMO_AWAITING_DURATION

async def promo_receive_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['promo']['duration'] = int(update.message.text)
        await update.message.reply_text("تعداد دفعات قابل استفاده را وارد کنید (مثلا: 1):")
        return states.PROMO_AWAITING_USES
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return states.PROMO_AWAITING_DURATION

async def promo_receive_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['promo']['uses'] = int(update.message.text)
        promo = context.user_data.pop('promo')
        
        async with AsyncSessionLocal() as session:
            new_code = await user_manager.create_promo_code(session, code=promo['code'], tier=promo['tier'], duration_days=promo['duration'], max_uses=promo['uses'])
        
        if new_code:
            await update.message.reply_text(f"✅ کد `{new_code.code}` با موفقیت ساخته شد.")
        else:
            await update.message.reply_text(f"❌ کد `{promo['code']}` قبلاً وجود داشته است.")
        
        await update.message.reply_text("بازگشت به پنل مدیریت...", reply_markup=await build_admin_main_menu())
        return states.ADMIN_MAIN
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return states.PROMO_AWAITING_USES