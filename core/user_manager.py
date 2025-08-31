# core/user_manager.py
import datetime
import json
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from database.models import User, Purchase, ActivityLog, PromoCode

# =================================================================
# توابع اصلی مدیریت کاربر (User Management)
# =================================================================

async def get_or_create_user(db: AsyncSession, update: Update) -> User:
    """
    کاربر را از پایگاه داده دریافت کرده یا در صورت عدم وجود، ایجاد می‌کند.
    این تابع همچنین وضعیت کاربر (اشتراک و دانلود روزانه) را به‌روزرسانی می‌کند.
    """
    user_id = update.effective_user.id
    username = update.effective_user.username

    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()

    if not user:
        user = User(user_id=user_id, username=username)
        db.add(user)
        await log_activity(db, user, 'register')
    else:
        user.username = username
        if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date < datetime.datetime.utcnow():
            user.subscription_tier = 'free'

        if user.last_download_date != datetime.date.today():
            user.daily_downloads = 0
            user.last_download_date = datetime.date.today()

    await db.commit()
    await db.refresh(user)
    return user

async def find_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """یک کاربر را با شناسه تلگرام او جستجو می‌کند."""
    result = await db.execute(select(User).filter(User.user_id == user_id))
    return result.scalars().first()

async def get_all_user_ids(db: AsyncSession) -> list[int]:
    """لیست تمام شناسه‌های کاربری را برمی‌گرداند."""
    result = await db.execute(select(User.user_id))
    return list(result.scalars().all())

def get_download_stats(user: User) -> dict:
    """آمار دانلود کاربر را از ستون JSON دریافت می‌کند."""
    if user and user.download_stats:
        return json.loads(user.download_stats)
    return {}

# =================================================================
# توابع مربوط به اشتراک و تنظیمات کاربر (Subscription & Settings)
# =================================================================

async def set_user_plan(db: AsyncSession, user: User, tier: str, duration_days: int) -> bool:
    """پلن اشتراک یک کاربر را تنظیم یا تمدید می‌کند."""
    if not user:
        return False

    if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date > datetime.datetime.utcnow():
        new_expiry_date = user.subscription_expiry_date + datetime.timedelta(days=duration_days)
    else:
        new_expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=duration_days)

    user.subscription_tier = tier
    user.subscription_expiry_date = new_expiry_date

    new_purchase = Purchase(user_id=user.user_id, duration_days=duration_days, tier_purchased=tier)
    db.add(new_purchase)

    await db.commit()
    return True

async def set_user_language(db: AsyncSession, user: User, language: str):
    """زبان مورد علاقه کاربر را تنظیم می‌کند."""
    if user:
        user.language = language
        await db.commit()

async def set_user_quality_setting(db: AsyncSession, user: User, platform: str, quality: str):
    """تنظیمات کیفیت دانلود کاربر را به‌روز می‌کند."""
    if not user: return

    if platform == 'yt':
        user.settings_yt_quality = quality
    elif platform == 'spotify':
        user.settings_spotify_quality = quality

    await db.commit()

# =================================================================
# توابع مدیریت دانلود و فعالیت (Download & Activity)
# =================================================================

async def increment_download_count(db: AsyncSession, user: User):
    """تعداد دانلودهای روزانه و کل کاربر را یک واحد افزایش می‌دهد."""
    if user:
        user.daily_downloads += 1
        user.total_downloads += 1
        await db.commit()

async def log_activity(db: AsyncSession, user: User, activity_type: str, details: str = None):
    """یک فعالیت کاربر را ثبت کرده و آمار دانلود را در ستون JSON به‌روز می‌کند."""
    log = ActivityLog(user_id=user.user_id, activity_type=activity_type, details=details)
    db.add(log)

    if activity_type == 'download' and details:
        if user:
            stats = json.loads(user.download_stats or '{}')
            service = details.split(':')[0]
            stats[service] = stats.get(service, 0) + 1
            user.download_stats = json.dumps(stats)

    await db.commit()

async def get_user_last_activity(db: AsyncSession, user_id: int) -> datetime.datetime | None:
    """آخرین زمان فعالیت ثبت شده برای یک کاربر را برمی‌گرداند."""
    result = await db.execute(
        select(func.max(ActivityLog.timestamp))
        .filter(ActivityLog.user_id == user_id)
    )
    return result.scalar_one_or_none()

# =================================================================
# توابع مدیریتی (Admin Panel)
# =================================================================

