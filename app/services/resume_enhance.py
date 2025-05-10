import google.generativeai as genai
from typing import Dict, List, Any, Optional, BinaryIO, Union
import json
import re
import logging
import os
import aiohttp
import base64
from dateutil import parser as date_parser
from app.services.resume_parser import extract_complete_resume_structure, extract_name_and_position

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Use settings from app.core.config instead of environment variables directly
GEMINI_API_KEY = settings.GOOGLE_AI_API_KEY
GEMINI_MODEL_NAME = settings.GEMINI_MODEL_NAME
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"

# Only configure Google AI if an API key is provided
has_google_ai = False
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        has_google_ai = True
        logger.info(f"Google AI configured successfully with model: {GEMINI_MODEL_NAME}")
    else:
        logger.warning("Google AI API key is not set, resume enhancement will use fallback mode")
except Exception as e:
    logger.error(f"Failed to configure Google AI: {str(e)}")

def use_fallback_processor() -> bool:
    """
    Determine if we should use the fallback processor instead of Gemini API.
    
    Returns:
        True if we should use fallback, False if we should try Gemini API
    """
    # If the API key is not configured, use fallback
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
        logger.warning("No Gemini API key configured, using fallback processor")
        return True
        
    # If we failed to configure the Google AI SDK, use fallback
    if not has_google_ai:
        logger.warning("Google AI SDK not properly configured, using fallback processor")
        return True
        
    # Otherwise, try to use the Gemini API
    return False

async def enhance_resume(resume_content: Union[str, bytes]) -> Dict[str, Any]:
    """
    Enhance a resume by extracting structured information and
    improving content for ATS optimization using Gemini AI.
    
    Args:
        resume_content: Raw text or binary content of the resume
        
    Returns:
        Dict containing enhanced resume data
    """
    try:
        # Handle binary content if provided
        resume_text = resume_content
        if isinstance(resume_content, bytes):
            try:
                resume_text = resume_content.decode('utf-8')
                logger.info("Successfully decoded binary content as UTF-8")
            except UnicodeDecodeError:
                # If not UTF-8, use a fallback encoding or handle as binary
                try:
                    resume_text = resume_content.decode('latin-1')
                    logger.info("Successfully decoded binary content as latin-1")
                except:
                    logger.error("Could not decode binary content, treating as empty")
                    resume_text = ""
        
        # First extract structured data using our parsing logic
        extracted_data = await extract_complete_resume_structure(resume_text)
        
        logger.info(f"Initial extraction completed with {len(extracted_data.get('workExperience', []))} work experiences, "
                   f"{len(extracted_data.get('education', []))} education entries, "
                   f"{len(extracted_data.get('skills', []))} skills")
        
        # Check if we should use the fallback processor
        if use_fallback_processor():
            logger.info("Using fallback processor for resume enhancement")
            return await extract_resume_structure_fallback(resume_text)
        
        # Process sections in parallel with dedicated prompts
        enhanced_resume = {}
        
        # Process personal info first - this is critical for correct identification
        personal_info = await enhance_personal_info(resume_text, extracted_data.get("personalInfo", {}))
        enhanced_resume["personalInfo"] = personal_info
        
        # Process work experience with dedicated prompt
        work_experience = await enhance_work_experience(resume_text, extracted_data.get("workExperience", []))
        enhanced_resume["workExperience"] = work_experience
        
        # Process education with dedicated prompt
        education = await enhance_education(resume_text, extracted_data.get("education", []))
        enhanced_resume["education"] = education
        
        # Process skills with dedicated prompt
        skills = await enhance_skills(resume_text, extracted_data.get("skills", []))
        enhanced_resume["skills"] = skills
        
        # Process projects with dedicated prompt
        projects = await enhance_projects(resume_text, extracted_data.get("projects", []))
        enhanced_resume["projects"] = projects
        
        logger.info(f"Resume enhancement completed successfully with {len(enhanced_resume.get('workExperience', []))} work experiences, "
                   f"{len(enhanced_resume.get('education', []))} education entries, "
                   f"{len(enhanced_resume.get('skills', []))} skills")
        
        # Format the response to match the desired structure
        formatted_response = format_response(enhanced_resume)
        
        return formatted_response
        
    except Exception as e:
        logger.error(f"Error in resume enhancement: {str(e)}", exc_info=True)
        # Fall back to basic extraction if enhancement fails
        return await extract_resume_structure_fallback(resume_text)

