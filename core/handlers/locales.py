# core/handlers/locales.py

translations = {
    'en': {
        'welcome': "🤖 Welcome!\n\nSend a link from a supported service to start downloading.",
        'language_selection': "Please select your language:",
        'language_selected': "Language set to English.",
        'back_button': "⬅️ Back",
        
        # --- Main Menu ---
        'menu_help': "📥 Download Guide",
        'menu_services': "📊 Service Status",
        'menu_account': "⭐️ Account & Subscription",
        'menu_settings': "⚙️ Settings",
        'menu_about': "ℹ️ About & Support",

        # --- Service Status ---
        'services_title': "📊 **Service Status**\n\n",
        'no_services': "No services available to display status.",
        'service_legend': "🔒: Requires a premium subscription.",
        
        # --- Settings Menu ---
        'settings_main_text': "⚙️ **Settings**\n\nHere you can customize the bot's settings.",
        'settings_language': "🌐 Change Language",
        'settings_language_select': "Please select your desired language:",

    },
    'fa': {
        'welcome': "🤖 خوش آمدید!\n\nبرای شروع، یک لینک از سرویس‌های پشتیبانی شده ارسال کنید.",
        'language_selection': "لطفا زبان خود را انتخاب کنید:",
        'language_selected': "زبان به فارسی تغییر کرد.",
        'back_button': "⬅️ بازگشت",

        # --- منوی اصلی ---
        'menu_help': "📥 راهنمای دانلود",
        'menu_services': "📊 وضعیت سرویس‌ها",
        'menu_account': "⭐️ حساب کاربری و اشتراک",
        'menu_settings': "⚙️ تنظیمات",
        'menu_about': "ℹ️ درباره و پشتیبانی",
        
        # --- وضعیت سرویس‌ها ---
        'services_title': "📊 **وضعیت فعال بودن سرویس‌ها**\n\n",
        'no_services': "هیچ سرویسی برای نمایش وضعیت وجود ندارد.",
        'service_legend': "🔒: نیازمند اشتراک ویژه است.",

        # --- منوی تنظیمات ---
        'settings_main_text': "⚙️ **تنظیمات**\n\nدر این بخش می‌توانید تنظیمات ربات را شخصی‌سازی کنید.",
        'settings_language': "🌐 تغییر زبان",
        'settings_language_select': "لطفا زبان مورد نظر خود را انتخاب کنید:",
    }
}

def get_text(key, lang='en'):
    """Retrieves a translated string, falling back to English if the key is not found."""
    # Fallback to English if a key is not found in the selected language
    return translations.get(lang, translations['en']).get(key, translations['en'].get(key, key))