async def get_users_paginated(db: AsyncSession, page: int = 1, per_page: int = 10) -> tuple[list[User], int]:
    """لیستی از کاربران را به صورت صفحه‌بندی شده برای پنل ادمین برمی‌گرداند."""
    offset = (page - 1) * per_page

    users_query = select(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
    total_query = select(func.count(User.user_id))

    users_result = await db.execute(users_query)
    total_result = await db.execute(total_query)

    return list(users_result.scalars().all()), total_result.scalar_one()

async def delete_user_by_id(db: AsyncSession, user_id: int) -> bool:
    """یک کاربر را از پایگاه داده حذف می‌کند."""
    user = await find_user_by_id(db, user_id)
    if user:
        await db.delete(user)
        await db.commit()
        return True
    return False

async def ban_user(db: AsyncSession, user_id: int) -> bool:
    """یک کاربر را مسدود می‌کند."""
    user = await find_user_by_id(db, user_id)
    if user:
        user.is_banned = True
        await db.commit()
        return True
    return False

async def unban_user(db: AsyncSession, user_id: int) -> bool:
    """یک کاربر را از حالت مسدود خارج می‌کند."""
    user = await find_user_by_id(db, user_id)
    if user:
        user.is_banned = False
        await db.commit()
        return True
    return False

async def get_bot_stats(db: AsyncSession) -> dict:
    """آمار کلی ربات را برای پنل ادمین محاسبه می‌کند."""
    total_users = (await db.execute(select(func.count(User.user_id)))).scalar_one()
    new_users_today = (await db.execute(select(func.count(User.user_id)).filter(func.date(User.created_at) == datetime.date.today()))).scalar_one()
    total_downloads = (await db.execute(select(func.sum(User.total_downloads)))).scalar_one() or 0

    all_stats_json = (await db.execute(select(User.download_stats))).scalars().all()
    service_counts = {}
    for stats_json in all_stats_json:
        if stats_json:
            stats = json.loads(stats_json)
            for service, count in stats.items():
                service_counts[service] = service_counts.get(service, 0) + count

    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "total_downloads": total_downloads,
        "service_counts": service_counts
    }

# =================================================================
# توابع مربوط به کدهای تخفیف (Promo Codes)
# =================================================================

async def create_promo_code(db: AsyncSession, code: str, tier: str, duration_days: int, max_uses: int) -> PromoCode | None:
    """یک کد تخفیف جدید ایجاد می‌کند."""
    existing_code = (await db.execute(select(PromoCode).filter(PromoCode.code == code.upper()))).scalars().first()
    if existing_code:
        return None

    new_code = PromoCode(code=code.upper(), tier=tier, duration_days=duration_days, max_uses=max_uses)
    db.add(new_code)
    await db.commit()
    await db.refresh(new_code)
    return new_code

async def get_all_promo_codes(db: AsyncSession) -> list[PromoCode]:
    """تمام کدهای تخفیf را برمی‌گرداند."""
    result = await db.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
    return list(result.scalars().all())

async def delete_promo_code(db: AsyncSession, code_id: int) -> bool:
    """یک کد تخفیف را با استفاده از ID آن حذف می‌کند."""
    promo_code_result = await db.execute(select(PromoCode).filter(PromoCode.id == code_id))
    promo_code = promo_code_result.scalars().first()
    if promo_code:
        await db.delete(promo_code)
        await db.commit()
        return True
    return False

async def redeem_promo_code(db: AsyncSession, user: User, code: str) -> str:
    """یک کد تخفیf را برای کاربر اعمال می‌کند و نتیجه را به صورت متنی برمی‌گرداند."""
    promo_code_result = await db.execute(select(PromoCode).filter(PromoCode.code == code.upper(), PromoCode.is_active == True))
    promo_code = promo_code_result.scalars().first()

    if not promo_code:
        return "کد تخفیف نامعتبر یا منقضی شده است."

    if promo_code.uses_count >= promo_code.max_uses:
        return "ظرفیت استفاده از این کد تخفیف به پایان رسیده است."

    # <<-- FIX: Pass the user object directly -->>
    success = await set_user_plan(db, user, promo_code.tier, promo_code.duration_days)

    if success:
        promo_code.uses_count += 1
        await db.commit()
        return f"✅ اشتراک **{promo_code.tier.capitalize()}** با موفقیت برای شما فعال شد!"
    else:
        return "خطایی در فعال‌سازی اشتراک رخ داد. لطفاً با پشتیبانی تماس بگیرید."

# =================================================================
# توابع همزمان (Synchronous) که با پایگاه داده کار نمی‌کنند
# =================================================================

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