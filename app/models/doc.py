from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey, Text, LargeBinary, Table, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from app.db.base import Base

# Association table for doc relationships (self-referential many-to-many)
doc_relationships = Table(
    "doc_relationships",
    Base.metadata,
    Column("source_doc_id", String, ForeignKey("docs.id"), primary_key=True),
    Column("target_doc_id", String, ForeignKey("docs.id"), primary_key=True),
    Column("relationship_type", String),  # e.g., 'analysis_of', 'job_for', etc.
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

class DocType(enum.Enum):
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description" 
    ANALYSIS = "analysis"
    OTHER = "other"

class Doc(Base):
    """
    Consolidated document model that replaces multiple specialized tables:
    - Resumes
    - Resume files
    - Job descriptions
    - Resume analyses
    
    Uses a flexible schema with metadata JSON for type-specific fields.
    """
    __tablename__ = "docs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Document classification
    doc_type = Column(Enum(DocType), index=True)
    file_name = Column(String)  # Renamed from 'title'
    
    # Text content (e.g., resume text, job description)
    extracted_text = Column(Text, nullable=True)  # Renamed from 'text_content'
    
    # Binary content (for file storage)
    binary_content = Column(LargeBinary, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # Personal information fields for resume documents
    person_name = Column(String, nullable=True)
    person_email = Column(String, nullable=True)
    person_phone = Column(String, nullable=True)
    person_address = Column(Text, nullable=True)
    person_links = Column(Text, nullable=True)
    
    # Flexible metadata (analysis results, scores, etc.)
    meta_data = Column(JSON, nullable=True)
    
    # Common fields
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Self-referential relationships (e.g., analysis -> resume)
    related_docs = relationship(
        "Doc",
        secondary=doc_relationships,
        primaryjoin=id==doc_relationships.c.source_doc_id,
        secondaryjoin=id==doc_relationships.c.target_doc_id,
        backref="referenced_by"
    ) 