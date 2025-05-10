from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import uuid

from app.models.enhanced_resume import EnhancedResume
from app.schemas.resume import EnhancedResumeData

async def create_enhanced_resume(
    db: Session,
    enhanced_data: EnhancedResumeData,
    user_id: Optional[str] = None,
    source_file_name: Optional[str] = None,
    source_doc_id: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None
) -> EnhancedResume:
    """
    Create a new enhanced resume record in the database
    
    Args:
        db: Database session
        enhanced_data: Structured resume data
        user_id: Optional ID of the user
        source_file_name: Optional name of the source file
        source_doc_id: Optional ID of the source document
        meta_data: Optional additional metadata
        
    Returns:
        The created EnhancedResume object
    """
    enhanced_resume = EnhancedResume(
        id=str(uuid.uuid4()),
        user_id=user_id,
        personal_info=enhanced_data.personalInfo.dict(),
        work_experience=[exp.dict() for exp in enhanced_data.workExperience],
        education=[edu.dict() for edu in enhanced_data.education],
        skills=enhanced_data.skills,
        projects=[proj.dict() for proj in enhanced_data.projects],
        source_file_name=source_file_name,
        source_doc_id=source_doc_id,
        meta_data=meta_data or {}
    )
    
    db.add(enhanced_resume)
    db.commit()
    db.refresh(enhanced_resume)
    
    return enhanced_resume

async def get_enhanced_resumes_for_user(
    db: Session,
    user_id: str,
    skip: int = 0,
    limit: int = 100
) -> List[EnhancedResume]:
    """
    Get all enhanced resumes for a specific user
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of EnhancedResume objects
    """
    return db.query(EnhancedResume).filter(
        EnhancedResume.user_id == user_id,
        EnhancedResume.is_active == True
    ).order_by(EnhancedResume.created_at.desc()).offset(skip).limit(limit).all()

async def get_enhanced_resume_by_id(
    db: Session,
    enhanced_resume_id: str,
    user_id: Optional[str] = None
) -> Optional[EnhancedResume]:
    """
    Get an enhanced resume by its ID
    
    Args:
        db: Database session
        enhanced_resume_id: ID of the enhanced resume
        user_id: Optional user ID for access control
        
    Returns:
        The EnhancedResume object if found, None otherwise
    """
    query = db.query(EnhancedResume).filter(
        EnhancedResume.id == enhanced_resume_id,
        EnhancedResume.is_active == True
    )
    
    if user_id:
        query = query.filter(EnhancedResume.user_id == user_id)
        
    return query.first() 