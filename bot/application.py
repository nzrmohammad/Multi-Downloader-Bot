import logging
from telegram.ext import Application, ApplicationBuilder
from telegram.request import HTTPXRequest
import config

def create_application() -> Application:
    """اپلیکیشن ربات را با تنظیمات اولیه می‌سازد."""
    
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=60.0)
    
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request)
        .build()
    )
    return application