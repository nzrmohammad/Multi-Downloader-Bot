import datetime
from sqlalchemy import (Column, Integer, String, BigInteger, DateTime,
                        ForeignKey, Text, Date, func)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    daily_downloads = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    last_download_date = Column(Date, default=datetime.date.today)
    subscription_tier = Column(String, default='free')
    subscription_expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    language = Column(String, default='en') 
    settings_yt_quality = Column(String, default='audio')
    settings_spotify_quality = Column(String, default='audio')
    purchases = relationship("Purchase", back_populates="user")

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    purchase_date = Column(DateTime, default=datetime.datetime.utcnow)
    duration_days = Column(Integer)
    amount = Column(Integer, default=0)
    tier_purchased = Column(String)
    user = relationship("User", back_populates="purchases")

class FileCache(Base):
    __tablename__ = 'file_cache'
    id = Column(Integer, primary_key=True)
    original_url = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(BigInteger)

class ActivityLog(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    activity_type = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(String, nullable=True)

class Ticket(Base):
    __tablename__ = 'tickets'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger)
    message = Column(Text)
    status = Column(String, default='open')
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)