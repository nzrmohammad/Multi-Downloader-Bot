# core/handlers/service_manager.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database.database import AsyncSessionLocal
from database.models import ServiceStatus
from services import SERVICES

def get_service_names() -> list[str]:
    """
    نام تمام سرویس‌های تعریف شده در پروژه را برمی‌گرداند.
    (این تابع با دیتابیس کاری ندارد و sync باقی می‌ماند)
    """
    return [s.__class__.__name__.replace("Service", "").lower() for s in SERVICES]

async def initialize_services():
    """
    سرویس‌های تعریف شده را در دیتابیس به صورت غیرهمزمان ثبت می‌کند.
    این تابع باید در هنگام راه‌اندازی ربات فراخوانی شود.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ServiceStatus.service_name))
        existing_services = {s for s in result.scalars().all()}
        
        new_services = []
        for service_name in get_service_names():
            if service_name not in existing_services:
                new_services.append(ServiceStatus(service_name=service_name, is_enabled=True))
                print(f"Registered service: {service_name}, Enabled: True")
        
        if new_services:
            db.add_all(new_services)
            await db.commit()

async def get_service_status(service_name: str) -> bool:
    """وضعیت یک سرویس را از دیتابیس به صورت غیرهمزمان می‌خواند."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ServiceStatus.is_enabled).filter(ServiceStatus.service_name == service_name)
        )
        status = result.scalar_one_or_none()
        # اگر سرویس در دیتابیس نباشد، به طور پیش‌فرض آن را غیرفعال در نظر می‌گیریم
        return status if status is not None else False

async def get_all_statuses() -> list[ServiceStatus]:
    """وضعیت تمام سرویس‌ها را به صورت غیرهمزمان برمی‌گرداند."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ServiceStatus))
        return list(result.scalars().all())

async def toggle_service_status(service_name: str) -> bool | None:
    """وضعیت فعال/غیرفعال بودن یک سرویس را تغییر می‌دهد."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ServiceStatus).filter(ServiceStatus.service_name == service_name))
        service = result.scalars().first()
        
        if service:
            service.is_enabled = not service.is_enabled
            await db.commit()
            return service.is_enabled
        return None