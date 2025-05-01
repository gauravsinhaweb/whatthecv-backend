from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import uuid

from app.db.base import Base

class OTP(Base):
    __tablename__ = "otps"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, index=True)
    code = Column(String)
    purpose = Column(String)  # "signup", "login", "reset_password"
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.now() + timedelta(minutes=10))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    attempts = Column(Integer, default=0) 