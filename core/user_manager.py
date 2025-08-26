import datetime
from sqlalchemy import func
from telegram import Update

from database.database import SessionLocal
from database.models import User, Purchase, ActivityLog

# --- User Management ---

def get_or_create_user(update: Update) -> User:
    """Gets a user from the DB or creates one if they don't exist. Also updates their status."""
    db = SessionLocal()
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, username=username)
        db.add(user)
        log_activity(user_id, 'register', db_session=db)
    else:
        user.username = username # Update username if changed
    
    # Check for subscription expiration
    if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date < datetime.datetime.utcnow():
        user.subscription_tier = 'free'
    
    # Reset daily download count if a new day has started
    if user.last_download_date != datetime.date.today():
        user.daily_downloads = 0
        user.last_download_date = datetime.date.today()
    
    db.commit()
    db.refresh(user)
    db.close()
    return user

# --- Subscription and Plan Management ---

def set_user_plan(user_id: int, tier: str, duration_days: int) -> bool:
    """Sets a user's subscription plan and duration."""
    db = SessionLocal()
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        db.close()
        return False

    # Calculate new expiry date
    if user.subscription_tier != 'free' and user.subscription_expiry_date and user.subscription_expiry_date > datetime.datetime.utcnow():
        new_expiry_date = user.subscription_expiry_date + datetime.timedelta(days=duration_days)
    else:
        new_expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=duration_days)
    
    user.subscription_tier = tier
    user.subscription_expiry_date = new_expiry_date
    
    # Log the purchase/grant
    new_purchase = Purchase(user_id=user_id, duration_days=duration_days, tier_purchased=tier)
    db.add(new_purchase)
    
    db.commit()
    db.close()
    return True

# --- Activity and Download Logic ---

def can_download(user: User) -> bool:
    """Checks if a user is allowed to perform a download based on their plan."""
    tier_limits = {
        'free': 5,
        'silver': 30,
        'gold': float('inf'), # Unlimited
        'platinum': float('inf')
    }
    limit = tier_limits.get(user.subscription_tier, 0)
    return user.daily_downloads < limit

def increment_download_count(user_id: int):
    """Increments the daily and total download counts for a user."""
    db = SessionLocal()
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.daily_downloads += 1
        user.total_downloads += 1
        db.commit()
    db.close()

def log_activity(user_id: int, activity_type: str, details: str = None, db_session=None):
    """Logs a user activity."""
    close_session = False
    if db_session is None:
        db_session = SessionLocal()
        close_session = True
        
    log = ActivityLog(user_id=user_id, activity_type=activity_type, details=details)
    db_session.add(log)
    db_session.commit()
    
    if close_session:
        db_session.close()

# --- Admin Utilities ---

def get_users_paginated(page: int = 1, per_page: int = 10):
    """Gets a paginated list of users for the admin panel."""
    db = SessionLocal()
    offset = (page - 1) * per_page
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(per_page).all()
    total_users = db.query(func.count(User.user_id)).scalar()
    db.close()
    return users, total_users