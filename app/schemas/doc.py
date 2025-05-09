from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
from app.models.doc import DocType

class DocTypeEnum(str, Enum):
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"
    ANALYSIS = "analysis"
    OTHER = "other"

class DocMetadata(BaseModel):
    """Base metadata for all document types"""
    pass

class ResumeMetadata(BaseModel):
    """Metadata specific to resume documents"""
    detected_sections: Optional[List[str]] = []
    ats_score: Optional[int] = None
    format_score: Optional[int] = None
    content_score: Optional[int] = None
    confidence: Optional[float] = None
    
    # Personal information fields
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_summary: Optional[str] = None
    
class JobDescriptionMetadata(BaseModel):
    """Metadata specific to job description documents"""
    company: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    
class AnalysisMetadata(BaseModel):
    """Metadata specific to analysis documents"""
    score: Optional[int] = None
    is_resume: Optional[bool] = True
    suggestions: Optional[List[Dict[str, Any]]] = []
    keywords: Optional[Dict[str, List[str]]] = {}
    
class RelatedDoc(BaseModel):
    """Information about a related document"""
    id: str
    doc_type: DocTypeEnum
    title: Optional[str] = None
    relationship_type: str
    
class DocBase(BaseModel):
    """Base document fields for creation/updates"""
    file_name: str  # Updated from title
    doc_type: DocTypeEnum
    extracted_text: Optional[str] = None  # Updated from text_content
    metadata: Optional[Dict[str, Any]] = Field(None, alias="meta_data")
    
class DocCreate(DocBase):
    """Schema for creating a new document without a file"""
    user_id: Optional[str] = None
    related_doc_ids: Optional[List[Dict[str, str]]] = None  # [{"id": "...", "relationship": "..."}]

class DocResponse(DocBase):
    """Schema for document responses"""
    id: str
    user_id: Optional[str] = None
    binary_content: Optional[bytes] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    
    # Personal information fields
    person_name: Optional[str] = None
    person_email: Optional[str] = None
    person_phone: Optional[str] = None
    person_address: Optional[str] = None
    person_links: Optional[str] = None
    
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    related_docs: Optional[List[RelatedDoc]] = []
    
    class Config:
        from_attributes = True
        populate_by_name = True  # Allow populating by attribute name instead of alias

class DocUpdate(BaseModel):
    """Schema for updating document properties"""
    file_name: Optional[str] = None  # Updated from title
    extracted_text: Optional[str] = None  # Updated from text_content
    metadata: Optional[Dict[str, Any]] = Field(None, alias="meta_data")
    is_active: Optional[bool] = None
    
    # Also allow updating personal info
    person_name: Optional[str] = None
    person_email: Optional[str] = None
    person_phone: Optional[str] = None
    person_address: Optional[str] = None
    person_links: Optional[str] = None
    
class DocSearch(BaseModel):
    """Schema for searching documents"""
    doc_type: Optional[DocTypeEnum] = None
    user_id: Optional[str] = None
    title_contains: Optional[str] = None  # Keep this for backward compatibility
    file_name_contains: Optional[str] = None  # New alias for title search
    content_contains: Optional[str] = None  # Keep for backward compatibility
    text_contains: Optional[str] = None  # New alias for content search
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    is_active: Optional[bool] = None
    related_to_doc_id: Optional[str] = None
    
class RelationshipCreate(BaseModel):
    """Schema for creating document relationships"""
    source_doc_id: str
    target_doc_id: str
    relationship_type: str

class DocFile(BaseModel):
    """Schema for file-related operations"""
    doc_id: str
    filename: str
    mime_type: str
    file_size: int 