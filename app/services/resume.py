from sqlalchemy.orm import Session
import google.generativeai as genai
from typing import Optional, List, Dict, Any, Tuple
import json

from app.core.config import settings
from app.models.resume import Resume, JobDescription, ResumeAnalysis, ResumeFile
from app.schemas.resume import AIAnalysisResult, Suggestion, KeywordMatch

genai.configure(api_key=settings.GOOGLE_AI_API_KEY)

async def is_resume_document(text: str) -> bool:
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)

        prompt = f"""You are a document classifier specializing in resume identification. 
Analyze the following text and determine if it is a resume/CV document.

Look for key resume elements:
- Contact information 
- Work experience/professional history
- Education/qualifications
- Skills section
- Career objective or summary

Answer with ONLY "true" if this is a resume/CV or "false" if it's not a resume/CV.

Text to analyze:
{text[:2000]}"""  # Only analyze first 2000 chars for efficiency

        result = await model.generate_content(prompt)
        prediction = result.text.lower().strip()

        return "true" in prediction
    except Exception as e:
        print(f"Resume detection error: {e}")
        return True

async def analyze_resume(
    resume_text: str,
    job_description: Optional[str] = None
) -> AIAnalysisResult:
    try:
        is_resume = await is_resume_document(resume_text)

        if not is_resume:
            return AIAnalysisResult(
                score=0,
                isResume=False,
                suggestions=[
                    Suggestion(
                        section="Document Type",
                        improvements=[
                            "The uploaded document doesn't appear to be a resume or CV.",
                            "Please upload a resume document for proper analysis.",
                            "A resume should include work experience, education, and skills sections."
                        ]
                    )
                ],
                keywords=KeywordMatch(
                    matched=[],
                    missing=[]
                )
            )

        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)

        prompt = f"""You are an expert ATS and resume analyzer. Analyze this resume {job_description and 'for the following job description' or 'in general'} and provide a detailed response in the following JSON format:
{{
  "score": <number between 0-100>,
  "suggestions": [
    {{
      "section": "<section name>",
      "improvements": ["<improvement 1>", "<improvement 2>", ...]
    }}
  ],
  "keywords": {{
    "matched": ["<keyword 1>", "<keyword 2>", ...],
    "missing": ["<keyword 1>", "<keyword 2>", ...]
  }}
}}

Consider:
1. ATS compatibility and keyword optimization
2. Industry-standard formatting
3. Impact metrics and quantifiable achievements
4. Professional language and clarity
5. Modern resume best practices
"""

        if job_description:
            prompt += f"\nJob Description:\n{job_description}\n"

        prompt += f"\nResume:\n{resume_text}"

        try:
            result = await model.generate_content(prompt)
            text = result.text
            
            try:
                analysis_json = json.loads(text)
                return AIAnalysisResult(
                    score=analysis_json["score"],
                    isResume=True,
                    suggestions=[
                        Suggestion(
                            section=item["section"],
                            improvements=item["improvements"]
                        ) for item in analysis_json["suggestions"]
                    ],
                    keywords=KeywordMatch(
                        matched=analysis_json["keywords"]["matched"],
                        missing=analysis_json["keywords"]["missing"]
                    )
                )
            except json.JSONDecodeError:
                prompt = f"{prompt}\n\nIMPORTANT: Your response MUST be valid JSON without any additional text before or after."
                result = await model.generate_content(prompt)
                text = result.text
                
                json_match = text[text.find("{"):text.rfind("}")+1]
                analysis_json = json.loads(json_match)
                
                return AIAnalysisResult(
                    score=analysis_json["score"],
                    isResume=True,
                    suggestions=[
                        Suggestion(
                            section=item["section"],
                            improvements=item["improvements"]
                        ) for item in analysis_json["suggestions"]
                    ],
                    keywords=KeywordMatch(
                        matched=analysis_json["keywords"]["matched"],
                        missing=analysis_json["keywords"]["missing"]
                    )
                )
        except Exception as e:
            print(f"AI analysis failed: {e}")
            return AIAnalysisResult(
                score=70,
                isResume=True,
                suggestions=[
                    Suggestion(
                        section="General",
                        improvements=[
                            "Add more quantifiable achievements",
                            "Improve formatting for better ATS compatibility",
                            "Enhance skill descriptions with specific examples"
                        ]
                    )
                ],
                keywords=KeywordMatch(
                    matched=["skills", "experience", "education"],
                    missing=["metrics", "achievements", "keywords"]
                )
            )
    except Exception as e:
        print(f"Resume analysis error: {e}")
        raise

