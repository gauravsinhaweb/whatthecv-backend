from sqlalchemy.orm import Session
import google.generativeai as genai
from typing import Optional, List, Dict, Any, Tuple
import json
import re
import uuid
import logging
import traceback
from datetime import datetime

from app.core.config import settings
from app.models.doc import Doc, DocType, doc_relationships
from app.schemas.resume import AIAnalysisResult, Suggestion, KeywordMatch, SectionAnalysis, ResumeAnalysisCreate, PersonalInfo
from app.services.file import extract_text_from_file
from app.services.resume_parser import extract_personal_info
from app.services.doc import create_document

genai.configure(api_key=settings.GOOGLE_AI_API_KEY)

async def is_resume_document(text: str) -> Dict[str, Any]:
    # First do a quick heuristic check for common resume sections
    heuristic_result = check_resume_heuristics(text)
    
    # If heuristic confidence is high enough, return early
    if heuristic_result["confidence"] >= 0.85:
        return heuristic_result
    
    # Otherwise, use AI for a more thorough check
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)

        prompt = f"""You are a document classifier specializing in resume identification. 
Analyze the following text and determine if it is a resume/CV document.

Look for key resume elements:
- Contact information (email, phone, address, LinkedIn)
- Work experience/professional history with job titles, company names, dates
- Education/qualifications with institution names, degrees, graduation dates
- Skills section with technical or professional competencies
- Career objective or summary statement
- Projects, certifications, or achievements

Reply with a JSON object in this exact format:
{{
  "is_resume": true/false,
  "confidence": <float between 0 and 1>,
  "detected_sections": ["contact", "experience", "education", "skills", etc],
  "reasoning": "<brief explanation of your decision>"
}}

Text to analyze:
{text[:3000]}"""  # Increased character limit for better accuracy

        result = await model.generate_content(prompt)
        response_text = result.text
        
        # Extract JSON from the response
        json_str = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_str:
            ai_result = json.loads(json_str.group(0))
            
            # Combine AI and heuristic results
            combined_confidence = (ai_result.get("confidence", 0.5) * 0.8) + (heuristic_result["confidence"] * 0.2)
            
            return {
                "is_resume": ai_result.get("is_resume", False),
                "confidence": combined_confidence,
                "detected_sections": ai_result.get("detected_sections", []),
                "reasoning": ai_result.get("reasoning", "")
            }
    except Exception as e:
        print(f"Resume detection AI error: {e}")
        # Fall back to heuristic result if AI fails
    
    return heuristic_result

def check_resume_heuristics(text: str) -> Dict[str, Any]:
    """Use pattern matching to identify common resume elements"""
    
    text_lower = text.lower()
    detected_sections = []
    confidence_score = 0.0
    reasoning = []
    
    # Check for contact information patterns
    contact_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone
        r'linkedin\.com\/in\/[\w-]+'  # LinkedIn profile
    ]
    
    has_contact = any(re.search(pattern, text) for pattern in contact_patterns)
    if has_contact:
        detected_sections.append("contact")
        confidence_score += 0.2
        reasoning.append("Contains contact information")
    
    # Check for experience section
    experience_keywords = ["experience", "work history", "employment", "job history", "career"]
    if any(keyword in text_lower for keyword in experience_keywords):
        detected_sections.append("experience")
        confidence_score += 0.25
        reasoning.append("Contains work experience section")
    
    # Check for education section
    education_keywords = ["education", "degree", "university", "college", "school", "academic"]
    if any(keyword in text_lower for keyword in education_keywords):
        detected_sections.append("education")
        confidence_score += 0.2
        reasoning.append("Contains education section")
    
    # Check for skills section
    skills_keywords = ["skills", "competencies", "proficiencies", "abilities", "expertise"]
    if any(keyword in text_lower for keyword in skills_keywords):
        detected_sections.append("skills")
        confidence_score += 0.15
        reasoning.append("Contains skills section")
    
    # Check for typical resume structure indicators
    structure_indicators = [
        # Date patterns (both US and international formats)
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}\b',
        r'\b\d{4}-\d{2}\b',  # YYYY-MM
        r'\b\d{1,2}/\d{4}\b',  # MM/YYYY
        r'\bpresent\b',  # Current job indicator
        
        # Job titles/positions
        r'\b(senior|junior|lead|chief|director|manager|supervisor|engineer|developer|analyst|specialist|coordinator|assistant)\b'
    ]
    
    structure_score = sum(1 for pattern in structure_indicators if re.search(pattern, text_lower)) / len(structure_indicators)
    confidence_score += structure_score * 0.2
    
    if structure_score > 0.3:
        reasoning.append("Contains resume-like date formats and job titles")
    
    # Final confidence calculation
    is_resume = confidence_score >= 0.5
    
    return {
        "is_resume": is_resume,
        "confidence": min(confidence_score, 1.0),  # Cap at 1.0
        "detected_sections": detected_sections,
        "reasoning": ", ".join(reasoning)
    }

