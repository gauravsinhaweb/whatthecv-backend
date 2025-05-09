from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class KeywordMatch(BaseModel):
    matched: List[str]
    missing: List[str]

class Suggestion(BaseModel):
    section: str
    improvements: List[str]

class SectionAnalysis(BaseModel):
    name: str
    content: Optional[str] = None
    strengths: List[str] = []
    weaknesses: List[str] = []

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_summary: Optional[str] = None

class ResumeCheckResult(BaseModel):
    is_resume: bool
    confidence: float = Field(..., ge=0, le=1)
    detected_sections: List[str] = []
    reasoning: str = ""
    extracted_text: Optional[str] = None

class AIAnalysisResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    isResume: bool = True
    suggestions: List[Suggestion]
    keywords: KeywordMatch
    ats_score: Optional[int] = Field(None, ge=0, le=100)
    content_score: Optional[int] = Field(None, ge=0, le=100)
    format_score: Optional[int] = Field(None, ge=0, le=100)
    sections_analysis: Optional[List[SectionAnalysis]] = None
    personal_info: Optional[PersonalInfo] = None
    doc_ids: Optional[Dict[str, str]] = None

class ResumeCreate(BaseModel):
    filename: str
    content: str

class ResumeResponse(BaseModel):
    id: str
    filename: str
    is_resume: bool
    score: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ResumeFileResponse(BaseModel):
    """
    DEPRECATED: This schema is maintained only for backward compatibility.
    We are no longer storing binary file content in the database.
    """
    id: str
    resume_id: str
    filename: Optional[str] = "Unnamed file"
    file_type: str = "application/octet-stream"  # Default type
    file_size: int = 0  # Default size
    created_at: datetime
    
    class Config:
        from_attributes = True

class ResumeAnalysisCreate(BaseModel):
    resume_id: str
    job_description_id: Optional[str] = None

class ResumeAnalysisResponse(BaseModel):
    id: str
    score: int
    is_resume: bool
    suggestions: List[Suggestion]
    keywords: KeywordMatch
    created_at: datetime
    
    class Config:
        from_attributes = True

class SectionImprovement(BaseModel):
    section: str
    content: str
    job_description_id: Optional[str] = None 