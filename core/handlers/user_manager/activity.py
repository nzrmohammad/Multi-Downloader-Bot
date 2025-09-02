# core/user_manager/activity.py
import datetime
import json
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, ActivityLog

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