async def analyze_resume(
    resume_text: str,
    job_description: Optional[str] = None,
    doc_id: Optional[str] = None,
    db: Optional[Session] = None
) -> AIAnalysisResult:
    """
    Analyze a resume with AI and generate a complete analysis
    
    Args:
        resume_text: Text content of the resume
        job_description: Optional job description to tailor analysis
        doc_id: Optional document ID to update with analysis results
        db: Optional database session for updating document
        
    Returns:
        AIAnalysisResult: Complete analysis of the resume
    """
    # Extract personal information for the resume
    personal_info = await extract_personal_info(resume_text)
    logger = logging.getLogger(__name__)
    
    try:
        try:
            # Generate the AI analysis
            model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)
            
            # Build the analysis prompt
            prompt = f"""Analyze this resume for quality and ATS compatibility. Provide a detailed breakdown of its strengths and weaknesses.

Resume text:
{resume_text[:7000]} 

Respond with a JSON object containing:
- score (0-100): Overall quality score
- ats_score (0-100): How well optimized for Applicant Tracking Systems 
- content_score (0-100): Quality of content and achievements
- format_score (0-100): Structure and formatting quality
- suggestions: Array of {{section, improvements}} where improvements is an array of suggestion strings
- keywords: {{matched: [array of keywords found], missing: [important keywords that should be added]}}

Example response format:
{{
  "score": 75,
  "ats_score": 70,
  "content_score": 80,
  "format_score": 75,
  "suggestions": [
    {{
      "section": "Experience",
      "improvements": ["Add more quantifiable achievements", "Use stronger action verbs"] 
    }},
    {{
      "section": "Skills",
      "improvements": ["Add more technical skills", "Organize skills by category"]
    }}
  ],
  "keywords": {{
    "matched": ["project management", "agile", "leadership"],
    "missing": ["scrum", "kanban", "stakeholder management"]
  }}
}}"""

            if job_description:
                prompt += f"\n\nAlso analyze how well the resume matches this job description:\n{job_description[:3000]}"
            
            # Generate the analysis
            result = model.generate_content(prompt)
            text = result.text
            
            # Extract the JSON part
            start_index = text.find('{')
            end_index = text.rfind('}') + 1
            if start_index >= 0 and end_index > start_index:
                json_text = text[start_index:end_index]
                # Parse the JSON
                analysis_json = json.loads(json_text)
            else:
                raise ValueError("Failed to extract JSON from the response")
            
            # Section extraction
            section_prompt = f"""Extract the major sections from this resume and provide an analysis of each section.

Resume text:
{resume_text[:7000]}

Respond with JSON:
{{
  "sections": [
    {{
      "name": "Experience",
      "content": "extracted content...",
      "strengths": ["strength 1", "strength 2"],
      "weaknesses": ["weakness 1", "weakness 2"]
    }},
    {{
      "name": "Education",
      "content": "extracted content...",
      "strengths": ["strength 1"],
      "weaknesses": ["weakness 1"]
    }}
  ]
}}"""
            
            try:
                section_result = model.generate_content(section_prompt)
                sections_text = section_result.text
                
                # Extract the JSON part
                start_index = sections_text.find('{')
                end_index = sections_text.rfind('}') + 1
                if start_index >= 0 and end_index > start_index:
                    sections_json = sections_text[start_index:end_index]
                    # Parse the JSON
                    sections_data = json.loads(sections_json)
                else:
                    sections_data = None
            except Exception as e:
                logger.error(f"Section extraction failed: {e}")
                sections_data = None
            
            # Ensure all required fields are present
            analysis_json["score"] = analysis_json.get("score", 70)
            analysis_json["suggestions"] = analysis_json.get("suggestions", [])
            analysis_json["keywords"] = analysis_json.get("keywords", {"matched": [], "missing": []})
            
            # Convert Suggestion and KeywordMatch objects to dictionaries for AIAnalysisResult
            suggestions_list = []
            for item in analysis_json["suggestions"]:
                suggestions_list.append({
                    "section": item["section"],
                    "improvements": item["improvements"]
                })
                
            keywords_dict = {
                "matched": analysis_json["keywords"]["matched"],
                "missing": analysis_json["keywords"]["missing"]
            }
            
            sections_analysis_list = None
            if sections_data and "sections" in sections_data:
                sections_analysis_list = []
                for section in sections_data["sections"]:
                    sections_analysis_list.append({
                        "name": section.get("name", ""),
                        "content": section.get("content", ""),
                        "strengths": section.get("strengths", []),
                        "weaknesses": section.get("weaknesses", [])
                    })
            
            # Create the analysis result using dictionaries instead of model objects
            analysis_result = AIAnalysisResult(
                score=analysis_json["score"],
                ats_score=analysis_json.get("ats_score"),
                content_score=analysis_json.get("content_score"),
                format_score=analysis_json.get("format_score"),
                suggestions=suggestions_list,
                keywords=keywords_dict,
                sections_analysis=sections_analysis_list,
                extracted_text=resume_text
            )
            
            # If doc_id is provided, update the document with analysis results
            if doc_id and db:
                try:
                    from app.models.doc import Doc
                    
                    # Get the document
                    doc = db.query(Doc).filter(Doc.id == doc_id).first()
                    if doc:
                        # Update metadata with analysis results
                        if not doc.meta_data:
                            doc.meta_data = {}
                        
                        # Add analysis results to metadata
                        doc.meta_data.update({
                            "analysis_score": analysis_json["score"],
                            "ats_score": analysis_json.get("ats_score"),
                            "content_score": analysis_json.get("content_score"),
                            "format_score": analysis_json.get("format_score"),
                            "keywords_matched": analysis_json["keywords"]["matched"],
                            "keywords_missing": analysis_json["keywords"]["missing"],
                        })
                        
                        # Update the database
                        db.commit()
                        logger.info(f"Updated document {doc_id} with analysis results")
                except Exception as e:
                    logger.error(f"Error updating document with analysis results: {e}")
            
            return analysis_result
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Create a fallback analysis result using dictionaries
            return AIAnalysisResult(
                score=70,
                ats_score=65,
                content_score=70,
                format_score=75,
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
                sections_analysis=None,
                extracted_text=resume_text
            )
    except Exception as e:
        logger.error(f"Resume analysis error: {e}")
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

