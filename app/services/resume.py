from sqlalchemy.orm import Session
import google.generativeai as genai
from typing import Optional, List, Dict, Any, Tuple
import json
import re
import uuid

from app.core.config import settings
from app.models.doc import Doc, DocType, doc_relationships
from app.schemas.resume import AIAnalysisResult, Suggestion, KeywordMatch, SectionAnalysis, ResumeAnalysisCreate
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
    try:
        # Extract personal information from the resume
        personal_info = await extract_personal_info(resume_text)
        
        # Check if valid resume
        resume_check = await is_resume_document(resume_text)
        
        if not resume_check["is_resume"]:
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
                ),
                personal_info=personal_info
            )

        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL_NAME,
            generation_config={"temperature": 0.2, "top_p": 0.8, "top_k": 40}
        )

        # First, extract key sections and perform a preliminary analysis
        sections_prompt = f"""Analyze this resume and extract the key sections with their content.
Identify these standard resume sections:
- Contact Information/Personal Details
- Professional Summary/Objective
- Work Experience/Employment History
- Education
- Skills
- Projects
- Certifications
- Languages
- Publications
- Volunteer Experience
- Awards

For each section, extract:
1. The section name
2. The specific content
3. Key strengths of this section
4. Major weaknesses or areas for improvement

Return as a clean JSON object like this:
{{
  "sections": [
    {{
      "name": "section name",
      "content": "extracted content",
      "strengths": ["strength 1", "strength 2"],
      "weaknesses": ["weakness 1", "weakness 2"]
    }}
  ]
}}

Resume:
{resume_text}"""

        try:
            sections_result = await model.generate_content(sections_prompt)
            sections_text = sections_result.text
            
            # Extract JSON from the response
            sections_json_str = re.search(r'\{.*\}', sections_text, re.DOTALL)
            if sections_json_str:
                sections_data = json.loads(sections_json_str.group(0))
            else:
                sections_data = {"sections": []}
        except Exception as e:
            print(f"Section extraction failed: {e}")
            sections_data = {"sections": []}

        # Main analysis prompt with detailed instructions
        main_prompt = f"""You are an expert ATS resume analyzer with deep experience in hiring and recruitment.
Analyze this resume {job_description and 'for the job description provided below' or 'for general job market competitiveness'}.

Your analysis should be comprehensive and focus on:
1. ATS compatibility and optimization - Will this resume pass ATS filters?
2. Content quality - Does it effectively communicate value and achievements?
3. Format and structure - Is it well-organized and professional?
4. Keyword optimization - Does it include relevant industry and role-specific terms?
5. Quantifiable achievements - Are accomplishments measurable and results-oriented?

{job_description and 'CRITICAL: Your analysis must specifically evaluate how well this resume matches the provided job description requirements and qualifications.' or ''}

Return your analysis as a JSON object with the following structure:
{{
  "score": <number between 0-100 representing overall effectiveness>,
  "suggestions": [
    {{
      "section": "<section name>",
      "improvements": ["<specific actionable improvement 1>", "<improvement 2>", ...]
    }}
  ],
  "keywords": {{
    "matched": ["<important keyword 1 found in resume>", "<keyword 2>", ...],
    "missing": ["<important keyword 1 missing from resume>", "<keyword 2>", ...]
  }},
  "ats_score": <number between 0-100 for ATS compatibility>,
  "content_score": <number between 0-100 for content quality>,
  "format_score": <number between 0-100 for formatting and structure>
}}

Base your scores on these criteria:
- ATS Score: Proper formatting, appropriate keywords, lack of tables/images/charts, standard section headings
- Content Score: Specific achievements, quantifiable results, relevant experience, focused skills
- Format Score: Clean layout, consistent formatting, appropriate length, scannable structure

Your analysis MUST be returned as valid JSON only with no additional text."""

        if job_description:
            main_prompt += f"\n\nJob Description:\n{job_description}\n"

        # Add the previously extracted sections analysis if available
        if sections_data and "sections" in sections_data and len(sections_data["sections"]) > 0:
            main_prompt += "\n\nPreliminary Section Analysis:\n" + json.dumps(sections_data, indent=2) + "\n"

        main_prompt += f"\n\nResume:\n{resume_text}"

        try:
            result = await model.generate_content(main_prompt)
            response_text = result.text
            
            try:
                # Try direct JSON parsing
                analysis_json = json.loads(response_text)
            except json.JSONDecodeError:
                # Extract JSON if there's additional text
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    analysis_json = json.loads(json_match.group(0))
                else:
                    # Retry with a stronger instruction for valid JSON
                    result = await model.generate_content(main_prompt + "\n\nIMPORTANT: Return ONLY valid JSON with no additional text.")
                    text = result.text
                    analysis_json = json.loads(re.search(r'\{.*\}', text, re.DOTALL).group(0))
            
            # Ensure all expected fields exist
            analysis_json["score"] = analysis_json.get("score", 70)
            analysis_json["suggestions"] = analysis_json.get("suggestions", [])
            analysis_json["keywords"] = analysis_json.get("keywords", {"matched": [], "missing": []})
            
            # Create the analysis result
            analysis_result = AIAnalysisResult(
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
                ),
                ats_score=analysis_json.get("ats_score"),
                content_score=analysis_json.get("content_score"),
                format_score=analysis_json.get("format_score"),
                sections_analysis=[
                    SectionAnalysis(
                        name=section.get("name"),
                        content=section.get("content"),
                        strengths=section.get("strengths", []),
                        weaknesses=section.get("weaknesses", [])
                    ) for section in sections_data.get("sections", [])
                ] if sections_data and "sections" in sections_data else None,
                personal_info=personal_info
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
                        print(f"Updated document {doc_id} with analysis results")
                except Exception as e:
                    print(f"Error updating document with analysis results: {e}")
            
            return analysis_result
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
                    ),
                    Suggestion(
                        section="Experience",
                        improvements=[
                            "Include measurable results for each role",
                            "Use more action verbs to describe responsibilities",
                            "Tailor achievements to target industry keywords"
                        ]
                    )
                ],
                keywords=KeywordMatch(
                    matched=["skills", "experience", "education"],
                    missing=["metrics", "achievements", "keywords"]
                ),
                ats_score=65,
                content_score=70,
                format_score=75,
                sections_analysis=None,
                personal_info=personal_info
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