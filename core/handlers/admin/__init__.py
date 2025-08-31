# nzrmohammad/multi-downloader-bot/Multi-Downloader-Bot-51607f5e4788060c5ecbbd007b59d05e883abb58/core/handlers/admin/__init__.py

from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
)

# Define states for ConversationHandler
(
    ADMIN_MAIN, AWAITING_USER_ID, AWAITING_BROADCAST_MESSAGE,
    PROMO_MAIN, PROMO_AWAITING_CODE, PROMO_AWAITING_TIER,
    PROMO_AWAITING_DURATION, PROMO_AWAITING_USES,
    AWAITING_MESSAGE_TO_USER
) = range(9)

# A simple object to hold states for better readability
class states:
    ADMIN_MAIN = ADMIN_MAIN
    AWAITING_USER_ID = AWAITING_USER_ID
    AWAITING_BROADCAST_MESSAGE = AWAITING_BROADCAST_MESSAGE
    PROMO_MAIN = PROMO_MAIN
    PROMO_AWAITING_CODE = PROMO_AWAITING_CODE
    PROMO_AWAITING_TIER = PROMO_AWAITING_TIER
    PROMO_AWAITING_DURATION = PROMO_AWAITING_DURATION
    PROMO_AWAITING_USES = PROMO_AWAITING_USES
    AWAITING_MESSAGE_TO_USER = AWAITING_MESSAGE_TO_USER


# Import handlers from separated files
from .callbacks import admin_entry, main_router, cancel
from .user_management import user_router, search_user_prompt, receive_user_id, receive_message_to_user
from .broadcast import receive_broadcast_message, execute_broadcast
from .promo_codes import (
    promo_main_menu, promo_delete, promo_create_start,
    promo_receive_code, promo_receive_tier, promo_receive_duration, promo_receive_uses
)

admin_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_entry, pattern='^admin:main$')],
    states={
        states.ADMIN_MAIN: [
            CallbackQueryHandler(main_router, pattern='^admin:(exit_to_main_menu|stats|users_main|broadcast_start|promo_main)$'),
            CallbackQueryHandler(user_router, pattern='^admin:user_.*'),
            CallbackQueryHandler(execute_broadcast, pattern='^admin:broadcast_confirm$'),
            CallbackQueryHandler(search_user_prompt, pattern='^admin:user_search_prompt$'),
        ],
        states.AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id)],
        states.AWAITING_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_broadcast_message)],
        states.AWAITING_MESSAGE_TO_USER: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_message_to_user)],
        states.PROMO_MAIN: [
            CallbackQueryHandler(promo_main_menu, pattern='^admin:promo_main$'),
            CallbackQueryHandler(promo_delete, pattern='^admin:promo_delete:.*'),
            CallbackQueryHandler(promo_create_start, pattern='^admin:promo_create_start$'),
            CallbackQueryHandler(main_router, pattern='^admin:main$')
        ],
        states.PROMO_AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_code)],
        states.PROMO_AWAITING_TIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_tier)],
        states.PROMO_AWAITING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_duration)],
        states.PROMO_AWAITING_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_receive_uses)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)