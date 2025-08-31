# core/user_manager.py

import datetime
import json
from sqlalchemy import func
from telegram import Update

from database.database import SessionLocal
from database.models import User, Purchase, ActivityLog, PromoCode

def get_download_stats(user_id: int) -> dict:
    """Gets a user's download stats from the new JSON column."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user and user.download_stats:
            return json.loads(user.download_stats)
        return {}
    finally:
        db.close()

def set_user_language(user_id: int, language: str):
    """Sets the user's preferred language."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.language = language
            db.commit()
    finally:
        db.close()

def set_user_quality_setting(user_id: int, platform: str, quality: str):
    """Updates a user's download quality setting for a specific platform."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return

        if platform == 'yt':
            user.settings_yt_quality = quality
        elif platform == 'spotify':
            user.settings_spotify_quality = quality
        
        db.commit()
    finally:
        db.close()

def get_or_create_user(update: Update) -> User:
    """Gets a user from the DB or creates one if they don't exist. Also updates their status."""
    db = SessionLocal()
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id, username=username)
            db.add(user)
            # Pass the session to avoid opening a new one
            log_activity(user_id, 'register', db_session=db) 
        else:
            user.username = username # Update username if changed
        
        if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date < datetime.datetime.utcnow():
            user.subscription_tier = 'free'
        
        if user.last_download_date != datetime.date.today():
            user.daily_downloads = 0
            user.last_download_date = datetime.date.today()
        
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def set_user_plan(user_id: int, tier: str, duration_days: int) -> bool:
    """Sets a user's subscription plan and duration."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False

        if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date > datetime.datetime.utcnow():
            new_expiry_date = user.subscription_expiry_date + datetime.timedelta(days=duration_days)
        else:
            new_expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=duration_days)
        
        user.subscription_tier = tier
        user.subscription_expiry_date = new_expiry_date
        
        new_purchase = Purchase(user_id=user_id, duration_days=duration_days, tier_purchased=tier)
        db.add(new_purchase)
        
        db.commit()
        return True
    finally:
        db.close()

def can_download(user: User) -> bool:
    """Checks if a user is allowed to perform a download based on their plan."""
    tier_limits = {
        'free': 5,
        'silver': 30,
        'gold': float('inf'),
        'platinum': float('inf')
    }
    limit = tier_limits.get(user.subscription_tier, 0)
    return user.daily_downloads < limit

def increment_download_count(user_id: int):
    """Increments the daily and total download counts for a user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.daily_downloads += 1
            user.total_downloads += 1
            db.commit()
    finally:
        db.close()

def log_activity(user_id: int, activity_type: str, details: str = None, db_session=None):
    """Logs a user activity and updates their download stats."""
    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True
    
    try:
        log = ActivityLog(user_id=user_id, activity_type=activity_type, details=details)
        db_session.add(log)
        
        if activity_type == 'download' and details:
            user = db_session.query(User).filter(User.user_id == user_id).first()
            if user:
                stats = json.loads(user.download_stats or '{}')
                service = details.split(':')[0]
                stats[service] = stats.get(service, 0) + 1
                user.download_stats = json.dumps(stats)
        
        db_session.commit()
    finally:
        if close_session:
            db_session.close()

def get_users_paginated(page: int = 1, per_page: int = 10):
    """Gets a paginated list of users for the admin panel."""
    db = SessionLocal()
    try:
        offset = (page - 1) * per_page
        users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(per_page).all()
        total_users = db.query(func.count(User.user_id)).scalar()
        return users, total_users
    finally:
        db.close()

def find_user_by_id(user_id: int) -> User | None:
    """Finds a user by their Telegram ID."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        return user
    finally:
        db.close()

def delete_user_by_id(user_id: int) -> bool:
    """Deletes a user from the database."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False
    finally:
        db.close()

def get_all_user_ids() -> list[int]:
    """Returns a list of all user IDs from the database."""
    db = SessionLocal()
    try:
        users = db.query(User.user_id).all()
        return [user_id for (user_id,) in users]
    finally:
        db.close()

