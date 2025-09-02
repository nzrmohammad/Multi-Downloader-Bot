# core/handlers/callbacks/castbox_callback.py
from telegram import Update
from telegram.ext import ContextTypes
from services.castbox import CastboxService

async def handle_castbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    await query.answer()
    
    command, *params = query.data.split(':')[1:]
    
    castbox_service = CastboxService()
    
    if command == 'page':
        page = int(params[0])
        chat_id = int(params[1])
        episodes = context.bot_data.get(f"castbox_eps_{chat_id}", [])
        if episodes:
            keyboard = castbox_service.build_episode_keyboard(episodes, chat_id=chat_id, page=page)
            await query.edit_message_reply_markup(reply_markup=keyboard)
            
    elif command == 'dl':
        episode_id = params[0]
        episode_url = f"https://castbox.fm/ep/{episode_id}"
        
        original_message = await query.edit_message_text(f"در حال آماده‌سازی برای دانلود قسمت انتخابی...")
        
        class MockUpdate:
            def __init__(self, message, effective_user):
                self.message = message
                self.effective_user = effective_user

        mock_update = MockUpdate(original_message, query.from_user)
        await castbox_service.process(mock_update, context, user, episode_url)