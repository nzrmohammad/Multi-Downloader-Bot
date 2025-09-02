# core/user_manager/promo_codes.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, PromoCode
from .profile import set_user_plan # وارد کردن از ماژول هم‌سطح

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
    """تمام کدهای تخفیف را برمی‌گرداند."""
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
    """یک کد تخفیف را برای کاربر اعمال می‌کند."""
    promo_code_result = await db.execute(select(PromoCode).filter(PromoCode.code == code.upper(), PromoCode.is_active == True))
    promo_code = promo_code_result.scalars().first()
    if not promo_code:
        return "کد تخفیف نامعتبر یا منقضی شده است."
    if promo_code.uses_count >= promo_code.max_uses:
        return "ظرفیت استفاده از این کد تخفیف به پایان رسیده است."
    success = await set_user_plan(db, user, promo_code.tier, promo_code.duration_days)
    if success:
        promo_code.uses_count += 1
        await db.commit()
        return f"✅ اشتراک **{promo_code.tier.capitalize()}** با موفقیت فعال شد!"
    else:
        return "خطایی در فعال‌سازی اشتراک رخ داد."