from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any

from app.db.base import get_db
from app.models.user import User
from app.models.resume import Resume, JobDescription, ResumeFile
from app.services.auth import get_current_user, get_optional_current_user
from app.services.resume import (
    is_resume_document, analyze_resume, suggest_improvements, 
    save_resume, save_job_description, create_analysis,
    save_resume_file, get_resume_file, save_resume_with_file
)
from app.services.file import extract_text_from_file
from app.schemas.resume import (
    AIAnalysisResult, ResumeResponse, ResumeAnalysisCreate, 
    ResumeAnalysisResponse, SectionImprovement, ResumeFileResponse
)
import io

router = APIRouter(prefix="/resume", tags=["resume"])

@router.post("/check", response_model=dict)
async def check_if_resume(file: UploadFile = File(...)) -> Any:
    try:
        text = await extract_text_from_file(file)
        is_resume = await is_resume_document(text)
        return {"is_resume": is_resume}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/analyze", response_model=AIAnalysisResult)
async def analyze_resume_text(
    resume_text: str, 
    job_description: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user)
) -> Any:
    try:
        analysis = await analyze_resume(resume_text, job_description)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/improve-section", response_model=List[str])
async def improve_section(
    improvement_data: SectionImprovement,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
) -> Any:
    try:
        job_description = None
        if improvement_data.job_description_id and current_user:
            job = db.query(JobDescription).filter(
                JobDescription.id == improvement_data.job_description_id,
                JobDescription.user_id == current_user.id
            ).first()
            if job:
                job_description = job.content
        
        suggestions = await suggest_improvements(
            improvement_data.section,
            improvement_data.content,
            job_description
        )
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/upload", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        text = await extract_text_from_file(file)
        resume = await save_resume(db, current_user.id, file.filename, text)
        return resume
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/upload/with-file", response_model=dict)
async def upload_resume_with_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload a resume and store both the extracted text and the original file
    """
    try:
        # Extract text from the file
        text = await extract_text_from_file(file)
        
        # Reset file position to read binary content
        await file.seek(0)
        file_content = await file.read()
        
        # Save both text content and file
        resume, resume_file = await save_resume_with_file(
            db,
            current_user.id,
            file.filename,
            text,
            file_content,
            file.content_type
        )
        
        return {
            "resume_id": resume.id,
            "file_id": resume_file.id,
            "filename": resume.filename,
            "is_resume": resume.is_resume,
            "file_size": resume_file.file_size
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/files/{file_id}", response_class=StreamingResponse)
async def download_resume_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Download the original resume file
    """
    resume_file = await get_resume_file(db, file_id)
    
    if not resume_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Get the associated resume to check ownership
    resume = db.query(Resume).filter(Resume.id == resume_file.resume_id).first()
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this file"
        )
    
    # Return the file as a streaming response
    return StreamingResponse(
        io.BytesIO(resume_file.file_content),
        media_type=resume_file.file_type,
        headers={"Content-Disposition": f"attachment; filename={resume_file.filename}"}
    )

@router.get("/files", response_model=List[ResumeFileResponse])
async def list_resume_files(
    resume_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    List all resume files belonging to the current user
    Optionally filter by resume_id
    """
    try:
        query = db.query(ResumeFile)
        
        if resume_id:
            # Check if the resume belongs to the current user
            resume = db.query(Resume).filter(
                Resume.id == resume_id,
                Resume.user_id == current_user.id
            ).first()
            
            if not resume:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Resume not found"
                )
            
            query = query.filter(ResumeFile.resume_id == resume_id)
        else:
            # Only return files for resumes that belong to the current user
            query = query.join(Resume).filter(Resume.user_id == current_user.id)
        
        resume_files = query.all()
        return resume_files
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/job", response_model=dict)
async def create_job_description(
    title: str = Form(...),
    content: str = Form(...),
    company: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        job = await save_job_description(db, current_user.id, title, content, company)
        return {"id": job.id, "title": job.title}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/analysis", response_model=ResumeAnalysisResponse)
async def analyze_saved_resume(
    analysis_data: ResumeAnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    try:
        resume = db.query(Resume).filter(
            Resume.id == analysis_data.resume_id,
            Resume.user_id == current_user.id
        ).first()
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        if analysis_data.job_description_id:
            job = db.query(JobDescription).filter(
                JobDescription.id == analysis_data.job_description_id,
                JobDescription.user_id == current_user.id
            ).first()
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job description not found"
                )
        
        analysis = await create_analysis(db, analysis_data.resume_id, analysis_data.job_description_id)
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 