# core/handlers/service_manager.py

from database.database import SessionLocal
from database.models import ServiceStatus
from services import SERVICES # <-- تغییر مهم: وارد کردن از مکان جدید

def get_service_names():
    """نام تمام سرویس‌های تعریف شده را برمی‌گرداند."""
    return [s.__class__.__name__.replace("Service", "").lower() for s in SERVICES]

def initialize_services():
    """سرویس‌های تعریف شده را در دیتابیس ثبت می‌کند."""
    db = SessionLocal()
    existing_services = {s.service_name for s in db.query(ServiceStatus).all()}
    
    for service_name in get_service_names():
        if service_name not in existing_services:
            new_service = ServiceStatus(service_name=service_name, is_enabled=True)
            db.add(new_service)
            print(f"Registered service: {service_name}, Enabled: True")
            
    db.commit()
    db.close()

def get_service_status(service_name: str) -> bool:
    """وضعیت یک سرویس را از دیتابیس می‌خواند."""
    db = SessionLocal()
    service = db.query(ServiceStatus).filter(ServiceStatus.service_name == service_name).first()
    db.close()
    return service.is_enabled if service else False

def get_all_statuses() -> list:
    """وضعیت تمام سرویس‌ها را برمی‌گرداند."""
    db = SessionLocal()
    statuses = db.query(ServiceStatus).all()
    db.close()
    return statuses

def toggle_service_status(service_name: str) -> bool:
    """وضعیت یک سرویس را تغییر می‌دهد."""
    db = SessionLocal()
    service = db.query(ServiceStatus).filter(ServiceStatus.service_name == service_name).first()
    if service:
        service.is_enabled = not service.is_enabled
        db.commit()
        new_status = service.is_enabled
        db.close()
        return new_status
    db.close()
    return False