async def suggest_improvements(
    section: str,
    content: str,
    job_description: Optional[str] = None
) -> List[str]:
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)

        prompt = f"""You are an expert resume writer. Analyze this {section} section {job_description and 'for this specific job' or ''} and provide 3-5 specific improvements.

Focus on:
1. ATS optimization
2. Impact metrics and quantifiable results
3. Industry-specific keywords
4. Action verbs and achievement focus
5. Modern resume best practices"""

        if job_description:
            prompt += f"\n\nJob Description:\n{job_description}"

        prompt += f"\n\nContent:\n{content}"

        result = await model.generate_content(prompt)
        text = result.text
        
        improvements = []
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.lower().startswith(("here", "suggestion", "improve")):
                if line[0].isdigit() and ". " in line:
                    line = line[line.find(".")+1:].strip()
                if line and len(line) > 5:
                    improvements.append(line)
                    
        return improvements[:5] if improvements else [
            "Add more quantifiable achievements",
            "Use stronger action verbs",
            "Include industry-specific keywords"
        ]
    except Exception as e:
        print(f"Suggestion generation error: {e}")
        return [
            "Add more quantifiable achievements",
            "Use stronger action verbs",
            "Include industry-specific keywords"
        ]

async def save_resume(db: Session, user_id: str, filename: str, content: str) -> Resume:
    is_resume_doc = await is_resume_document(content)
    
    resume = Resume(
        user_id=user_id,
        filename=filename,
        content=content,
        is_resume=is_resume_doc
    )
    
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    return resume

async def save_job_description(db: Session, user_id: str, title: str, content: str, company: Optional[str] = None) -> JobDescription:
    job = JobDescription(
        user_id=user_id,
        title=title,
        company=company,
        content=content
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job

async def create_analysis(db: Session, resume_id: str, job_description_id: Optional[str] = None) -> ResumeAnalysis:
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise ValueError("Resume not found")
    
    job_description = None
    if job_description_id:
        job_description = db.query(JobDescription).filter(JobDescription.id == job_description_id).first()
        if not job_description:
            raise ValueError("Job description not found")
    
    analysis_result = await analyze_resume(
        resume.content, 
        job_description.content if job_description else None
    )
    
    analysis = ResumeAnalysis(
        resume_id=resume_id,
        job_description_id=job_description_id,
        score=analysis_result.score,
        is_resume=analysis_result.isResume,
        suggestions=[suggestion.dict() for suggestion in analysis_result.suggestions],
        keywords=analysis_result.keywords.dict()
    )
    
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    return analysis 

async def save_resume_file(db: Session, resume_id: str, filename: str, file_content: bytes, file_type: str) -> ResumeFile:
    """
    Save the original resume file to the database
    
    Args:
        db: Database session
        resume_id: ID of the associated resume document
        filename: Original filename
        file_content: Binary content of the file
        file_type: MIME type of the file
        
    Returns:
        ResumeFile object
    """
    file_size = len(file_content)
    
    resume_file = ResumeFile(
        resume_id=resume_id,
        filename=filename,
        file_content=file_content,
        file_type=file_type,
        file_size=file_size
    )
    
    db.add(resume_file)
    db.commit()
    db.refresh(resume_file)
    
    return resume_file

async def get_resume_file(db: Session, file_id: str) -> Optional[ResumeFile]:
    """
    Retrieve a resume file from the database
    
    Args:
        db: Database session
        file_id: ID of the file to retrieve
        
    Returns:
        ResumeFile object or None if not found
    """
    return db.query(ResumeFile).filter(ResumeFile.id == file_id).first()

async def save_resume_with_file(
    db: Session, 
    user_id: str, 
    filename: str, 
    text_content: str,
    file_content: bytes,
    file_type: str
) -> Tuple[Resume, ResumeFile]:
    """
    Save both the resume text content and the original file
    
    Args:
        db: Database session
        user_id: User ID
        filename: Original filename
        text_content: Extracted text from the resume
        file_content: Binary content of the file
        file_type: MIME type of the file
        
    Returns:
        Tuple of (Resume, ResumeFile)
    """
    # First save the resume text content
    is_resume_doc = await is_resume_document(text_content)
    
    resume = Resume(
        user_id=user_id,
        filename=filename,
        content=text_content,
        is_resume=is_resume_doc
    )
    
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    # Then save the original file
    resume_file = await save_resume_file(db, resume.id, filename, file_content, file_type)
    
    return resume, resume_file 