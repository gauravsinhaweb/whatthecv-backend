from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class KeywordMatch(BaseModel):
    matched: List[str]
    missing: List[str]

class Suggestion(BaseModel):
    section: str
    improvements: List[str]

class AIAnalysisResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    isResume: bool
    suggestions: List[Suggestion]
    keywords: KeywordMatch

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
    id: str
    resume_id: str
    filename: str
    file_type: str
    file_size: int
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