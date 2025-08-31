# database/database.py

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base

# استفاده از درایور aiosqlite برای حالت غیرهمزمان
DATABASE_URL = "sqlite+aiosqlite:///bot_database.db"

# ساخت موتور غیرهمزمان
async_engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}, # برای SQLite همچنان لازم است
    echo=False, # برای دیباگ کردن کوئری‌ها می‌توانید True کنید
)

# ساخت یک SessionMaker غیرهمزمان که در کل پروژه استفاده خواهد شد
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def create_db():
    """تمام جداول را در پایگاه داده به صورت غیرهمزمان ایجاد می‌کند."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)