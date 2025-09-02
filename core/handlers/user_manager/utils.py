# core/user_manager/utils.py
from database.models import User

def can_download(user: User) -> bool:
    """بررسی می‌کند که آیا کاربر مجاز به دانلود است یا خیر."""
    tier_limits = {'free': 5, 'bronze': 30, 'silver': 100, 'gold': float('inf'), 'diamond': float('inf')}
    limit = tier_limits.get(user.subscription_tier, 0)
    return user.daily_downloads < limit

def get_batch_limit(user: User) -> int:
    """محدودیت دانلود دسته‌ای کاربر را برمی‌گرداند."""
    if user.is_banned: return 0
    limits = {'free': 1, 'bronze': 1, 'silver': 1, 'gold': 10, 'diamond': 50}
    return limits.get(user.subscription_tier, 1)

def get_file_size_limit(user: User) -> int:
    """محدودیت حجم فایل کاربر را بر اساس پلن اشتراک او برمی‌گرداند."""
    if user.subscription_tier in ['gold', 'diamond']:
        return 4 * 1024 * 1024 * 1024  # 4 GB
    return 2 * 1024 * 1024 * 1024  # 2 GB