def get_batch_limit(user: User) -> int:
    """محدودیت دانلود دسته‌ای کاربر را بر اساس پلن اشتراک برمی‌گرداند."""
    if user.is_banned:
        return 0
        
    limits = {
        'free': 1,
        'bronze': 1,
        'silver': 1,
        'gold': 10,
        'diamond': 50
    }
    return limits.get(user.subscription_tier, 1)

# ✨ تابع جدید برای مسدود/آزاد کردن کاربر
def ban_user(user_id: int) -> bool:
    """یک کاربر را مسدود می‌کند."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.is_banned = True
            db.commit()
            return True
        return False
    finally:
        db.close()

def unban_user(user_id: int) -> bool:
    """یک کاربر را از مسدودیت خارج می‌کند."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.is_banned = False
            db.commit()
            return True
        return False
    finally:
        db.close()

def get_bot_stats() -> dict:
    """آمار کلی ربات را برمی‌گرداند."""
    db = SessionLocal()
    try:
        total_users = db.query(func.count(User.user_id)).scalar()
        today = datetime.date.today()
        new_users_today = db.query(func.count(User.user_id)).filter(func.date(User.created_at) == today).scalar()
        total_downloads = db.query(func.sum(User.total_downloads)).scalar() or 0
        
        # استخراج آمار دانلود از ستون JSON
        all_stats = db.query(User.download_stats).all()
        service_counts = {}
        for stats_json, in all_stats:
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
    finally:
        db.close()

def create_promo_code(code: str, tier: str, duration_days: int, max_uses: int) -> PromoCode | None:
    """یک کد تخفیف جدید ایجاد می‌کند."""
    db = SessionLocal()
    try:
        existing_code = db.query(PromoCode).filter(PromoCode.code == code).first()
        if existing_code:
            return None # کد تکراری است
        
        new_code = PromoCode(
            code=code.upper(),
            tier=tier,
            duration_days=duration_days,
            max_uses=max_uses
        )
        db.add(new_code)
        db.commit()
        db.refresh(new_code)
        return new_code
    finally:
        db.close()

def get_all_promo_codes() -> list[PromoCode]:
    """تمام کدهای تخفیف را برمی‌گرداند."""
    db = SessionLocal()
    try:
        return db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()
    finally:
        db.close()

def delete_promo_code(code_id: int) -> bool:
    """یک کد تخفیف را با استفاده از ID آن حذف می‌کند."""
    db = SessionLocal()
    try:
        promo_code = db.query(PromoCode).filter(PromoCode.id == code_id).first()
        if promo_code:
            db.delete(promo_code)
            db.commit()
            return True
        return False
    finally:
        db.close()

def redeem_promo_code(user_id: int, code: str) -> str:
    """یک کد تخفیف را برای کاربر اعمال می‌کند و نتیجه را به صورت متنی برمی‌گرداند."""
    db = SessionLocal()
    try:
        # کد با حروف بزرگ و فعال جستجو می‌شود
        promo_code = db.query(PromoCode).filter(
            PromoCode.code == code.upper(), 
            PromoCode.is_active == True
        ).first()

        if not promo_code:
            return "کد تخفیف نامعتبر یا منقضی شده است."

        if promo_code.uses_count >= promo_code.max_uses:
            return "ظرفیت استفاده از این کد تخفیف به پایان رسیده است."

        # اشتراک برای کاربر ثبت می‌شود
        success = set_user_plan(user_id, promo_code.tier, promo_code.duration_days)

        if success:
            promo_code.uses_count += 1
            db.commit()
            return f"✅ اشتراک **{promo_code.tier.capitalize()}** با موفقیت برای شما فعال شد!"
        else:
            return "خطایی در فعال‌سازی اشتراک رخ داد. لطفاً با پشتیبانی تماس بگیرید."

    finally:
        db.close()