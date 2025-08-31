# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/ui.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core import user_manager

async def build_admin_main_menu():
    """منوی اصلی پنل ادمین را ایجاد می‌کند."""
    keyboard = [
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin:stats"), InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin:users_main")],
        [InlineKeyboardButton("🔧 مدیریت سرویس‌ها", callback_data="admin:manage_services"), InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin:broadcast_start")],
        [InlineKeyboardButton("🎁 کدهای تخفیf", callback_data="admin:promo_main")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی ربات", callback_data="admin:exit_to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def build_user_management_panel(session, user):
    """منوی مدیریت یک کاربر خاص را با جزئیات کامل ایجاد می‌کند."""
    if not user:
        return "**خطا:** کاربر یافت نشد.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")]])
    
    last_activity = await user_manager.get_user_last_activity(session, user.user_id)
    last_activity_str = last_activity.strftime("%Y-%m-%d %H:%M") if last_activity else "N/A"
        
    ban_text = "✅ آزاد کردن" if user.is_banned else "🚫 مسدود کردن"
    ban_callback = f"admin:user_unban:{user.user_id}" if user.is_banned else f"admin:user_ban:{user.user_id}"
    text = (
        f"**👤 مدیریت کاربر:** `{user.user_id}`\n"
        f"**نام کاربری:** @{user.username or 'N/A'}\n\n"
        f"**وضعیت:** `{'مسدود' if user.is_banned else 'فعال'}`\n"
        f"**اشتراک:** `{user.subscription_tier}`\n"
        f"**انقضا اشتراک:** `{user.subscription_expiry_date or 'N/A'}`\n"
        f"**مجموع دانلودها:** `{user.total_downloads}`\n"
        f"**آخرین فعالیت:** `{last_activity_str}`"
    )
    keyboard = [
        [InlineKeyboardButton("🥈 ۳۰ روز نقره‌ای", callback_data=f"admin:user_extend_silver:{user.user_id}"), InlineKeyboardButton("🥇 ۱ سال طلایی", callback_data=f"admin:user_promote_gold:{user.user_id}")],
        [InlineKeyboardButton("✉️ ارسال پیام به کاربر", callback_data=f"admin:user_message_prompt:{user.user_id}")],
        [InlineKeyboardButton(ban_text, callback_data=ban_callback), InlineKeyboardButton("🗑 حذف کامل", callback_data=f"admin:user_delete_confirm:{user.user_id}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin:users_main")],
    ]
    return text, InlineKeyboardMarkup(keyboard)