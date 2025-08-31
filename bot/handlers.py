# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/bot/handlers.py

from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    CallbackQueryHandler, InlineQueryHandler
)

# Import the main ConversationHandler from the new admin package
from core.handlers.admin import admin_conv_handler 
from core.handlers.command_handler import start_command, plans_command, inline_query_handler
from core.handlers.dispatch_handler import dispatch_link
from core.handlers.callback_query_handler import main_callback_router, promo_conv_handler

def register_handlers(application: Application):
    """تمام هندلرها را به اپلیکیشن اضافه می‌کند."""
    
    application.add_handler(promo_conv_handler)
    application.add_handler(admin_conv_handler)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("plans", plans_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_link))
    
    application.add_handler(CallbackQueryHandler(main_callback_router))
    application.add_handler(InlineQueryHandler(inline_query_handler))