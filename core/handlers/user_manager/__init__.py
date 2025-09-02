# core/user_manager/__init__.py

# وارد کردن توابع از ماژول‌های تفکیک شده
from .profile import (
    get_or_create_user,
    find_user_by_id,
    set_user_plan,
    set_user_language,
    set_user_quality_setting,
    get_download_stats
)
from .activity import (
    increment_download_count,
    log_activity,
    get_user_last_activity
)
from .admin_actions import (
    get_all_user_ids,
    get_users_paginated,
    delete_user_by_id,
    ban_user,
    unban_user,
    get_bot_stats
)
from .promo_codes import (
    create_promo_code,
    get_all_promo_codes,
    delete_promo_code,
    redeem_promo_code
)
from .utils import (
    can_download,
    get_batch_limit,
    get_file_size_limit
)
# وارد کردن مدل User برای type hinting در سایر بخش‌های پروژه
from database.models import User