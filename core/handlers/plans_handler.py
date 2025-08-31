# core/handlers/plans_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .menu_handler import get_main_menu_keyboard
from core.user_manager import get_or_create_user

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the subscription plans and features to the user."""
    user = get_or_create_user(update)
    
    # Define the features for each plan
    plans = {
        "🆓 رایگان (Free)": {
            "Downloads": "۵ عدد در روز",
            "YouTube Playlist": "❌",
            "Spotify Playlist": "❌",
            "Batch Download": "❌",
            "Ad-Free": "❌",
            "Support": "عادی"
        },
        "🥉 برنزی (Bronze)": {
            "Downloads": "۳۰ عدد در روز",
            "YouTube Playlist": "✅",
            "Spotify Playlist": "❌",
            "Batch Download": "❌",
            "Ad-Free": "✅",
            "Support": "اولویت‌دار"
        },
        "🥈 نقره‌ای (Silver)": {
            "Downloads": "۱۰۰ عدد در روز",
            "YouTube Playlist": "✅",
            "Spotify Playlist": "✅",
            "Batch Download": "❌",
            "Ad-Free": "✅",
            "Support": "اولویت‌دار"
        },
        "🥇 طلایی (Gold)": {
            "Downloads": "نامحدود",
            "YouTube Playlist": "✅",
            "Spotify Playlist": "✅",
            "Batch Download": "✅ (تا ۱۰ لینک)",
            "Ad-Free": "✅",
            "Support": "ویژه"
        },
        "💎 الماسی (Diamond)": {
            "Downloads": "نامحدود",
            "YouTube Playlist": "✅",
            "Spotify Playlist": "✅",
            "Batch Download": "✅ (تا ۵۰ لینک)",
            "Ad-Free": "✅",
            "Support": "ویژه ۲۴/۷"
        }
    }

    header = "⭐️ **پلن‌های اشتراک و قابلیت‌ها** ⭐️\n\n"
    plan_details = ""
    for plan_name, features in plans.items():
        plan_details += f"\n**{plan_name}**\n"
        for feature, value in features.items():
            plan_details += f"▪️ {feature}: **{value}**\n"
        plan_details += "—------------------\n"

    footer = "\nبرای خرید یا ارتقاء اشتراک، لطفاً با پشتیبانی در تماس باشید: @YourAdminUsername"
    
    full_text = header + plan_details + footer
    
    keyboard = [[InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="menu:main")]]
    
    # If the command came from a button press, edit the message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=full_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    # If it came from a /plans command, send a new message
    else:
        await update.message.reply_text(
            text=full_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )