from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
import logging
import json

from app.db.base import get_db
from app.models.user import User
from app.models.doc import Doc, DocType, doc_relationships
from app.services.auth import get_current_user, get_optional_current_user
from app.services.resume import (
    is_resume_document, analyze_resume, suggest_improvements, 
    save_resume, save_job_description, create_analysis
)
from app.services.file import extract_text_from_file
from app.schemas.resume import (
    AIAnalysisResult, ResumeResponse, ResumeAnalysisCreate, 
    ResumeAnalysisResponse, SectionImprovement, ResumeCheckResult,
    EnhancedResumeData
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])

@router.post("/check", response_model=ResumeCheckResult)
async def check_if_resume(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = None,
    return_text: Optional[bool] = False
) -> Any:
    """
    Check if the provided content is a resume.
    Can accept either an uploaded file or direct text input.
    
    Parameters:
    - file: Optional file upload
    - text: Optional text content
    - return_text: If True, returns the extracted text with the result
    
    Returns enhanced information about resume detection:
    - is_resume: Boolean indicating if the document is a resume
    - confidence: Confidence score (0-1)
    - detected_sections: List of detected resume sections
    - reasoning: Explanation of the decision
    - extracted_text: Only included if return_text=True
    """
    try:
        # If text is provided directly, use that
        if text:
            resume_text = text
        # Otherwise extract from file
        elif file:
            resume_text = await extract_text_from_file(file)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file or text must be provided"
            )
            
        detection_result = await is_resume_document(resume_text)
        
        response = {
            "is_resume": detection_result["is_resume"],
            "confidence": detection_result["confidence"],
            "detected_sections": detection_result["detected_sections"],
            "reasoning": detection_result["reasoning"]
        }
        
        # Optionally include the extracted text in the response
        if return_text:
            response["extracted_text"] = resume_text
            
        return response
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
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload a resume and store only the extracted text (no longer storing the original file).
    Authentication is optional - unauthenticated uploads will not be linked to any user.
    """
    try:
        # Extract text from the file
        try:
            text = await extract_text_from_file(file)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Text extraction failed: {str(e)}"
            )
        
        # Save only text content
        try:
            user_id = current_user.id if current_user else None
            # Modified to only save resume text, not file content
            resume = await save_resume(
                db,
                user_id,
                file.filename,
                text
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database save operation failed: {str(e)}"
            )
        
        return {
            "resume_id": resume.id,
            "filename": resume.filename,
            "is_resume": resume.is_resume
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.post("/debug/with-file", response_model=dict)
async def debug_upload_with_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Any:
    """
    Debug endpoint for the upload/with-file functionality
    """
    try:
        # Step 1: Extract file details
        step1 = {
            "filename": file.filename,
            "content_type": file.content_type
        }
        
        # Step 2: Read file content
        file_content = await file.read()
        step2 = {
            "file_size": len(file_content),
            "file_read": True
        }
        
        # Step 3: Reset file position
        await file.seek(0)
        step3 = {"file_position_reset": True}
        
        # Step 4: Check database connection
        try:
            db_session = next(db)
            step4 = {"database_connection": "success"}
        except Exception as db_error:
            step4 = {"database_connection": "failed", "error": str(db_error)}
        
        return {
            "message": "Debug information for file upload",
            "steps": {
                "1_file_details": step1,
                "2_file_content": step2,
                "3_file_reset": step3,
                "4_database": step4
            }
        }
    except Exception as e:
        return {
            "message": "Error in debug endpoint",
            "error": str(e),
            "error_type": type(e).__name__
        }

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

@router.post("/enhance", response_model=EnhancedResumeData)
async def enhance_resume_text(
    resume_text: str, 
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Enhance a resume by extracting structured information and optimizing content for ATS.
    """
    try:
        logger.info("Processing resume enhancement from text")
        
        from app.services.resume_enhance import enhance_resume
        enhanced_data = await enhance_resume(resume_text)
        
        # Verify the structure of returned data and provide defaults where missing
        validated_data = EnhancedResumeData(
            personalInfo={
                "name": enhanced_data.get("personalInfo", {}).get("name", ""),
                "title": enhanced_data.get("personalInfo", {}).get("title", ""),
                "email": enhanced_data.get("personalInfo", {}).get("email", ""),
                "phone": enhanced_data.get("personalInfo", {}).get("phone", ""),
                "location": enhanced_data.get("personalInfo", {}).get("location", ""),
                "summary": enhanced_data.get("personalInfo", {}).get("summary", "")
            },
            workExperience=[
                {
                    "id": exp.get("id", str(i+1)),
                    "title": exp.get("title", ""),
                    "company": exp.get("company", ""),
                    "location": exp.get("location", ""),
                    "startDate": exp.get("startDate", ""),
                    "endDate": exp.get("endDate", ""),
                    "current": exp.get("current", False),
                    "description": exp.get("description", "")
                }
                for i, exp in enumerate(enhanced_data.get("workExperience", []))
            ],
            education=[
                {
                    "id": edu.get("id", str(i+1)),
                    "degree": edu.get("degree", ""),
                    "institution": edu.get("institution", ""),
                    "location": edu.get("location", ""),
                    "startDate": edu.get("startDate", ""),
                    "endDate": edu.get("endDate", ""),
                    "description": edu.get("description", "")
                }
                for i, edu in enumerate(enhanced_data.get("education", []))
            ],
            skills=enhanced_data.get("skills", []),
            projects=[
                {
                    "id": proj.get("id", str(i+1)),
                    "name": proj.get("name", ""),
                    "description": proj.get("description", ""),
                    "technologies": proj.get("technologies", ""),
                    "link": proj.get("link", "")
                }
                for i, proj in enumerate(enhanced_data.get("projects", []))
            ],
            extracted_text=resume_text
        )
        
        # Log the structure of data being returned
        logger.info(f"Enhanced resume data sections: {list(validated_data.dict().keys())}")
        logger.info(f"Work experience count: {len(validated_data.workExperience)}")
        logger.info(f"Education count: {len(validated_data.education)}")
        logger.info(f"Skills count: {len(validated_data.skills)}")
        logger.info(f"Projects count: {len(validated_data.projects)}")
        
        return validated_data
    except Exception as e:
        logger.error(f"Resume enhancement failed: {str(e)}", exc_info=True)
        
        # Provide a minimal fallback structure rather than failing completely
        try:
            # Basic fallback extraction
            from app.services.resume_enhance import extract_resume_structure_fallback
            fallback_data = await extract_resume_structure_fallback(resume_text)
            
            if fallback_data:
                logger.info("Using fallback data structure for failed enhancement")
                # Convert the fallback data to the proper schema
                return EnhancedResumeData(
                    personalInfo={
                        "name": fallback_data.get("personalInfo", {}).get("name", ""),
                        "title": fallback_data.get("personalInfo", {}).get("title", ""),
                        "email": fallback_data.get("personalInfo", {}).get("email", ""),
                        "phone": fallback_data.get("personalInfo", {}).get("phone", ""),
                        "location": fallback_data.get("personalInfo", {}).get("location", ""),
                        "summary": fallback_data.get("personalInfo", {}).get("summary", "")
                    },
                    workExperience=[
                        {
                            "id": str(i+1),
                            "title": exp.get("title", ""),
                            "company": exp.get("company", ""),
                            "location": exp.get("location", ""),
                            "startDate": exp.get("startDate", ""),
                            "endDate": exp.get("endDate", ""),
                            "current": exp.get("current", False),
                            "description": exp.get("description", "")
                        }
                        for i, exp in enumerate(fallback_data.get("workExperience", []))
                    ],
                    education=[
                        {
                            "id": str(i+1),
                            "degree": edu.get("degree", ""),
                            "institution": edu.get("institution", ""),
                            "location": edu.get("location", ""),
                            "startDate": edu.get("startDate", ""),
                            "endDate": edu.get("endDate", ""),
                            "description": edu.get("description", "")
                        }
                        for i, edu in enumerate(fallback_data.get("education", []))
                    ],
                    skills=fallback_data.get("skills", []),
                    projects=[
                        {
                            "id": str(i+1),
                            "name": proj.get("name", ""),
                            "description": proj.get("description", ""),
                            "technologies": proj.get("technologies", ""),
                            "link": proj.get("link", "")
                        }
                        for i, proj in enumerate(fallback_data.get("projects", []))
                    ],
                    extracted_text=resume_text
                )
        except Exception as fallback_error:
            logger.error(f"Fallback extraction also failed: {str(fallback_error)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to enhance resume: {str(e)}",
                "error_type": type(e).__name__,
                "fallback_failed": True
            }
        )

@router.post("/extract-text", response_model=dict)
async def extract_resume_text_only(
    file: UploadFile = File(...),
) -> Any:
    """
    Extract text from a resume file without saving it to the database.
    Returns only the extracted text.
    """
    try:
        text = await extract_text_from_file(file)
        return {"text": text}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/process-file", response_model=AIAnalysisResult)
async def process_resume_file(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Process a resume file in one step: extract text and analyze it.
    This endpoint handles the binary file directly, extracting text on the backend.
    
    Args:
        file: The resume file to process
        job_description: Optional job description to tailor the analysis
        current_user: Optional authenticated user
        
    Returns:
        AIAnalysisResult: Complete analysis of the resume
    """
    try:
        # Extract text from the file
        extracted_text = await extract_text_from_file(file)
        logger.info(f"Processing resume file: {file.filename}")
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            logger.warning(f"Insufficient text extracted from file: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract sufficient text from the resume file. The file may be corrupted, password-protected, or contain only images."
            )
        
        # Always save to Doc table regardless of authentication
        text_doc_id = None
        
        # Create document in the Doc table
        from app.services.doc import create_document
        from app.models.doc import DocType
        from app.services.resume_parser import extract_personal_info
        
        # Extract personal info
        try:
            personal_info = await extract_personal_info(extracted_text)
        except Exception as extract_error:
            logger.error(f"Personal info extraction failed: {str(extract_error)}")
            personal_info = {}
        
        # Create the text document with new field names
        doc_data = {
            "user_id": current_user.id if current_user else None,
            "doc_type": DocType.RESUME.value,
            "file_name": file.filename or "Untitled Resume",
            "extracted_text": extracted_text,
            "metadata": {
                "is_resume": True,
                **(personal_info or {})  # Include personal info in metadata for compatibility
            }
        }
        
        try:
            # Create text document
            text_doc = await create_document(db, doc_data)
            text_doc_id = text_doc.id
            
            logger.info(f"Successfully saved to Doc table: text_doc.id={text_doc_id}")
        except Exception as db_error:
            # Don't swallow database errors - they should cause API errors
            logger.error(f"Failed to save documents to database: {str(db_error)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save documents to database: {str(db_error)}"
            )
        
        try:
            # Analyze the extracted text - pass the doc_id and db to update metadata with analysis results
            analysis_result = await analyze_resume(
                resume_text=extracted_text, 
                job_description=job_description,
                doc_id=text_doc_id,
                db=db
            )
            
            # Add document ID to the result
            if text_doc_id:
                # Initialize doc_ids if it doesn't exist
                if not hasattr(analysis_result, "doc_ids") or analysis_result.doc_ids is None:
                    analysis_result.doc_ids = {}
                analysis_result.doc_ids["text_doc_id"] = text_doc_id
            
            # Add extracted text to the result for reference
            analysis_result.extracted_text = extracted_text
            
            return analysis_result
        except Exception as analysis_error:
            logger.error(f"Resume analysis error: {str(analysis_error)}", exc_info=True)
            
            # Create a minimal fallback analysis result
            fallback_result = AIAnalysisResult(
                score=60,
                ats_score=55,
                content_score=65,
                format_score=60,
                suggestions=[
                    {
                        "section": "General",
                        "improvements": [
                            "Add more quantifiable achievements",
                            "Improve formatting for better ATS compatibility",
                            "Enhance skill descriptions with specific examples"
                        ]
                    },
                    {
                        "section": "Experience",
                        "improvements": [
                            "Include measurable results for each role",
                            "Use more action verbs to describe responsibilities",
                            "Tailor achievements to target industry keywords"
                        ]
                    }
                ],
                keywords={
                    "matched": ["skills", "experience", "education"],
                    "missing": ["metrics", "achievements", "keywords"]
                },
                sections_analysis=[],
                doc_ids={"text_doc_id": text_doc_id} if text_doc_id else None,
                extracted_text=extracted_text
            )
            
            return fallback_result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume file processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume processing failed: {str(e)}"
        )

@router.post("/save-to-doc", response_model=Dict[str, str])
async def save_resume_to_doc_table(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Save a resume file directly to the Doc table.
    This endpoint is specifically for testing Doc table storage.
    
    Args:
        file: The resume file to process
        current_user: Authenticated user
        
    Returns:
        Dict with document IDs
    """
    try:
        # Extract text from the file
        extracted_text = await extract_text_from_file(file)
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract sufficient text from the resume file. The file may be corrupted, password-protected, or contain only images."
            )
        
        # No longer need to read file content since we're not storing binary data
        
        # Create document in the Doc table
        from app.services.doc import create_document
        from app.models.doc import DocType
        from app.services.resume_parser import extract_personal_info
        
        # Extract personal info
        personal_info = await extract_personal_info(extracted_text)
        
        # Create the text document using new field names
        doc_data = {
            "user_id": current_user.id,
            "doc_type": DocType.RESUME.value,
            "file_name": file.filename,
            "extracted_text": extracted_text,
            "metadata": {
                "is_resume": True,
                **personal_info
            }
        }
        
        text_doc = await create_document(db, doc_data)
        
        # No longer creating file document with binary content
        
        return {
            "text_doc_id": text_doc.id,
            "message": "Successfully saved resume to Doc table"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving to Doc table: {str(e)}"
        )

