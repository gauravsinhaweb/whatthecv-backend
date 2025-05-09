from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union, Set
from enum import Enum
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
    name: str = Field("", description="Full name")
    title: str = Field("", description="Job title")
    email: str = Field("", description="Email address")
    phone: str = Field("", description="Phone number")
    location: str = Field("", description="Location (country)")
    summary: str = Field("", description="Professional summary")
    profilePicture: Optional[str] = Field(None, description="Profile picture URL")

class WorkExperience(BaseModel):
    id: str = Field(..., description="Unique identifier")
    title: str = Field("", description="Job title")
    company: str = Field("", description="Company name")
    location: str = Field("", description="Location (country)")
    startDate: str = Field("", description="Start date")
    endDate: str = Field("", description="End date or 'Present'")
    current: bool = Field(False, description="Whether this is the current job")
    description: str = Field("", description="Job description with bullet points")

class Education(BaseModel):
    id: str = Field(..., description="Unique identifier")
    degree: str = Field("", description="Degree name")
    institution: str = Field("", description="Institution name")
    location: str = Field("", description="Location (country)")
    startDate: str = Field("", description="Start date")
    endDate: str = Field("", description="End date")
    description: str = Field("", description="Additional details")

class Project(BaseModel):
    id: str = Field(..., description="Unique identifier")
    name: str = Field("", description="Project name")
    description: str = Field("", description="Project description")
    technologies: str = Field("", description="Technologies used")
    link: str = Field("", description="Project URL")

class ResumeCheckResult(BaseModel):
    is_resume: bool = Field(..., description="Whether the document is a resume")
    confidence: float = Field(..., description="Confidence score (0-1)")
    detected_sections: List[str] = Field(default_factory=list, description="List of detected resume sections")
    reasoning: str = Field(..., description="Explanation of the decision")
    extracted_text: Optional[str] = Field(None, description="Extracted text (only included if return_text=True)")

class AIAnalysisResult(BaseModel):
    score: int = Field(..., description="Overall score")
    ats_score: Optional[int] = Field(None, description="ATS compatibility score")
    content_score: Optional[int] = Field(None, description="Content quality score")
    format_score: Optional[int] = Field(None, description="Format score")
    feedback: Optional[Dict[str, List[str]]] = Field(None, description="Feedback details")
    sections_analysis: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Section-by-section analysis")
    keywords: Dict[str, List[str]] = Field(default_factory=lambda: {"matched": [], "missing": []}, description="Keyword analysis")
    suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="Improvement suggestions")
    doc_ids: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Associated document IDs")
    extracted_text: Optional[str] = Field(None, description="Extracted text from the resume")

class ResumeCreate(BaseModel):
    filename: str
    content: str

class ResumeResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    filename: str
    content: str
    is_resume: bool
    created_at: str

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
    resume_id: int
    job_description_id: Optional[int] = None

class ResumeAnalysisResponse(BaseModel):
    id: int
    resume_id: int
    job_description_id: Optional[int] = None
    content: Dict[str, Any]
    created_at: str

class SectionImprovement(BaseModel):
    section: str = Field(..., description="Section name")
    content: str = Field(..., description="Section content")
    job_description_id: Optional[int] = Field(None, description="Job description ID to use for tailoring")

class EnhancedResumeData(BaseModel):
    personalInfo: PersonalInfo = Field(..., description="Personal information")
    workExperience: List[WorkExperience] = Field(default_factory=list, description="Work experience entries")
    education: List[Education] = Field(default_factory=list, description="Education entries")
    skills: List[str] = Field(default_factory=list, description="Skills")
    projects: List[Project] = Field(default_factory=list, description="Projects")
    extracted_text: Optional[str] = Field(None, description="Original extracted text") 