async def save_resume(db: Session, user_id: Optional[str], filename: str, content: str) -> Doc:
    is_resume_doc = await is_resume_document(content)
    
    # Extract personal information
    personal_info = await extract_personal_info(content)
    
    # Create a Doc object instead of Resume
    doc_data = {
        "user_id": user_id,
        "doc_type": DocType.RESUME.value,
        "file_name": filename,
        "extracted_text": content,
        "metadata": {
            "is_resume": is_resume_doc.get("is_resume", False),
            "confidence": is_resume_doc.get("confidence", 0),
            "detected_sections": is_resume_doc.get("detected_sections", []),
            **personal_info
        }
    }
    
    doc = await create_document(db, doc_data)
    return doc

async def save_job_description(db: Session, user_id: str, title: str, content: str, company: Optional[str] = None) -> Doc:
    # Create a Doc object for job description
    doc_data = {
        "user_id": user_id,
        "doc_type": DocType.JOB_DESCRIPTION.value,
        "file_name": title,
        "extracted_text": content,
        "metadata": {
            "company": company
        }
    }
    
    doc = await create_document(db, doc_data)
    return doc

async def create_analysis(db: Session, resume_id: str, job_description_id: Optional[str] = None) -> Doc:
    # Get the resume document
    resume = db.query(Doc).filter(Doc.id == resume_id).first()
    if not resume:
        raise ValueError("Resume document not found")
    
    job_description = None
    if job_description_id:
        job_description = db.query(Doc).filter(Doc.id == job_description_id).first()
        if not job_description:
            raise ValueError("Job description document not found")
    
    analysis_result = await analyze_resume(
        resume.extracted_text, 
        job_description.extracted_text if job_description else None
    )
    
    # Create a new analysis document
    analysis_doc_data = {
        "user_id": resume.user_id,
        "doc_type": DocType.ANALYSIS.value,
        "file_name": f"Analysis of {resume.file_name}",
        "extracted_text": "",  # Analysis doesn't have text content
        "metadata": {
            "score": analysis_result.score,
            "is_resume": analysis_result.isResume,
            "suggestions": [suggestion.dict() if hasattr(suggestion, 'dict') else suggestion.model_dump() for suggestion in analysis_result.suggestions],
            "keywords": analysis_result.keywords.dict() if hasattr(analysis_result.keywords, 'dict') else analysis_result.keywords.model_dump()
        }
    }
    
    analysis_doc = await create_document(db, analysis_doc_data)
    
    # Create relationship between resume and analysis
    db.execute(
        doc_relationships.insert().values(
            parent_id=resume_id,
            child_id=analysis_doc.id,
            relationship_type="ANALYSIS"
        )
    )
    
    # Create relationship between job description and analysis if provided
    if job_description_id:
        db.execute(
            doc_relationships.insert().values(
                parent_id=job_description_id,
                child_id=analysis_doc.id,
                relationship_type="ANALYSIS"
            )
        )
    
    db.commit()
    return analysis_doc 