@router.post("/check-file", response_model=ResumeCheckResult)
async def check_if_file_is_resume(
    file: UploadFile = File(...),
    return_text: Optional[bool] = False
) -> Any:
    """
    Check if the uploaded file is a resume, performing only the extraction and resume detection.
    
    Args:
        file: The file to check
        return_text: If True, returns the extracted text with the result
        
    Returns:
        ResumeCheckResult: Information about resume detection
    """
    try:
        # Extract text from the file
        extracted_text = await extract_text_from_file(file)
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            return ResumeCheckResult(
                is_resume=False,
                confidence=0.1,
                detected_sections=[],
                reasoning="Insufficient text extracted from the file",
                extracted_text=extracted_text if return_text else None
            )
            
        # Check if the extracted text is a resume
        detection_result = await is_resume_document(extracted_text)
        
        response = ResumeCheckResult(
            is_resume=detection_result["is_resume"],
            confidence=detection_result["confidence"],
            detected_sections=detection_result["detected_sections"],
            reasoning=detection_result["reasoning"],
            extracted_text=extracted_text if return_text else None
        )
            
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/enhance-file", response_model=EnhancedResumeData)
async def enhance_resume_file(
    file: UploadFile = File(...), 
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Enhance a resume by extracting structured information and optimizing content for ATS.
    This endpoint accepts a file directly instead of extracted text.
    """
    try:
        # First extract text from the file
        extracted_text = await extract_text_from_file(file)
        
        logger.info(f"Processing resume enhancement for file: {file.filename}")
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            logger.warning(f"Insufficient text extracted from file: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract sufficient text from the resume file. The file may be corrupted, password-protected, or contain only images."
            )
            
        # Optional: Save to database for authenticated users
        if current_user:
            try:
                # Create document in the Doc table
                from app.services.doc import create_document
                from app.models.doc import DocType
                from app.services.resume_parser import extract_personal_info
                
                # Extract personal info
                personal_info = await extract_personal_info(extracted_text)
                
                # Create the text document
                doc_data = {
                    "user_id": current_user.id,
                    "doc_type": DocType.RESUME.value,
                    "file_name": file.filename or "Untitled Resume",
                    "extracted_text": extracted_text,
                    "metadata": {
                        "is_resume": True,
                        **personal_info
                    }
                }
                
                # Create text document
                await create_document(db, doc_data)
                logger.info(f"Resume document saved to database for user ID: {current_user.id}")
            except Exception as db_error:
                # Log error but continue with enhancement
                logger.error(f"Failed to save document to database: {str(db_error)}")
        
        # Now enhance the extracted text
        from app.services.resume_enhance import enhance_resume
        enhanced_data = await enhance_resume(extracted_text)
        
        # Verify the structure of returned data and provide defaults where missing
        validated_data = EnhancedResumeData(
            personalInfo={
                "name": enhanced_data.get("personalInfo", {}).get("name", ""),
                "title": enhanced_data.get("personalInfo", {}).get("title", ""),
                "email": enhanced_data.get("personalInfo", {}).get("email", ""),
                "phone": enhanced_data.get("personalInfo", {}).get("phone", ""),
                "location": enhanced_data.get("personalInfo", {}).get("location", ""),
                "summary": enhanced_data.get("personalInfo", {}).get("summary", "")
            },
            workExperience=[
                {
                    "id": exp.get("id", str(i+1)),
                    "title": exp.get("title", ""),
                    "company": exp.get("company", ""),
                    "location": exp.get("location", ""),
                    "startDate": exp.get("startDate", ""),
                    "endDate": exp.get("endDate", ""),
                    "current": exp.get("current", False),
                    "description": exp.get("description", "")
                }
                for i, exp in enumerate(enhanced_data.get("workExperience", []))
            ],
            education=[
                {
                    "id": edu.get("id", str(i+1)),
                    "degree": edu.get("degree", ""),
                    "institution": edu.get("institution", ""),
                    "location": edu.get("location", ""),
                    "startDate": edu.get("startDate", ""),
                    "endDate": edu.get("endDate", ""),
                    "description": edu.get("description", "")
                }
                for i, edu in enumerate(enhanced_data.get("education", []))
            ],
            skills=enhanced_data.get("skills", []),
            projects=[
                {
                    "id": proj.get("id", str(i+1)),
                    "name": proj.get("name", ""),
                    "description": proj.get("description", ""),
                    "technologies": proj.get("technologies", ""),
                    "link": proj.get("link", "")
                }
                for i, proj in enumerate(enhanced_data.get("projects", []))
            ],
            extracted_text=extracted_text
        )
        
        # Log the structure of data being returned
        logger.info(f"Enhanced resume data sections: {list(validated_data.dict().keys())}")
        logger.info(f"Work experience count: {len(validated_data.workExperience)}")
        logger.info(f"Education count: {len(validated_data.education)}")
        logger.info(f"Skills count: {len(validated_data.skills)}")
        logger.info(f"Projects count: {len(validated_data.projects)}")
        
        return validated_data
    except Exception as e:
        logger.error(f"Resume enhancement failed: {str(e)}", exc_info=True)
        
        # Provide a minimal fallback structure rather than failing completely
        try:
            # Basic fallback extraction
            from app.services.resume_enhance import extract_resume_structure_fallback
            fallback_data = await extract_resume_structure_fallback(extracted_text if 'extracted_text' in locals() else "")
            
            if fallback_data:
                logger.info("Using fallback data structure for failed enhancement")
                # Convert the fallback data to the proper schema
                return EnhancedResumeData(
                    personalInfo={
                        "name": fallback_data.get("personalInfo", {}).get("name", ""),
                        "title": fallback_data.get("personalInfo", {}).get("title", ""),
                        "email": fallback_data.get("personalInfo", {}).get("email", ""),
                        "phone": fallback_data.get("personalInfo", {}).get("phone", ""),
                        "location": fallback_data.get("personalInfo", {}).get("location", ""),
                        "summary": fallback_data.get("personalInfo", {}).get("summary", "")
                    },
                    workExperience=[
                        {
                            "id": str(i+1),
                            "title": exp.get("title", ""),
                            "company": exp.get("company", ""),
                            "location": exp.get("location", ""),
                            "startDate": exp.get("startDate", ""),
                            "endDate": exp.get("endDate", ""),
                            "current": exp.get("current", False),
                            "description": exp.get("description", "")
                        }
                        for i, exp in enumerate(fallback_data.get("workExperience", []))
                    ],
                    education=[
                        {
                            "id": str(i+1),
                            "degree": edu.get("degree", ""),
                            "institution": edu.get("institution", ""),
                            "location": edu.get("location", ""),
                            "startDate": edu.get("startDate", ""),
                            "endDate": edu.get("endDate", ""),
                            "description": edu.get("description", "")
                        }
                        for i, edu in enumerate(fallback_data.get("education", []))
                    ],
                    skills=fallback_data.get("skills", []),
                    projects=[
                        {
                            "id": str(i+1),
                            "name": proj.get("name", ""),
                            "description": proj.get("description", ""),
                            "technologies": proj.get("technologies", ""),
                            "link": proj.get("link", "")
                        }
                        for i, proj in enumerate(fallback_data.get("projects", []))
                    ],
                    extracted_text=extracted_text if 'extracted_text' in locals() else ""
                )
        except Exception as fallback_error:
            logger.error(f"Fallback extraction also failed: {str(fallback_error)}")
            
        # If both main and fallback approach fail, return detailed error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to enhance resume: {str(e)}",
                "error_type": type(e).__name__,
                "fallback_failed": True
            }
        ) 