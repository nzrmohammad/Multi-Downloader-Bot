# core/user_manager/profile.py
import datetime
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from database.models import User, Purchase
from .activity import log_activity # وارد کردن از ماژول هم‌سطح

async def get_or_create_user(db: AsyncSession, update: Update) -> User:
    """کاربر را از پایگاه داده دریافت کرده یا در صورت عدم وجود، ایجاد می‌کند."""
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

def get_download_stats(user: User) -> dict:
    """آمار دانلود کاربر را از ستون JSON دریافت می‌کند."""
    if user and user.download_stats:
        return json.loads(user.download_stats)
    return {}