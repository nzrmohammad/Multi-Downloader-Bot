# core/user_manager/admin_actions.py
import datetime
import json
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from .profile import find_user_by_id # وارد کردن از ماژول هم‌سطح

async def get_all_user_ids(db: AsyncSession) -> list[int]:
    """لیست تمام شناسه‌های کاربری را برمی‌گرداند."""
    result = await db.execute(select(User.user_id))
    return list(result.scalars().all())

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