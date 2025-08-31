from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base

# Using SQLite for simplicity. For production, consider PostgreSQL.
DATABASE_URL = "sqlite:///bot_database.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db():
    """Creates all tables in the database."""
    Base.metadata.create_all(bind=engine)