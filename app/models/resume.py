from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey, Text, LargeBinary
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    filename = Column(String)
    content = Column(Text)
    is_resume = Column(Boolean, default=True)
    score = Column(Integer, nullable=True)
    analysis = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ResumeFile(Base):
    __tablename__ = "resume_files"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    resume_id = Column(String, ForeignKey("resumes.id"))
    filename = Column(String)
    file_content = Column(LargeBinary)
    file_type = Column(String)
    file_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    company = Column(String, nullable=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    resume_id = Column(String, ForeignKey("resumes.id"))
    job_description_id = Column(String, ForeignKey("job_descriptions.id"), nullable=True)
    score = Column(Integer)
    is_resume = Column(Boolean, default=True)
    suggestions = Column(JSON)
    keywords = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 