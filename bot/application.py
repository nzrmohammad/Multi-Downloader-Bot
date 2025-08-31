# bot/application.py
import logging
from telegram.ext import Application, ApplicationBuilder
from telegram.request import HTTPXRequest
from core.settings import settings

def create_application() -> Application:
    """اپلیکیشن ربات را با تنظیمات اولیه می‌سازد."""
    
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=60.0)
    
    application = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .request(request)
        .build()
    )
    return application