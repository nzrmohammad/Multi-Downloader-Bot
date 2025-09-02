# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/dispatch_handler.py

import re
import logging
from urllib.parse import urlparse
import requests
from telegram import Update
from telegram.ext import ContextTypes

from database.database import AsyncSessionLocal
from services import SERVICES
from core.handlers import user_manager
from .service_manager import get_service_status

logger = logging.getLogger(__name__)
URL_REGEX = r"(https?://[^\s]+)"

def resolve_shortened_url(url: str) -> str:
    """لینک‌های کوتاه شده را به لینک اصلی تبدیل می‌کند."""
    parsed_url = urlparse(url)
    if 'on.soundcloud.com' in parsed_url.netloc:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            if response.status_code == 200 and response.url != url:
                return response.url
        except requests.RequestException:
            return url
    return url

async def dispatch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لینک‌ها را شناسایی کرده و به سرویس مناسب ارسال می‌کند."""
    async with AsyncSessionLocal() as session:
        user = await user_manager.get_or_create_user(session, update)
        
        if user.is_banned:
            await update.message.reply_text("شما از استفاده از این ربات محروم شده‌اید.")
            return

        urls = re.findall(URL_REGEX, update.message.text or "")
        if not urls:
            await update.message.reply_text("هیچ لینک معتبری در پیام شما یافت نشد. 🧐")
            return

        batch_limit = user_manager.get_batch_limit(user)
        if len(urls) > batch_limit:
            await update.message.reply_text(f"شما مجاز به ارسال حداکثر {batch_limit} لینک در یک پیام هستید.")
            return
        
        if len(urls) > 1:
            await update.message.reply_text(f"✅ {len(urls)} لینک دریافت شد. دانلودها به زودی ارسال خواهند شد.")

        for url in urls:
            # --- FIX: تمیز کردن لینک از کاراکترهای اضافی و اشتباه در انتها ---
            cleaned_url = url.rstrip('`\'">.,').replace('%60', '')
            
            resolved_url = resolve_shortened_url(cleaned_url)
            found_service = False
            for service in SERVICES:
                service_name = service.__class__.__name__.replace("Service", "").lower()
                service_is_enabled = await get_service_status(service_name)
                if not service_is_enabled: 
                    continue
                
                if await service.can_handle(resolved_url):
                    try:
                        await service.process(update, context, user, resolved_url)
                    except Exception as e:
                        logger.error(f"Error processing {url} with {service_name}: {e}", exc_info=True)
                        await context.bot.send_message(chat_id=user.user_id, text=f"❌ در پردازش لینک زیر خطایی رخ داد:\n`{url}`", parse_mode='Markdown')
                    found_service = True
                    break
            
            if not found_service:
                # --- FIX: افزودن parse_mode و نمایش لینک تمیز شده ---
                await context.bot.send_message(
                    chat_id=user.user_id, 
                    text=f"لینک زیر پشتیبانی نمی‌شود: `{resolved_url}`",
                    parse_mode='Markdown'
                )