def format_response(enhanced_resume: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format the enhanced resume data to match the desired JSON structure.
    
    Args:
        enhanced_resume: The enhanced resume data
        
    Returns:
        Properly formatted resume data
    """
    formatted = {}
    
    # Format personal info
    personal_info = enhanced_resume.get("personalInfo", {})
    formatted["personalInfo"] = {
        "name": personal_info.get("name", ""),
        "position": personal_info.get("position", ""),
        "email": personal_info.get("email", ""),
        "phone": personal_info.get("phone", ""),
        "location": personal_info.get("location", ""),
        "summary": personal_info.get("summary", ""),
        "profilePicture": personal_info.get("profilePicture")
    }
    
    # Format work experience
    formatted["workExperience"] = []
    for i, exp in enumerate(enhanced_resume.get("workExperience", [])):
        formatted_exp = {
            "id": exp.get("id", f"work-{i+1}"),
            "position": exp.get("position", ""),
            "company": exp.get("company", ""),
            "location": exp.get("location", ""),
            "startDate": exp.get("startDate", ""),
            "endDate": exp.get("endDate", ""),
            "current": exp.get("current", False),
            "description": exp.get("description", "")
        }
        formatted["workExperience"].append(formatted_exp)
    
    # Format education
    formatted["education"] = []
    for i, edu in enumerate(enhanced_resume.get("education", [])):
        formatted_edu = {
            "id": edu.get("id", f"edu-{i+1}"),
            "degree": edu.get("degree", ""),
            "institution": edu.get("institution", ""),
            "location": edu.get("location", ""),
            "startDate": edu.get("startDate", ""),
            "endDate": edu.get("endDate", ""),
            "description": edu.get("description", "")
        }
        formatted["education"].append(formatted_edu)
    
    # Format skills
    formatted["skills"] = enhanced_resume.get("skills", [])
    
    # Format projects
    formatted["projects"] = []
    for i, proj in enumerate(enhanced_resume.get("projects", [])):
        # Convert technologies to string if it's a list
        technologies = proj.get("technologies", "")
        if isinstance(technologies, list):
            technologies = ", ".join(technologies)
        elif technologies is None:
            technologies = ""
            
        # Ensure link is a string, not None
        link = proj.get("link", "")
        if link is None:
            link = ""
            
        formatted_proj = {
            "id": proj.get("id", f"proj-{i+1}"),
            "name": proj.get("name", ""),
            "description": proj.get("description", ""),
            "technologies": technologies,
            "link": link
        }
        formatted["projects"].append(formatted_proj)
    
    return formatted

async def enhance_personal_info(resume_text: str, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance personal information with a focused Gemini prompt.
    
    Args:
        resume_text: The full resume text
        extracted_info: Previously extracted personal info
        
    Returns:
        Enhanced personal info dictionary
    """
    # Start with the extracted data
    personal_info = extracted_info.copy()
    
    # Create a focused prompt for personal info
    prompt = f"""
    Extract and enhance the following personal information from this resume text for optimal ATS compatibility:
    
    1. Full Name (first and last name only, no job titles or credentials)
    2. Position/Job Title (e.g., "Frontend Engineer", "Product Manager")
    3. Email Address
    4. Phone Number (in standard format)
    5. Location (city, state/country)
    6. Professional Summary (concise paragraph highlighting key qualifications)
    
    Resume Text:
    {resume_text[:2000]}  # Use first 2000 chars as personal info is usually at the top
    
    Return only clean, formatted data values without labels or explanations.
    Format the output as a JSON object with these exact keys: name, position, email, phone, location, summary.
    Ensure each field contains only the specific information requested with no additional text or labels.
    For any fields not found, use empty strings.
    """
    
    try:
        # Call Gemini API for improved extraction
        gemini_response = await call_gemini_api(prompt)
        
        # Extract JSON from the response
        ai_personal_info = extract_json_from_text(gemini_response)
        
        if ai_personal_info and isinstance(ai_personal_info, dict):
            # Process and validate each field
            # Name: Clean and separate from position if needed
            if ai_personal_info.get("name"):
                name = ai_personal_info["name"]
                position = ai_personal_info.get("position", personal_info.get("position", personal_info.get("title", "")))
                
                # Use specialized function to separate name from position
                clean_name, position = await extract_name_and_position(name, position)
                personal_info["name"] = clean_name
                personal_info["position"] = position
            
            # Email: Validate and use
            if ai_personal_info.get("email") and "@" in ai_personal_info["email"]:
                personal_info["email"] = ai_personal_info["email"]
            
            # Phone: Format consistently
            if ai_personal_info.get("phone"):
                personal_info["phone"] = format_phone_number(ai_personal_info["phone"])
            
            # Location: Clean and format
            if ai_personal_info.get("location"):
                personal_info["location"] = ai_personal_info["location"]
            
            # Summary: Enhance with AI insights
            if ai_personal_info.get("summary"):
                personal_info["summary"] = ai_personal_info["summary"]
        
        # Ensure all required fields exist
        for field in ["name", "position", "email", "phone", "location", "summary"]:
            if field not in personal_info or not personal_info[field]:
                personal_info[field] = ""
        
        # Add a placeholder for profilePicture as required by the response schema
        personal_info["profilePicture"] = None
                
        return personal_info
    
    except Exception as e:
        logger.error(f"Error enhancing personal info: {str(e)}", exc_info=True)
        # Return the original extracted data with basic field validation
        for field in ["name", "position", "email", "phone", "location", "summary", "profilePicture"]:
            if field not in personal_info:
                personal_info[field] = "" if field != "profilePicture" else None
        
        return personal_info

async def enhance_work_experience(resume_text: str, extracted_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance work experience entries with a dedicated Gemini prompt.
    
    Args:
        resume_text: The full resume text
        extracted_jobs: Previously extracted work experience entries
        
    Returns:
        Enhanced work experience list
    """
    # If we don't have any extracted jobs, try to find work experience section directly
    if not extracted_jobs:
        # Extract work experience section from resume
        work_section_prompt = f"""
        Extract the work experience section from this resume.
        Identify each separate job entry including job title, company, dates, and descriptions.
        
        Resume Text:
        {resume_text}
        
        Format the output as a JSON array where each job has these fields: position, company, location, startDate, endDate, description.
        Only include raw data with NO explanations. JSON format only.
        """
        
        try:
            # Call Gemini API to identify work experience
            work_section_response = await call_gemini_api(work_section_prompt)
            initial_jobs = extract_json_from_text(work_section_response)
            
            if isinstance(initial_jobs, list) and initial_jobs:
                # Add IDs to the extracted jobs
                for i, job in enumerate(initial_jobs):
                    job["id"] = f"work-{i+1}"
                extracted_jobs = initial_jobs
            
        except Exception as e:
            logger.error(f"Error extracting work experience section: {str(e)}", exc_info=True)
    
    # If we have existing jobs, enhance each one individually
    if extracted_jobs:
        enhanced_jobs = []
        
        # Process each job individually for better accuracy
        for i, job in enumerate(extracted_jobs):
            # Prepare context for this job
            job_context = f"""
            Position: {job.get('position', '')}
            Company: {job.get('company', '')}
            Location: {job.get('location', '')}
            Dates: {job.get('startDate', '')} to {job.get('endDate', '')}
            Description: {job.get('description', '')}
            """
            
            # Create a focused prompt specifically for enhancing this job
            prompt = f"""
            Enhance the following work experience entry for optimal ATS compatibility:
            
            {job_context}
            
            Improve and extract these fields:
            1. Position: Ensure the job title is clear, standardized, and optimized for ATS
            2. Company: Format the company name properly
            3. Location: Provide city and state/country in standard format
            4. Start Date: Format as YYYY-MM
            5. End Date: Format as YYYY-MM or "Present" for current roles
            6. Description: Transform into 3-5 bullet points that:
               - Start with strong action verbs
               - Include measurable achievements with metrics when possible
               - Focus on relevant responsibilities and accomplishments
               - Are optimized for ATS keyword matching
            
            Format the output ONLY as a JSON object with these exact keys: position, company, location, startDate, endDate, current, description.
            For the description field, provide the content in HTML format using <ul> and <li> tags.
            Do not include any other text or explanations outside the JSON.
            """
            
            try:
                # Call Gemini API for improved job details
                gemini_response = await call_gemini_api(prompt)
                
                # Extract JSON from the response
                ai_job = extract_json_from_text(gemini_response)
                
                if ai_job and isinstance(ai_job, dict):
                    # Start with original job data to preserve ID
                    enhanced_job = job.copy()
                    
                    # Update job with enhanced fields
                    for field in ["position", "company", "location", "startDate", "endDate", "description"]:
                        if field in ai_job and ai_job[field]:
                            enhanced_job[field] = ai_job[field]
                    
                    # Set the "current" flag based on the end date
                    if "endDate" in ai_job:
                        enhanced_job["current"] = "present" in ai_job["endDate"].lower() or "current" in ai_job["endDate"].lower()
                
                    # Ensure all required fields exist and are properly formatted
                    if "description" in enhanced_job and enhanced_job["description"] and not enhanced_job["description"].startswith("<ul>"):
                        # Convert plain text to bullet points if needed
                        enhanced_job["description"] = format_as_bullet_points(enhanced_job["description"])
                    
                    # Ensure ID field exists
                    if "id" not in enhanced_job:
                        enhanced_job["id"] = f"work-{i+1}"
                    
                    # Add to enhanced jobs list
                    enhanced_jobs.append(enhanced_job)
                else:
                    # If AI enhancement failed, keep the original job
                    job["id"] = job.get("id", f"work-{i+1}")
                    enhanced_jobs.append(job)
                
            except Exception as e:
                logger.error(f"Error enhancing job {i+1}: {str(e)}", exc_info=True)
                # Keep the original job entry but ensure required fields
                for field in ["position", "company", "location", "startDate", "endDate", "current", "description"]:
                    if field not in job:
                        if field == "current":
                            job[field] = False
                        else:
                            job[field] = ""
                
                job["id"] = job.get("id", f"work-{i+1}")
                enhanced_jobs.append(job)
        
        return enhanced_jobs
    
    # If no jobs were found, return an empty list
    return []

async def enhance_education(resume_text: str, extracted_education: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance education entries with a dedicated Gemini prompt.
    
    Args:
        resume_text: The full resume text
        extracted_education: Previously extracted education entries
        
    Returns:
        Enhanced education list
    """
    # If we don't have any extracted education entries, try to find them directly
    if not extracted_education:
        # Extract education section from resume
        education_section_prompt = f"""
        Extract the education section from this resume.
        Identify each separate education entry including degree, institution, location, dates, and description.
        
        Resume Text:
        {resume_text}
        
        Format the output as a JSON array where each entry has these fields: degree, institution, location, startDate, endDate, description.
        Only include raw data with NO explanations. JSON format only.
        """
        
        try:
            # Call Gemini API to identify education entries
            education_section_response = await call_gemini_api(education_section_prompt)
            initial_education = extract_json_from_text(education_section_response)
            
            if isinstance(initial_education, list) and initial_education:
                # Add IDs to the extracted education entries
                for i, edu in enumerate(initial_education):
                    edu["id"] = f"edu-{i+1}"
                extracted_education = initial_education
            
        except Exception as e:
            logger.error(f"Error extracting education section: {str(e)}", exc_info=True)
    
    # If we have existing education entries, enhance each one individually
    if extracted_education:
        enhanced_education = []
        
        # Process each education entry individually
        for i, edu in enumerate(extracted_education):
            # Prepare context for this education entry
            edu_context = f"""
            Degree: {edu.get('degree', '')}
            Institution: {edu.get('institution', '')}
            Location: {edu.get('location', '')}
            Dates: {edu.get('startDate', '')} to {edu.get('endDate', '')}
            Description: {edu.get('description', '')}
            """
            
            # Create a focused prompt specifically for enhancing this education entry
            prompt = f"""
            Enhance the following education entry for optimal ATS compatibility:
            
            {edu_context}
            
            Improve and extract these fields:
            1. Degree: Use standard degree terminology (e.g., "Bachelor of Science in Computer Science")
            2. Institution: Full and proper name of the institution
            3. Location: City and state/country
            4. Start Date: Format as YYYY-MM
            5. End Date: Format as YYYY-MM or "Expected YYYY-MM" for future graduation
            6. Description: Any relevant details such as GPA, honors, relevant coursework, etc.
            
            Format the output ONLY as a JSON object with these exact keys: degree, institution, location, startDate, endDate, description.
            For the description field, provide the content in HTML format using <p> tags.
            Do not include any other text or explanations outside the JSON.
            """
            
            try:
                # Call Gemini API for improved education details
                gemini_response = await call_gemini_api(prompt)
                
                # Extract JSON from the response
                ai_edu = extract_json_from_text(gemini_response)
                
                if ai_edu and isinstance(ai_edu, dict):
                    # Start with original education data to preserve ID
                    enhanced_edu = edu.copy()
                    
                    # Update education with enhanced fields
                    for field in ["degree", "institution", "location", "startDate", "endDate", "description"]:
                        if field in ai_edu and ai_edu[field]:
                            enhanced_edu[field] = ai_edu[field]
                    
                    # Format description as HTML if it's not already
                    if "description" in enhanced_edu and enhanced_edu["description"] and not enhanced_edu["description"].startswith("<"):
                        enhanced_edu["description"] = f"<p>{enhanced_edu['description']}</p>"
                    
                    # Ensure ID field exists
                    if "id" not in enhanced_edu:
                        enhanced_edu["id"] = f"edu-{i+1}"
                    
                    # Add to enhanced education list
                    enhanced_education.append(enhanced_edu)
                else:
                    # If AI enhancement failed, keep the original education entry
                    edu["id"] = edu.get("id", f"edu-{i+1}")
                    enhanced_education.append(edu)
                
            except Exception as e:
                logger.error(f"Error enhancing education entry {i+1}: {str(e)}", exc_info=True)
                # Keep the original education entry but ensure required fields
                for field in ["degree", "institution", "location", "startDate", "endDate", "description"]:
                    if field not in edu:
                        edu[field] = ""
                
                edu["id"] = edu.get("id", f"edu-{i+1}")
                enhanced_education.append(edu)
        
        return enhanced_education
    
    # If no education entries were found, return an empty list
    return []

async def enhance_skills(resume_text: str, extracted_skills: List[str]) -> List[str]:
    """
    Enhance skills with a dedicated Gemini prompt.
    
    Args:
        resume_text: The full resume text
        extracted_skills: Previously extracted skills
        
    Returns:
        Enhanced skills list
    """
    # If we don't have any extracted skills, try to find them directly
    if not extracted_skills:
        # Extract skills section from resume
        skills_section_prompt = f"""
        Extract a comprehensive list of professional skills from this resume.
        Include technical skills, soft skills, and any relevant competencies.
        For technical skills, include programming languages, frameworks, tools, and technologies.
        
        Resume Text:
        {resume_text}
        
        Format the output as a JSON array of strings, with each string being a single skill.
        For example: ["JavaScript", "React", "Node.js", "Project Management", "Team Leadership"]
        Only include the raw JSON array with NO explanations or text before or after.
        Use proper capitalization for each skill (e.g., "JavaScript" not "javascript").
        """
        
        try:
            # Call Gemini API to identify skills
            skills_section_response = await call_gemini_api(skills_section_prompt)
            initial_skills = extract_json_from_text(skills_section_response)
            
            if isinstance(initial_skills, list) and initial_skills:
                extracted_skills = initial_skills
            
        except Exception as e:
            logger.error(f"Error extracting skills section: {str(e)}", exc_info=True)
    
    # Enhanced skills prompt (whether we found some already or not)
    prompt = f"""
    Based on this resume, extract and enhance a comprehensive list of professional skills.
    
    Resume Text:
    {resume_text}
    
    Current Skills List (may be incomplete or contain errors):
    {', '.join(extracted_skills) if extracted_skills else 'No skills extracted yet'}
    
    Guidelines:
    1. Include both technical and soft skills
    2. Use proper capitalization (e.g., "JavaScript" not "javascript")
    3. Group similar skills together
    4. Prioritize the most relevant skills for modern job markets
    5. Remove duplicates and very generic skills
    6. Use specific technology names rather than general categories
    
    Format the output as a JSON array of strings, with each string being a single skill.
    For example: ["JavaScript", "React", "Node.js", "Python", "Project Management"]
    Only include the raw JSON array with NO explanations or text before or after.
    """
    
    try:
        # Call Gemini API for improved skills
        gemini_response = await call_gemini_api(prompt)
        
        # Extract JSON from the response
        ai_skills = extract_json_from_text(gemini_response)
        
        if ai_skills and isinstance(ai_skills, list):
            # Clean up the skills
            clean_skills = []
            for skill in ai_skills:
                # Ensure it's a string
                if not isinstance(skill, str):
                    continue
                    
                # Clean up any extra whitespace or punctuation
                skill = skill.strip()
                if skill.endswith(','):
                    skill = skill[:-1]
                
                # Skip very short skills (likely not valid)
                if len(skill) < 2:
                    continue
                    
                # Skip duplicates (case-insensitive check)
                if skill.lower() not in [s.lower() for s in clean_skills]:
                    clean_skills.append(skill)
            
            return clean_skills
        
        # If AI enhancement failed, return original skills
        return extracted_skills if extracted_skills else []
        
    except Exception as e:
        logger.error(f"Error enhancing skills: {str(e)}", exc_info=True)
        # Return the original extracted skills if available
        return extracted_skills if extracted_skills else []

async def enhance_projects(resume_text: str, extracted_projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance projects with a dedicated Gemini prompt.
    
    Args:
        resume_text: The full resume text
        extracted_projects: Previously extracted projects
        
    Returns:
        Enhanced projects list
    """
    # If we don't have any extracted projects, try to find them directly
    if not extracted_projects:
        # Extract projects section from resume
        projects_section_prompt = f"""
        Extract the projects section from this resume.
        Identify each separate project including name, description, technologies used, and any links.
        
        Resume Text:
        {resume_text}
        
        Format the output as a JSON array where each entry has these fields: name, description, technologies, link.
        For the technologies field, provide a string with comma-separated values, not an array.
        For the link field, use an empty string if no link is available.
        Only include raw data with NO explanations. JSON format only.
        """
        
        try:
            # Call Gemini API to identify projects
            projects_section_response = await call_gemini_api(projects_section_prompt)
            initial_projects = extract_json_from_text(projects_section_response)
            
            if isinstance(initial_projects, list) and initial_projects:
                # Add IDs to the extracted projects
                for i, proj in enumerate(initial_projects):
                    proj["id"] = f"proj-{i+1}"
                extracted_projects = initial_projects
            
        except Exception as e:
            logger.error(f"Error extracting projects section: {str(e)}", exc_info=True)
    
    # If we have existing projects, enhance each one individually
    if extracted_projects:
        enhanced_projects = []
        
        # Process each project individually
        for i, proj in enumerate(extracted_projects):
            # Prepare context for this project
            proj_context = f"""
            Name: {proj.get('name', '')}
            Description: {proj.get('description', '')}
            Technologies: {proj.get('technologies', '')}
            Link: {proj.get('link', '')}
            """
            
            # Create a focused prompt specifically for enhancing this project
            prompt = f"""
            Enhance the following project for optimal portfolio presentation:
            
            {proj_context}
            
            Improve and extract these fields:
            1. Name: Clear and concise project name
            2. Description: 2-4 bullet points that highlight:
               - The purpose of the project
               - Your specific contributions
               - Technical challenges overcome
               - End results or impact
            3. Technologies: List the key technologies, languages, frameworks used (as a comma-separated string, not an array)
            4. Link: Project URL (GitHub, live site, etc.) if available. Use empty string if no link.
            
            Format the output ONLY as a JSON object with these exact keys: name, description, technologies, link.
            For the description field, provide the content in HTML format using <ul> and <li> tags.
            For the technologies field, provide a comma-separated string, not an array.
            For the link field, use an empty string if no link is available.
            Do not include any other text or explanations outside the JSON.
            """
            
            try:
                # Call Gemini API for improved project details
                gemini_response = await call_gemini_api(prompt)
                
                # Extract JSON from the response
                ai_proj = extract_json_from_text(gemini_response)
                
                if ai_proj and isinstance(ai_proj, dict):
                    # Start with original project data to preserve ID
                    enhanced_proj = proj.copy()
                    
                    # Update project with enhanced fields
                    for field in ["name", "description", "technologies", "link"]:
                        if field in ai_proj and ai_proj[field]:
                            enhanced_proj[field] = ai_proj[field]
                    
                    # Format description as HTML if it's not already
                    if "description" in enhanced_proj and enhanced_proj["description"] and not enhanced_proj["description"].startswith("<"):
                        enhanced_proj["description"] = format_as_bullet_points(enhanced_proj["description"])
                    
                    # Ensure technologies is a string (convert list to string if needed)
                    if "technologies" in enhanced_proj:
                        if isinstance(enhanced_proj["technologies"], list):
                            enhanced_proj["technologies"] = ", ".join(enhanced_proj["technologies"])
                        elif enhanced_proj["technologies"] is None:
                            enhanced_proj["technologies"] = ""
                    else:
                        enhanced_proj["technologies"] = ""
                    
                    # Ensure link is a string, not None
                    if "link" not in enhanced_proj or enhanced_proj["link"] is None:
                        enhanced_proj["link"] = ""
                    
                    # Ensure ID field exists
                    if "id" not in enhanced_proj:
                        enhanced_proj["id"] = f"proj-{i+1}"
                    
                    # Add to enhanced projects list
                    enhanced_projects.append(enhanced_proj)
                else:
                    # If AI enhancement failed, keep the original project
                    proj["id"] = proj.get("id", f"proj-{i+1}")
                    
                    # Ensure technologies is a string
                    if "technologies" in proj and isinstance(proj["technologies"], list):
                        proj["technologies"] = ", ".join(proj["technologies"])
                    elif "technologies" not in proj or proj["technologies"] is None:
                        proj["technologies"] = ""
                        
                    # Ensure link is a string, not None
                    if "link" not in proj or proj["link"] is None:
                        proj["link"] = ""
                        
                    enhanced_projects.append(proj)
                
            except Exception as e:
                logger.error(f"Error enhancing project {i+1}: {str(e)}", exc_info=True)
                # Keep the original project but ensure required fields
                for field in ["name", "description", "technologies", "link"]:
                    if field not in proj:
                        proj[field] = ""
                    elif field == "technologies" and isinstance(proj[field], list):
                        proj[field] = ", ".join(proj[field])
                    elif proj[field] is None:
                        proj[field] = ""
                
                proj["id"] = proj.get("id", f"proj-{i+1}")
                enhanced_projects.append(proj)
        
        return enhanced_projects
    
    # If no projects were found, return an empty list
    return []

async def call_gemini_api(prompt: str) -> str:
    """
    Call Gemini API with a text prompt
    
    Args:
        prompt: The prompt to send to Gemini
        
    Returns:
        The text response from Gemini
    """
    try:
        # If no API key is configured, log error and return empty response
        if not GEMINI_API_KEY:
            logger.error("Cannot call Gemini API: No API key configured")
            return ""
            
        # Construct the API request to Gemini
        api_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 32,
                "maxOutputTokens": 2048,
            }
        }
        
        logger.info(f"Calling Gemini API with model: {GEMINI_MODEL_NAME}")
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                response_json = await response.json()
                
                # Check for error response
                if "error" in response_json:
                    error_info = response_json["error"]
                    error_message = error_info.get("message", "Unknown error")
                    error_code = error_info.get("code", 0)
                    
                    # Log detailed error information
                    logger.error(f"Gemini API error: {error_code} - {error_message}")
                    
                    # Special handling for API key issues
                    if "API key" in error_message or error_code == 400:
                        logger.critical("API key validation failed. Please check your .env file and ensure GOOGLE_AI_API_KEY is set correctly.")
                        
                    return ""
                
                # Process successful response
                if "candidates" in response_json and response_json["candidates"]:
                    # Extract text from response
                    content = response_json["candidates"][0]["content"]
                    if "parts" in content and content["parts"]:
                        return content["parts"][0]["text"]
                
                logger.warning(f"Unexpected Gemini API response structure: {response_json}")
                return ""
                
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
        return ""

def extract_json_from_text(text: str) -> Any:
    """
    Extract JSON object from text that might contain other content
    
    Args:
        text: Text that might contain JSON
        
    Returns:
        Parsed JSON object or None if extraction fails
    """
    if not text:
        return None
        
    try:
        # First try to parse the entire text as JSON
        try:
            return json.loads(text)
        except:
            pass
        
        # Look for JSON within markdown code blocks
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        code_blocks = re.findall(code_block_pattern, text)
        
        for block in code_blocks:
            try:
                return json.loads(block)
            except:
                continue
        
        # Look for JSON with surrounding characters
        json_pattern = r"\{[\s\S]*\}"
        json_matches = re.findall(json_pattern, text)
        
        for match in json_matches:
            try:
                return json.loads(match)
            except:
                continue
        
        logger.warning(f"Could not extract JSON from text: {text[:100]}...")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting JSON: {str(e)}", exc_info=True)
        return None

def format_as_bullet_points(text: str) -> str:
    """
    Format text as HTML bullet points if it isn't already
    
    Args:
        text: The text to format
        
    Returns:
        HTML bullet point list
    """
    if not text:
        return ""
        
    # If already HTML formatted, return as is
    if text.strip().startswith("<"):
        return text
    
    # Split by newlines or bullet markers
    lines = re.split(r"\n|•|\*|-", text)
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return ""
    
    # Format as bullet points
    bullet_points = "\n".join([f"<li>{line}</li>" for line in lines])
    return f"<ul>{bullet_points}</ul>"

def format_phone_number(phone: str) -> str:
    """
    Format phone number consistently
    
    Args:
        phone: The phone number to format
        
    Returns:
        Formatted phone number
    """
    if not phone:
        return ""
    
    # Remove any non-digit characters except + for international prefix
    digits = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If it starts with +, it's international
    if digits.startswith('+'):
        return digits  # Keep international format as is
    
    # If it's a 10-digit US number
    if len(digits) == 10:
        return f"+1 {digits[:3]}-{digits[3:6]}-{digits[6:]}"
    
    # If it's already an 11-digit US number (with country code)
    if len(digits) == 11 and digits.startswith('1'):
        return f"+{digits[0]} {digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    
    # For other formats, just return the cleaned version
    return digits

async def extract_resume_structure_fallback(resume_text: str) -> Dict[str, Any]:
    """
    Fallback method to extract resume structure when enhanced methods fail
    
    Args:
        resume_text: Raw text of the resume
        
    Returns:
        Dict containing structured resume data
    """
    try:
        # Extract structure using our existing parser
        extracted_structure = await extract_complete_resume_structure(resume_text)
        
        # Process the extracted personal info
        personal_info = extracted_structure.get("personalInfo", {})
        
        # Ensure name and position are properly separated
        if "name" in personal_info:
            name = personal_info["name"]
            position = personal_info.get("position", personal_info.get("title", ""))
            
            clean_name, position = await extract_name_and_position(name, position)
            personal_info["name"] = clean_name
            personal_info["position"] = position
            
            # Remove title field if present (we're standardizing on position)
            if "title" in personal_info:
                del personal_info["title"]
        
        # Ensure all required personal info fields exist
        for field in ["name", "position", "email", "phone", "location", "summary"]:
            if field not in personal_info or not personal_info[field]:
                personal_info[field] = ""
        
        # Add profilePicture field
        personal_info["profilePicture"] = None
        
        # Process work experience
        work_experience = extracted_structure.get("workExperience", [])
        for i, job in enumerate(work_experience):
            # Ensure ID exists
            if "id" not in job:
                job["id"] = f"work-{i+1}"
            
            # Change title to position if needed
            if "title" in job and ("position" not in job or not job["position"]):
                job["position"] = job["title"]
                del job["title"]
            
            # Ensure all required fields exist
            for field in ["position", "company", "location", "startDate", "endDate", "description"]:
                if field not in job or not job[field]:
                    job[field] = ""
            
            # Ensure current flag exists
            if "current" not in job:
                job["current"] = False
        
        # Process education
        education = extracted_structure.get("education", [])
        for i, edu in enumerate(education):
            # Ensure ID exists
            if "id" not in edu:
                edu["id"] = f"edu-{i+1}"
            
            # Ensure all required fields exist
            for field in ["degree", "institution", "location", "startDate", "endDate", "description"]:
                if field not in edu or not edu[field]:
                    edu[field] = ""
        
        # Process skills (ensure it's a list of strings)
        skills = extracted_structure.get("skills", [])
        
        # Process projects
        projects = extracted_structure.get("projects", [])
        for i, project in enumerate(projects):
            # Ensure ID exists
            if "id" not in project:
                project["id"] = f"proj-{i+1}"
            
            # Ensure all required fields exist
            for field in ["name", "description", "technologies", "link"]:
                if field not in project or not project[field]:
                    project[field] = ""
        
        # Return the structured data
        return {
            "personalInfo": personal_info,
            "workExperience": work_experience,
            "education": education,
            "skills": skills,
            "projects": projects
        }
        
    except Exception as e:
        logger.error(f"Error in fallback extraction: {str(e)}", exc_info=True)
        
        # If all else fails, return minimal valid structure
        return {
            "personalInfo": {
                "name": "",
                "position": "",
                "email": "",
                "phone": "",
                "location": "",
                "summary": "",
                "profilePicture": None
            },
            "workExperience": [],
            "education": [],
            "skills": [],
            "projects": []
        }

def normalize_date(date_str: str) -> str:
    """
    Normalize date strings to a consistent format.
    Handles various date formats and partial dates.
    
    Args:
        date_str: Date string to normalize
        
    Returns:
        Normalized date string in YYYY-MM format or empty string if invalid
    """
    if not date_str or date_str is None or date_str.lower() in ["present", "current", "now"]:
        if date_str is None:
            return ""
        return date_str
        
    try:
        # Handle common year-only formats
        if re.match(r'^\d{4}$', date_str):
            return f"{date_str}-01"
            
        # Handle month year formats (Jan 2023, January 2023, etc)
        if re.match(r'^[a-zA-Z]{3,}\s+\d{4}$', date_str):
            parsed_date = date_parser.parse(date_str, fuzzy=True)
            return parsed_date.strftime("%Y-%m")
            
        # Parse with dateutil for more complex formats
        parsed_date = date_parser.parse(date_str, fuzzy=True)
        return parsed_date.strftime("%Y-%m")
    except (ValueError, OverflowError, AttributeError, TypeError):
        # If parsing fails, return empty string instead of the original which might be None
        return "" if date_str is None else date_str 