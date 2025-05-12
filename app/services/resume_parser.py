import re
import logging
from typing import Dict, List, Optional, Any, Tuple
import json

# Configure logging
logger = logging.getLogger(__name__)

def check_resume_heuristics(text: str) -> Dict[str, Any]:
    """
    Quickly check if text is likely a resume using heuristics
    """
    # Common resume section keywords
    resume_sections = [
        "experience", "education", "skills", "employment", "work history",
        "professional experience", "qualification", "certification", "achievement",
        "objective", "summary", "profile", "project", "language", "reference",
        "volunteer", "training", "award", "publication"
    ]
    
    # Convert to lowercase for case-insensitive matching
    lower_text = text.lower()
    
    # Count matches
    matched_sections = [section for section in resume_sections if section in lower_text]
    match_count = len(matched_sections)
    
    # Calculate confidence
    # 0-2 matches: Low confidence
    # 3-4 matches: Medium confidence
    # 5+ matches: High confidence
    if match_count >= 5:
        confidence = 0.95
    elif match_count >= 3:
        confidence = 0.75
    elif match_count >= 1:
        confidence = 0.5
    else:
        confidence = 0.25
        
    return {
        "is_resume": confidence >= 0.5,
        "confidence": confidence,
        "detected_sections": matched_sections,
        "reasoning": f"Found {match_count} common resume sections"
    }

async def extract_personal_info(text: str) -> Dict[str, Any]:
    """
    Extract personal information from a resume text
    Returns name, email, phone, address, links
    """
    if not text:
        return {
            "name": None,
            "email": None,
            "phone": None,
            "address": None,
            "links": []
        }
    
    # Default results
    result = {
        "name": None,
        "email": None,
        "phone": None,
        "address": None,
        "links": []
    }
    
    # Split into lines for line-by-line analysis
    lines = text.split('\n')
    
    # Look for email address
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    if email_match:
        result["email"] = email_match.group(0)
    
    # Look for phone number
    phone_pattern = r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        result["phone"] = phone_match.group(0)
        
    # Look for LinkedIn or other profile links
    link_pattern = r'(?:linkedin\.com|github\.com|twitter\.com|instagram\.com|facebook\.com)/\S+'
    link_matches = re.findall(link_pattern, text)
    result["links"] = link_matches
    
    # Look for name (typically in the first 10 lines, looking for capitalized words)
    name_found = False
    for i in range(min(10, len(lines))):
        line = lines[i].strip()
        # Skip empty lines and lines with common header text
        if not line or any(x in line.lower() for x in ['resume', 'cv', 'curriculum', 'vitae']):
            continue
            
        # Look for a line with 1-3 words, all capitalized
        words = line.split()
        if 1 <= len(words) <= 3:
            capitalized_words = [w for w in words if w[0].isupper()]
            if len(capitalized_words) == len(words):
                result["name"] = line
                name_found = True
                break
    
    # If we didn't find a name with the above method, try another approach
    if not name_found and len(lines) > 0:
        # Take the first non-empty line that doesn't contain email or phone
        for i in range(min(5, len(lines))):
            if (lines[i].strip() and 
                (result["email"] is None or result["email"] not in lines[i]) and
                (result["phone"] is None or result["phone"] not in lines[i])):
                result["name"] = lines[i].strip()
                break
    
    # Extract potential profile/summary section
    profile_section = None
    
    # Look for dedicated profile/summary section
    summary_patterns = ['summary', 'profile', 'objective', 'about me', 'professional summary']
    for i, line in enumerate(lines):
        if any(pattern in line.lower() for pattern in summary_patterns):
            # Found a section header, extract the section content (next few lines)
            start = i + 1
            end = start
            while end < len(lines) and end < start + 10:
                if any(pattern in lines[end].lower() for pattern in ['experience', 'education', 'skills']):
                    break  # Stop at next section header
                end += 1
            if end > start:
                profile_section = '\n'.join(lines[start:end]).strip()
                break
    
    # If no dedicated section found, take the first paragraph that's not the name/contact info
    if not profile_section:
        for i in range(min(10, len(lines))):
            email_str = result["email"] if result["email"] else ""
            phone_str = result["phone"] if result["phone"] else ""
            name_str = result["name"] if result["name"] else ""
            
            if (lines[i].strip() and 
                all((info is None or info not in lines[i].lower()) for info in [email_str, phone_str, name_str] if info)):
                # This line doesn't contain already-extracted info, might be profile
                # Collect this and following lines as a paragraph
                start = i
                end = start
                while end < len(lines) and len(lines[end].strip()) > 0 and end < start + 5:
                    end += 1
                if end - start > 1:  # Must be at least 2 lines to be considered a paragraph
                    profile_section = "\n".join(lines[start:end])
                    break
    
    # Add profile text to result
    if profile_section:
        result["profile"] = profile_section
    
    # Extract address (simple heuristic - line with location indicators)
    address_indicators = ['st', 'street', 'ave', 'avenue', 'rd', 'road', 'lane', 'drive', 'circle', 
                         'blvd', 'boulevard', 'apt', 'suite', 'unit', 'box']
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        has_address_indicator = any(f" {indicator} " in f" {line_lower} " for indicator in address_indicators)
        has_zip = bool(re.search(r'\b\d{5}(?:-\d{4})?\b', line))  # US zip code pattern
        
        if (has_address_indicator or has_zip) and len(line.strip()) > 10:
            # Skip lines that contain email or phone
            if (result["email"] and result["email"] in line) or (result["phone"] and result["phone"] in line):
                continue
            
            result["address"] = line.strip()
            break
            
    return result

async def extract_complete_resume_structure(resume_text: str) -> Dict[str, Any]:
    """
    Extract complete resume structure with advanced parsing techniques.
    This function uses a combination of regex patterns and structure analysis
    to accurately split a resume into its component sections.
    
    Args:
        resume_text: Raw text extracted from the resume
        
    Returns:
        Dict containing structured resume data with personalInfo, workExperience,
        education, skills, and projects sections
    """
    try:
        logger.info("Extracting complete resume structure with advanced parsing")
        
        # Initialize the structure
        resume_structure = {
            "personalInfo": {},
            "workExperience": [],
            "education": [],
            "skills": [],
            "projects": []
        }
        
        # Split the text into lines for processing
        lines = resume_text.split('\n')
        clean_lines = [line.strip() for line in lines if line.strip()]
        
        # Extract personal information first
        personal_info = {}
        
        # Name is typically the first line
        if clean_lines:
            name_line = clean_lines[0]
            
            # Check if the first line contains a name and title
            name_title_split = re.split(r'\s+[|-]\s+', name_line, 1)
            if len(name_title_split) > 1:
                personal_info["name"] = name_title_split[0].strip()
                personal_info["title"] = name_title_split[1].strip()
            else:
                # Just use the first line as the name
                personal_info["name"] = name_line
                
                # Try to find the title in the second line
                if len(clean_lines) > 1:
                    second_line = clean_lines[1]
                    # Check if it looks like a job title (not an email or phone)
                    if not re.search(r'@|[0-9]{3}[-.]?[0-9]{3}[-.]?[0-9]{4}', second_line):
                        personal_info["title"] = second_line
        
        # Extract email using regex
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        email_matches = re.findall(email_pattern, resume_text)
        if email_matches:
            personal_info["email"] = email_matches[0]
        
        # Extract phone number using multiple patterns
        phone_patterns = [
            r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # Standard format
            r'\+\d{1,3}\s\d{10}',  # International format with space
            r'\+\d{10,14}'  # Pure international number
        ]
        
        for pattern in phone_patterns:
            phone_matches = re.findall(pattern, resume_text)
            if phone_matches:
                personal_info["phone"] = phone_matches[0]
                break
        
        # Extract location - this is often near the top with email/phone
        location_patterns = [
            r'(?:located in|location[:\s]+|based in)\s+([A-Za-z\s]+,\s+[A-Za-z\s]+)',
            r'([A-Za-z\s]+,\s+[A-Za-z\s]+)(?:\s+\d{5})?'  # City, State/Country + optional ZIP
        ]
        
        for pattern in location_patterns:
            location_match = re.search(pattern, resume_text[:500], re.IGNORECASE)  # Only search top part
            if location_match:
                personal_info["location"] = location_match.group(1).strip()
                break
        
        # Look for LinkedIn/website/portfolio near the top
        links_pattern = r'(?:linkedin\.com|github\.com|(?:www\.)?[\w\.-]+\.\w{2,})\/[\w\.-]+'
        links_match = re.search(links_pattern, resume_text[:500])
        if links_match:
            personal_info["links"] = links_match.group(0)
        
        # Add personal info to structure
        resume_structure["personalInfo"] = personal_info
        
        # Identify major sections in the resume
        sections = identify_resume_sections(resume_text)
        
        # Extract work experience
        if "experience" in sections:
            work_exp = extract_work_experience(resume_text, sections["experience"])
            resume_structure["workExperience"] = work_exp
        
        # Extract education
        if "education" in sections:
            education = extract_education(resume_text, sections["education"])
            resume_structure["education"] = education
        
        # Extract skills
        if "skills" in sections:
            skills = extract_skills(resume_text, sections["skills"])
            resume_structure["skills"] = skills
        
        # Extract projects
        if "projects" in sections:
            projects = extract_projects(resume_text, sections["projects"])
            resume_structure["projects"] = projects
        
        logger.info(f"Successfully extracted resume structure with: " +
                  f"{len(resume_structure['workExperience'])} jobs, " +
                  f"{len(resume_structure['education'])} education entries, " +
                  f"{len(resume_structure['skills'])} skills, " + 
                  f"{len(resume_structure['projects'])} projects")
        
        return resume_structure
    
    except Exception as e:
        logger.error(f"Error extracting resume structure: {str(e)}", exc_info=True)
        return {
            "personalInfo": {},
            "workExperience": [],
            "education": [],
            "skills": [],
            "projects": []
        }

def identify_resume_sections(text: str) -> Dict[str, Tuple[int, int]]:
    """
    Identify the major sections in a resume and their start/end positions
    
    Args:
        text: Full resume text
        
    Returns:
        Dictionary mapping section types to (start, end) positions
    """
    # Define section header patterns
    section_patterns = {
        "experience": [
            r'(?:WORK|PROFESSIONAL)\s+(?:EXPERIENCE|HISTORY)',
            r'EXPERIENCE',
            r'EMPLOYMENT(?:\s+HISTORY)?'
        ],
        "education": [
            r'EDUCATION',
            r'ACADEMIC(?:\s+BACKGROUND|\s+HISTORY)?',
            r'QUALIFICATIONS'
        ],
        "skills": [
            r'(?:TECHNICAL\s+)?SKILLS',
            r'CORE\s+COMPETENCIES',
            r'TECHNOLOGIES',
            r'PROFICIENCY'
        ],
        "projects": [
            r'PROJECTS',
            r'(?:PERSONAL|KEY)\s+PROJECTS',
            r'PROJECT\s+EXPERIENCE'
        ]
    }
    
    # Initialize result
    sections = {}
    
    # Find all section headers
    section_matches = []
    
    for section_type, patterns in section_patterns.items():
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                section_matches.append((section_type, match.start(), match.group()))
    
    # Sort matches by position
    section_matches.sort(key=lambda x: x[1])
    
    # Determine section boundaries
    for i, (section_type, start_pos, _) in enumerate(section_matches):
        if i < len(section_matches) - 1:
            # End position is the start of the next section
            end_pos = section_matches[i+1][1]
        else:
            # Last section goes to the end
            end_pos = len(text)
        
        sections[section_type] = (start_pos, end_pos)
    
    return sections

def extract_work_experience(text: str, section_range: Tuple[int, int]) -> List[Dict[str, str]]:
    """
    Extract work experience entries from the resume with improved accuracy
    
    Args:
        text: Full resume text
        section_range: (start, end) positions of the work experience section
        
    Returns:
        List of work experience entries
    """
    work_experience = []
    section_text = text[section_range[0]:section_range[1]]
    
    # Skip the header line
    section_lines = section_text.split('\n')
    section_content = '\n'.join(section_lines[1:])
    
    # Try multiple strategies for job entry detection
    # First try the date/company pattern (most common)
    job_patterns = [
        # Pattern 1: Date patterns or company names at beginning of line
        r'\n(?=\d{4}|\d{1,2}/\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4}|\d{1,2}/\d{2}|\b(?:[A-Z][a-z]+\s?)+(?:LLC|Inc|Corporation|Corp|Ltd|Company|Technologies|Solutions|Media|Group|International)\b)',
        
        # Pattern 2: Job titles at beginning of line
        r'\n(?=(?:Senior|Lead|Principal|Junior|Chief|Head|Director|VP|Vice President|Manager|Engineer|Developer|Architect|Designer|Consultant|Specialist|Analyst|Associate)\b)',
        
        # Pattern 3: Bullet point lists often indicate new job sections
        r'\n(?=•|\*|-\s+)',
        
        # Pattern 4: Common company names that don't have LLC/Inc, etc.
        r'\n(?=\b(?:Google|Amazon|Microsoft|Apple|Facebook|Netflix|Twitter|Uber|Airbnb|LinkedIn|GitHub|GitLab|Salesforce)\b)'
    ]
    
    # Try each pattern and use the best result
    best_entries = []
    best_entry_count = 0
    
    for pattern in job_patterns:
        job_entries = re.split(pattern, section_content)
        
        # Filter out empty entries and too-short entries
        entries = [entry.strip() for entry in job_entries if len(entry.strip()) > 20]
        
        if len(entries) > best_entry_count:
            best_entries = entries
            best_entry_count = len(entries)
    
    # If we still don't have good entries, try simpler paragraph splitting
    if best_entry_count <= 1:
        # Look for consecutive blank lines as job separators
        job_entries = re.split(r'\n\s*\n', section_content)
        best_entries = [entry.strip() for entry in job_entries if len(entry.strip()) > 20]
    
    # Process each job entry
    for i, entry in enumerate(best_entries):
        if not entry.strip():
            continue
            
        job = {}
        job["id"] = f"work-{i+1}"
        
        # Better position and company extraction
        lines = entry.split('\n')
        
        # Try to extract position and company from the first 1-3 lines
        position_found = False
        company_found = False
        location_found = False
        dates_found = False
        
        # Position and company patterns
        position_patterns = [
            r'^((?:Senior|Lead|Principal|Junior|Chief|Head|Director|VP|Vice President|Manager|Engineer|Developer|Architect|Designer|Consultant|Specialist|Analyst|Associate)[\s\w]+)',
            r'(?:Position|Title|Role)[\s:]+([^\n]+)'
        ]
        
        company_patterns = [
            r'(?:at|with|for)\s+([A-Z][^,\n]+)',
            r'(?:Company|Employer)[\s:]+([^\n]+)',
            r'^([A-Z][a-zA-Z0-9\s&\.,]+(?:LLC|Inc|Corporation|Corp|Ltd|Company|Technologies|Solutions|Media|Group|International))'
        ]
        
        # Parse the first few lines for key information
        for idx, line in enumerate(lines[:3]):
            # Skip empty lines
            if not line.strip():
                continue
                
            # Check for position in this line
            if not position_found:
                for pattern in position_patterns:
                    position_match = re.search(pattern, line)
                    if position_match:
                        job["position"] = position_match.group(1).strip()
                        position_found = True
                        break
                        
            # Check for company in this line
            if not company_found:
                for pattern in company_patterns:
                    company_match = re.search(pattern, line)
                    if company_match:
                        job["company"] = company_match.group(1).strip()
                        company_found = True
                        break
            
            # Look for dates
            if not dates_found:
                date_match = re.search(r'(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4})\s*[-–—]\s*(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4}|Present|Current|Now)', line)
                if date_match:
                    job["startDate"] = date_match.group(1).strip()
                    job["endDate"] = date_match.group(2).strip()
                    job["current"] = "present" in date_match.group(2).lower() or "current" in date_match.group(2).lower() or "now" in date_match.group(2).lower()
                    dates_found = True
                    
                    # Often location appears after dates
                    location_match = re.search(r'[-–—]\s*([A-Z][^,\n]+(?:,\s*[A-Z]{2})?)', line)
                    if location_match:
                        job["location"] = location_match.group(1).strip()
                        location_found = True
        
        # If position/company not found in specific patterns, use first line for position, second for company
        if not position_found and len(lines) > 0:
            job["position"] = lines[0].strip()
            position_found = True
            
        if not company_found and len(lines) > 1 and position_found:
            # Check if the second line looks like a company name (starts with capital letter)
            if re.match(r'^[A-Z]', lines[1].strip()):
                job["company"] = lines[1].strip()
                company_found = True
            # Try the third line if available
            elif len(lines) > 2 and re.match(r'^[A-Z]', lines[2].strip()):
                job["company"] = lines[2].strip()
                company_found = True
        
        # Extract location if not found yet
        if not location_found:
            for line in lines[:5]:
                location_match = re.search(r'(?:Location|Based in)[\s:]+([^\n]+)', line)
                if location_match:
                    job["location"] = location_match.group(1).strip()
                    location_found = True
                    break
                    
                # Look for common location patterns (City, State)
                location_match = re.search(r'\b([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b', line)
                if location_match:
                    job["location"] = location_match.group(1).strip()
                    location_found = True
                    break
        
        # Extract date range if not found yet
        if not dates_found:
            for line in lines[:5]:
                date_match = re.search(r'(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4})\s*[-–—]\s*(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4}|Present|Current|Now)', line)
                if date_match:
                    job["startDate"] = date_match.group(1).strip()
                    job["endDate"] = date_match.group(2).strip()
                    job["current"] = "present" in date_match.group(2).lower() or "current" in date_match.group(2).lower() or "now" in date_match.group(2).lower()
                    dates_found = True
                    break
                    
                # Try alternative date formats
                date_match = re.search(r'(\d{4})\s*to\s*(\d{4}|Present|Current|Now)', line, re.IGNORECASE)
                if date_match:
                    job["startDate"] = date_match.group(1).strip()
                    job["endDate"] = date_match.group(2).strip()
                    job["current"] = "present" in date_match.group(2).lower() or "current" in date_match.group(2).lower() or "now" in date_match.group(2).lower()
                    dates_found = True
                    break
        
        # Extract description (bullet points and other content)
        description_lines = []
        description_start = 0
        
        # Find where description starts (after position, company, dates info)
        for idx, line in enumerate(lines):
            if idx > 0 and (
                line.strip().startswith('•') or 
                line.strip().startswith('-') or 
                line.strip().startswith('*') or
                re.match(r'^\d+\.\s', line.strip())
            ):
                description_start = idx
                break
                
        # If no bullet points found, use a reasonable starting point
        if description_start == 0:
            description_start = min(3, len(lines))
        
        # Extract description content
        if description_start < len(lines):
            description = extract_job_description(lines[description_start:])
            job["description"] = description
        else:
            job["description"] = ""
        
        # Ensure all required fields have values
        for field in ["position", "company", "location", "startDate", "endDate"]:
            if field not in job:
                job[field] = ""
        
        work_experience.append(job)
    
    return work_experience

def extract_job_description(description_lines: List[str]) -> str:
    """
    Extract and format job description from lines of text,
    handling bullet points and paragraphs appropriately.
    
    Args:
        description_lines: Lines of text containing the job description
        
    Returns:
        Formatted HTML description
    """
    if not description_lines:
        return ""
        
    # Check if we have bullet points
    has_bullets = any(
        line.strip().startswith(('•', '-', '*')) or 
        re.match(r'^\d+\.\s', line.strip())
        for line in description_lines
    )
    
    if has_bullets:
        # Process bullet points
        bullets = []
        current_bullet = []
        
        for line in description_lines:
            line = line.strip()
            
            # Start of a new bullet point
            if line.startswith(('•', '-', '*')) or re.match(r'^\d+\.\s', line):
                # Save previous bullet if any
                if current_bullet:
                    bullets.append(' '.join(current_bullet))
                    current_bullet = []
                
                # Clean bullet marker and start new bullet
                clean_line = re.sub(r'^[•\*\-]\s*|^\d+\.\s*', '', line)
                current_bullet.append(clean_line)
            
            # Continuation of previous bullet point (indented line)
            elif line and current_bullet:
                current_bullet.append(line)
            
            # Standalone line (not part of bullet)
            elif line:
                # Save previous bullet if any
                if current_bullet:
                    bullets.append(' '.join(current_bullet))
                    current_bullet = []
                bullets.append(line)
        
        # Add the last bullet if any
        if current_bullet:
            bullets.append(' '.join(current_bullet))
        
        # Format as HTML list
        bullets_html = [f"<li>{bullet}</li>" for bullet in bullets if bullet.strip()]
        if bullets_html:
            return f"<ul>{' '.join(bullets_html)}</ul>"
        else:
            return ""
    else:
        # Format as paragraphs
        paragraphs = []
        current_para = []
        
        for line in description_lines:
            line = line.strip()
            
            # Empty line indicates paragraph break
            if not line and current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
            elif line:
                current_para.append(line)
        
        # Add the last paragraph if any
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        # Format as HTML paragraphs
        paragraphs_html = [f"<p>{para}</p>" for para in paragraphs if para.strip()]
        return ''.join(paragraphs_html)

def extract_education(text: str, section_range: Tuple[int, int]) -> List[Dict[str, str]]:
    """
    Extract education entries from the resume with improved accuracy
    
    Args:
        text: Full resume text
        section_range: (start, end) positions of the education section
        
    Returns:
        List of education entries
    """
    education = []
    section_text = text[section_range[0]:section_range[1]]
    
    # Skip the header line
    section_lines = section_text.split('\n')
    section_content = '\n'.join(section_lines[1:])
    
    # Define common education patterns for better recognition
    degree_keywords = [
        "bachelor", "master", "phd", "doctorate", "b.s.", "m.s.", "b.a.", "m.a.",
        "b.eng", "m.eng", "b.tech", "m.tech", "b.sc", "m.sc", "mba", "llb", "llm",
        "associate", "diploma", "certificate", "certification", "degree",
        "bsc", "msc", "ba", "ma", "bs", "ms", "b.e.", "m.e.", "b.com", "m.com"
    ]
    
    institution_keywords = [
        "university", "college", "institute", "school", "academy", "polytechnic", 
        "campus", "center", "centre"
    ]
    
    # Try to identify individual education entries
    # Multiple techniques for splitting education entries
    
    # Method 1: Identify entries by degree or institution keywords
    entry_pattern = r'\n(?=(?:[A-Z][^\n,]*\b(?:' + '|'.join(degree_keywords + institution_keywords) + r')\b[^\n,]*)|(?:\b(?:' + '|'.join(degree_keywords + institution_keywords) + r')\b[^\n,]*))'
    edu_entries = re.split(entry_pattern, section_content, flags=re.IGNORECASE)
    
    # Method 2: If first method doesn't find at least 2 entries, try date-based splitting
    if len(edu_entries) < 2:
        date_pattern = r'\n(?=\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*(?:Present|Current|Now)|\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4})'
        edu_entries = re.split(date_pattern, section_content)
    
    # Method 3: If still not enough entries, try blank line separation
    if len(edu_entries) < 2:
        edu_entries = re.split(r'\n\s*\n', section_content)
    
    # Process each education entry
    for i, entry in enumerate(edu_entries):
        entry = entry.strip()
        if not entry or len(entry) < 10:  # Skip very short entries
            continue
            
        edu = {}
        edu["id"] = f"edu-{i+1}"
        
        # Split entry into lines for analysis
        lines = entry.split('\n')
        if not lines:
            continue
        
        # Initialize flags for tracking what we've found
        degree_found = False
        institution_found = False
        dates_found = False
        location_found = False
        
        # Process each line of the entry
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Try to extract degree
            if not degree_found:
                # Look for common degree patterns
                for keyword in degree_keywords:
                    if re.search(r'\b' + re.escape(keyword) + r'\b', line, re.IGNORECASE):
                        # Try to extract the full degree
                        degree_match = re.search(r'((?:B|M|Ph)(?:\.|Sc|A|S|Eng|Tech)\.?|Bachelor(?:s|\'s)?|Master(?:s|\'s)?|MBA|Ph\.?D\.?|Doctor(?:ate)?|Associate(?:s|\'s)?)[^\n,]*(?:(?:of|in|on)\s+[^\n,]+)?', line, re.IGNORECASE)
                        if degree_match:
                            degree = degree_match.group(0).strip()
                            # Clean up and standardize the degree
                            degree = re.sub(r'\s+', ' ', degree)
                            edu["degree"] = degree
                            degree_found = True
                            break
                        else:
                            # If not a specific match, just use the line containing the keyword
                            edu["degree"] = line
                            degree_found = True
                            break
            
            # Try to extract institution
            if not institution_found:
                for keyword in institution_keywords:
                    if re.search(r'\b' + re.escape(keyword) + r'\b', line, re.IGNORECASE):
                        # Try to extract the full institution name
                        # University names often start with a capital letter and include the keyword
                        institution_match = re.search(r'([A-Z][^\n,]*\b' + re.escape(keyword) + r'\b[^\n,]*)', line, re.IGNORECASE)
                        if institution_match:
                            institution = institution_match.group(0).strip()
                            # Clean up and standardize the institution
                            institution = re.sub(r'\s+', ' ', institution)
                            edu["institution"] = institution
                            institution_found = True
                            break
                        else:
                            # If not a specific match, just use the line containing the keyword
                            edu["institution"] = line
                            institution_found = True
                            break
            
            # Try to extract dates
            if not dates_found:
                # Look for date patterns (start-end)
                date_match = re.search(r'(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4})\s*[-–—]\s*(\d{1,2}/\d{2,4}|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4}|Present|Current|Now|Expected)', line, re.IGNORECASE)
                if date_match:
                    edu["startDate"] = date_match.group(1).strip()
                    edu["endDate"] = date_match.group(2).strip()
                    dates_found = True
                    
                    # Location often appears with dates
                    loc_match = re.search(r'([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})', line)
                    if loc_match:
                        edu["location"] = loc_match.group(1).strip()
                        location_found = True
            
            # Try to extract location if not found yet
            if not location_found:
                # Look for common location patterns (City, State/Country)
                loc_match = re.search(r'([A-Z][a-zA-Z\s]+,\s*[A-Z]{2}|[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)', line)
                if loc_match:
                    edu["location"] = loc_match.group(1).strip()
                    location_found = True
            
            # Extract GPA if mentioned
            gpa_match = re.search(r'GPA\s*(?:of|:)?\s*(\d+\.\d+|\d+\,\d+)', line, re.IGNORECASE)
            if gpa_match:
                if "description" not in edu:
                    edu["description"] = ""
                edu["description"] += f"<p>GPA: {gpa_match.group(1)}</p>"
        
        # If institution not found but first line looks like institution (capitalized words)
        if not institution_found and lines and re.match(r'^[A-Z]', lines[0]):
            # Check if first line doesn't have a degree keyword
            if not any(re.search(r'\b' + re.escape(keyword) + r'\b', lines[0], re.IGNORECASE) for keyword in degree_keywords):
                edu["institution"] = lines[0].strip()
        
        # If degree not found but second line might contain it
        if not degree_found and len(lines) > 1:
            second_line = lines[1].strip()
            if any(re.search(r'\b' + re.escape(keyword) + r'\b', second_line, re.IGNORECASE) for keyword in degree_keywords):
                edu["degree"] = second_line
        
        # Try to fill in gaps with educated guesses based on structure
        if not degree_found and not institution_found and lines:
            if "," in lines[0]:
                # Format might be "Institution, Location"
                parts = lines[0].split(",", 1)
                edu["institution"] = parts[0].strip()
                if not location_found and len(parts) > 1:
                    edu["location"] = parts[1].strip()
            elif " - " in lines[0]:
                # Format might be "Degree - Institution"
                parts = lines[0].split(" - ", 1)
                if any(keyword in parts[0].lower() for keyword in degree_keywords):
                    edu["degree"] = parts[0].strip()
                    if len(parts) > 1:
                        edu["institution"] = parts[1].strip()
                elif any(keyword in parts[1].lower() for keyword in degree_keywords):
                    edu["institution"] = parts[0].strip()
                    edu["degree"] = parts[1].strip()
                else:
                    # Can't determine which is which, use reasonable defaults
                    edu["institution"] = parts[0].strip()
        
        # Normalize degree values for consistency
        if "degree" in edu:
            degree = edu["degree"].lower()
            if re.search(r'\bbach|b\.?s|b\.?a|b\.?eng|b\.?tech\b', degree):
                if "science" in degree or "s" in degree:
                    edu["degree"] = "Bachelor of Science"
                elif "art" in degree or "a" in degree:
                    edu["degree"] = "Bachelor of Arts"
                elif "engineering" in degree or "eng" in degree:
                    edu["degree"] = "Bachelor of Engineering"
                elif "technology" in degree or "tech" in degree:
                    edu["degree"] = "Bachelor of Technology"
                elif "commerce" in degree or "com" in degree:
                    edu["degree"] = "Bachelor of Commerce"
                elif "business" in degree:
                    edu["degree"] = "Bachelor's Degree"
                else:
                    edu["degree"] = "Bachelor's Degree"
            elif re.search(r'\bmast|m\.?s|m\.?a|m\.?eng|m\.?tech\b', degree):
                if "science" in degree or "s" in degree:
                    edu["degree"] = "Master of Science"
                elif "art" in degree or "a" in degree:
                    edu["degree"] = "Master of Arts"
                elif "engineering" in degree or "eng" in degree:
                    edu["degree"] = "Master of Engineering"
                elif "technology" in degree or "tech" in degree:
                    edu["degree"] = "Master of Technology"
                elif "business" in degree and "admin" in degree:
                    edu["degree"] = "Master of Business Administration"
                else:
                    edu["degree"] = "Master's Degree"
            elif re.search(r'\bphd|ph\.?d|doct\b', degree):
                edu["degree"] = "Ph.D."
            elif re.search(r'\bassoc|a\.?a\b', degree):
                edu["degree"] = "Associate's Degree"
        
        # Ensure all required fields have values
        for field in ["degree", "institution", "location", "startDate", "endDate", "description"]:
            if field not in edu:
                edu[field] = ""
        
        education.append(edu)
    
    # If we still couldn't find any education entries, try a more general approach
    if not education:
        # Look for any lines that might indicate education
        for i, line in enumerate(section_lines[1:]):
            line = line.strip()
            if any(keyword in line.lower() for keyword in degree_keywords + institution_keywords):
                edu = {
                    "id": f"edu-{i+1}",
                    "degree": "",
                    "institution": line,
                    "location": "",
                    "startDate": "",
                    "endDate": "",
                    "description": ""
                }
                
                # Try to determine if this is more likely a degree or institution
                if any(keyword in line.lower() for keyword in degree_keywords):
                    edu["degree"] = line
                    edu["institution"] = ""
                
                education.append(edu)
    
    return education

def extract_skills(text: str, section_range: Tuple[int, int]) -> List[str]:
    """
    Extract skills from the resume with improved accuracy for technical and soft skills
    
    Args:
        text: Full resume text
        section_range: (start, end) positions of the skills section
        
    Returns:
        List of skills
    """
    skills = []
    section_text = text[section_range[0]:section_range[1]]
    
    # Skip the header line
    section_lines = section_text.split('\n')
    section_content = ' '.join([line.strip() for line in section_lines[1:]])
    
    # Define common skill categories with their typical terms
    technical_skills = {
        "programming_languages": [
            "python", "java", "javascript", "typescript", "c++", "c#", "ruby", 
            "php", "go", "swift", "kotlin", "rust", "scala", "perl", "r", 
            "groovy", "dart", "objective-c", "shell", "bash", "powershell",
            "haskell", "clojure", "elixir", "erlang", "fortran", "cobol"
        ],
        "web_technologies": [
            "html", "css", "sass", "less", "bootstrap", "tailwind", "material-ui",
            "responsive design", "web accessibility", "webpack", "vite", "gulp", "grunt",
            "pwa", "progressive web apps", "web components", "webassembly", "wasm"
        ],
        "frameworks_libraries": [
            "react", "angular", "vue", "svelte", "ember", "backbone", 
            "jquery", "express", "django", "flask", "spring", "rails", 
            "laravel", "symfony", "asp.net", "next.js", "nuxt.js", 
            "gatsby", "meteor", "fastapi", "nest.js", "phoenix", 
            "strapi", "electron", "flutter", "react native"
        ],
        "databases": [
            "sql", "nosql", "mysql", "postgresql", "mongodb", "sqlite", 
            "oracle", "mariadb", "ms sql server", "dynamodb", "cassandra", 
            "redis", "neo4j", "couchdb", "firebase", "elasticsearch", 
            "cosmos db", "supabase", "prisma", "typeorm", "sequelize",
            "knex", "mongoose", "graphql"
        ],
        "cloud_infrastructure": [
            "aws", "amazon web services", "azure", "google cloud", "gcp", 
            "heroku", "digitalocean", "linode", "netlify", "vercel", 
            "cloudflare", "docker", "kubernetes", "jenkins", "terraform", 
            "ansible", "chef", "puppet", "vagrant", "serverless", "ci/cd", 
            "github actions", "gitlab ci", "travis ci", "circle ci"
        ],
        "data_science": [
            "machine learning", "artificial intelligence", "ai", "data mining", 
            "data visualization", "data analysis", "statistics", "big data", 
            "pandas", "numpy", "scipy", "matplotlib", "seaborn", "scikit-learn", 
            "tensorflow", "pytorch", "keras", "jupyter", "tableau", "power bi",
            "nlp", "natural language processing", "computer vision", "deep learning"
        ],
        "testing": [
            "unit testing", "integration testing", "e2e testing", "tdd", "bdd", 
            "jest", "mocha", "chai", "jasmine", "karma", "selenium", "cypress", 
            "puppeteer", "playwright", "jmeter", "junit", "pytest", "testng", 
            "rspec", "cucumber"
        ]
    }
    
    soft_skills = [
        "problem solving", "communication", "teamwork", "leadership", 
        "time management", "critical thinking", "adaptability", "creativity", 
        "project management", "emotional intelligence", "conflict resolution", 
        "decision making", "analytical thinking", "attention to detail", 
        "organization", "collaboration", "negotiation", "mentoring", 
        "coaching", "public speaking", "presentation", "research", 
        "writing", "agile", "scrum", "kanban", "lean"
    ]
    
    # Try different delimiters for skills
    delimiters = [',', '|', '•', '·', ':', '-', '/', '\\', '  ']
    
    # Try to find the best delimiter
    for delimiter in delimiters:
        if delimiter in section_content:
            extracted_skills = [skill.strip() for skill in section_content.split(delimiter) if skill.strip()]
            if len(extracted_skills) > len(skills):
                skills = extracted_skills
    
    # If we don't have many skills yet, try to find bullet points
    if len(skills) < 3:
        # Look for bullet point lists
        bullet_pattern = r'[•\-\*]\s*([^•\-\*\n]+)'
        bullet_matches = re.findall(bullet_pattern, section_text)
        if bullet_matches:
            skills = [match.strip() for match in bullet_matches if match.strip()]
    
    # If skills list is still small, try to extract from the whole resume text
    extracted_skills = skills.copy()
    if len(extracted_skills) < 10:
        # Try to identify skills from the rest of the resume
        full_text = text.lower()
        
        # Check for technical skill keywords
        for category, terms in technical_skills.items():
            for term in terms:
                # For exact skill names, search for word boundaries
                if re.search(r'\b' + re.escape(term) + r'\b', full_text):
                    # Normalize skill name (capitalize properly)
                    if term not in [s.lower() for s in extracted_skills]:
                        if term.upper() in ["AWS", "GCP", "CSS", "HTML", "API", "SQL", "UI", "UX", "TDD", "BDD", "CI/CD"]:
                            extracted_skills.append(term.upper())
                        elif " " in term:  # multi-word terms
                            extracted_skills.append(" ".join(word.capitalize() if word.lower() not in ["of", "the", "and", "in", "on", "with", "for"] else word.lower() for word in term.split()))
                        else:
                            # Special cases for programming languages
                            language_cases = {
                                "javascript": "JavaScript",
                                "typescript": "TypeScript",
                                "python": "Python",
                                "java": "Java",
                                "c++": "C++",
                                "c#": "C#",
                                "php": "PHP",
                                "ruby": "Ruby",
                                "swift": "Swift",
                                "kotlin": "Kotlin",
                                "rust": "Rust",
                                "go": "Go"
                            }
                            if term in language_cases:
                                extracted_skills.append(language_cases[term])
                            else:
                                extracted_skills.append(term.capitalize())
        
        # Check for soft skills as well
        for skill in soft_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', full_text) and skill not in [s.lower() for s in extracted_skills]:
                # Capitalize properly for presentation
                extracted_skills.append(" ".join(word.capitalize() if word.lower() not in ["of", "the", "and", "in", "on", "with", "for"] else word.lower() for word in skill.split()))
    
    # Look for frameworks and libraries in work experience sections
    experience_section_range = None
    for section_type, range_tuple in identify_resume_sections(text).items():
        if section_type == "experience":
            experience_section_range = range_tuple
            break
    
    if experience_section_range:
        experience_text = text[experience_section_range[0]:experience_section_range[1]].lower()
        
        # Check for frameworks and technologies in experience descriptions
        for category in ["frameworks_libraries", "databases", "cloud_infrastructure"]:
            for term in technical_skills[category]:
                if re.search(r'\b' + re.escape(term) + r'\b', experience_text) and term not in [s.lower() for s in extracted_skills]:
                    if term.upper() in ["AWS", "GCP", "API"]:
                        extracted_skills.append(term.upper())
                    elif " " in term:
                        extracted_skills.append(" ".join(word.capitalize() if word.lower() not in ["of", "the", "and", "in", "on", "with", "for"] else word.lower() for word in term.split()))
                    else:
                        framework_cases = {
                            "react": "React",
                            "angular": "Angular",
                            "vue": "Vue.js",
                            "django": "Django",
                            "flask": "Flask",
                            "express": "Express.js",
                            "spring": "Spring",
                            "rails": "Ruby on Rails",
                            "jquery": "jQuery",
                            "node.js": "Node.js",
                            "next.js": "Next.js",
                            "mongodb": "MongoDB",
                            "postgresql": "PostgreSQL",
                            "mysql": "MySQL"
                        }
                        if term in framework_cases:
                            extracted_skills.append(framework_cases[term])
                        else:
                            extracted_skills.append(term.capitalize())
    
    # Deduplicate and sort
    unique_skills = []
    for skill in extracted_skills:
        if skill.lower() not in [s.lower() for s in unique_skills]:
            unique_skills.append(skill)
    
    # Sort skills: programming languages first, then frameworks, databases, etc.
    def get_skill_priority(skill):
        skill_lower = skill.lower()
        if any(lang.lower() == skill_lower for lang in technical_skills["programming_languages"]):
            return 0
        if any(framework.lower() == skill_lower for framework in technical_skills["frameworks_libraries"]):
            return 1
        if any(db.lower() == skill_lower for db in technical_skills["databases"]):
            return 2
        if any(cloud.lower() == skill_lower for cloud in technical_skills["cloud_infrastructure"]):
            return 3
        if any(web.lower() == skill_lower for web in technical_skills["web_technologies"]):
            return 4
        if any(data.lower() == skill_lower for data in technical_skills["data_science"]):
            return 5
        if any(test.lower() == skill_lower for test in technical_skills["testing"]):
            return 6
        if any(soft.lower() == skill_lower for soft in soft_skills):
            return 7
        return 8
    
    sorted_skills = sorted(unique_skills, key=get_skill_priority)
    
    return sorted_skills

def extract_projects(text: str, section_range: Tuple[int, int]) -> List[Dict[str, str]]:
    """
    Extract projects from the resume
    
    Args:
        text: Full resume text
        section_range: (start, end) positions of the projects section
        
    Returns:
        List of project entries
    """
    projects = []
    section_text = text[section_range[0]:section_range[1]]
    
    # Skip the header line
    section_lines = section_text.split('\n')
    section_content = '\n'.join(section_lines[1:])
    
    # Try to identify individual projects
    # Project names are often capitalized and followed by description
    project_entries = re.findall(r'([A-Z][A-Za-z0-9\s&\-\'\(\)]+)(?:\n|\s{2,})(.+?)(?=(?:[A-Z][A-Za-z0-9\s&\-\'\(\)]+(?:\n|\s{2,}))|$)', 
                             section_content, re.DOTALL)
    
    for i, (name, description) in enumerate(project_entries):
        project = {}
        project["id"] = f"proj-{i+1}"
        project["name"] = name.strip()
        
        desc = description.strip()
        
        # Try to extract technologies/tech stack
        tech_match = re.search(r'(?:technologies|tech stack|built with)[:\s]*([^\.]+)', desc, re.IGNORECASE)
        if tech_match:
            project["technologies"] = tech_match.group(1).strip()
            # Remove this part from the description
            desc = desc.replace(tech_match.group(0), '')
        else:
            project["technologies"] = ""
        
        # Try to extract links
        link_match = re.search(r'(https?://(?:www\.)?[a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9\.\-_~:/\?#\[\]@!\$&\'\(\)\*\+,;=]*)?)', desc)
        if link_match:
            project["link"] = link_match.group(1)
            # Remove this part from the description
            desc = desc.replace(link_match.group(1), '')
        else:
            project["link"] = ""
        
        # Format description
        if desc:
            lines = desc.split('\n')
            if any(line.strip().startswith(('•', '-', '*')) for line in lines):
                # Format as bullet list
                bullets = []
                for line in lines:
                    line = line.strip()
                    if line.startswith(('•', '-', '*')):
                        line = re.sub(r'^[•\*\-]\s*', '', line)
                        bullets.append(f"<li>{line}</li>")
                if bullets:
                    project["description"] = f"<ul>{''.join(bullets)}</ul>"
                else:
                    project["description"] = f"<p>{desc}</p>"
            else:
                # Format as paragraph
                project["description"] = f"<p>{desc}</p>"
        else:
            project["description"] = ""
        
        projects.append(project)
    
    return projects 

async def extract_name_and_position(name_text: str, position_text: str = "") -> Tuple[str, str]:
    """
    Intelligently separate a person's name from their job position
    when they appear mixed together.
    
    Args:
        name_text: Text that may contain both name and position
        position_text: Any existing position text we already have
        
    Returns:
        Tuple of (clean_name, position)
    """
    position_keywords = [
        "fullstack", "full stack", "full-stack", 
        "frontend", "front end", "front-end", 
        "backend", "back end", "back-end", 
        "software", "developer", "engineer", 
        "manager", "director", "lead", 
        "designer", "ui", "ux", 
        "data", "product", "analyst",
        "senior", "junior", "architect", 
        "devops", "ops", "web", "mobile", 
        "ios", "android", "qa", "tester",
        "cloud", "security", "administrator",
        "scientist", "specialist", "consultant",
        "programmer", "tech lead", "technical lead",
        "staff", "principal", "head of", "chief",
        "cto", "cio", "vp", "vice president"
    ]
    
    if not name_text:
        return "", position_text
    
    # Check for common separator patterns first (cleaner separation)
    common_separators = [" - ", " | ", " — ", " – ", " // ", "\\n"]
    for separator in common_separators:
        if separator in name_text:
            parts = name_text.split(separator, 1)
            if len(parts) == 2:
                # Check if the second part is likely a position
                if any(keyword in parts[1].lower() for keyword in position_keywords):
                    extracted_position = parts[1].strip()
                    clean_name = parts[0].strip()
                    
                    # Combine with existing position if needed
                    if extracted_position and position_text:
                        if extracted_position.lower() not in position_text.lower():
                            position = f"{extracted_position} {position_text}"
                        else:
                            position = position_text
                    elif extracted_position:
                        position = extracted_position
                    else:
                        position = position_text
                        
                    return clean_name, position.strip()
    
    # Parse the capitalization pattern to detect where name ends and title begins
    # Names typically have first letter of each word capitalized, with no all-caps words
    words = name_text.split()
    name_pattern_end = -1
    
    for i, word in enumerate(words):
        # Skip single-letter words like middle initials
        if len(word) == 1:
            continue
            
        # If we encounter an all-lowercase technical term, likely part of position
        if word.lower() in position_keywords and word == word.lower():
            name_pattern_end = i
            break
            
        # If we encounter a word with irregular capitalization, likely part of position
        # (e.g., "JavaScript", "DevOps", "iOS")
        if any(c.isupper() for c in word[1:]) and not word.isupper():
            if word.lower() in [k.lower() for k in position_keywords]:
                name_pattern_end = i
                break
                
        # All-uppercase words might be abbreviations in a position (e.g., "UI", "UX", "SEO")
        if word.isupper() and len(word) > 1:
            if i > 1:  # Allow for abbreviations in names, if they're at the start
                name_pattern_end = i
                break
    
    # If we found a pattern break, split accordingly
    if name_pattern_end > 0:
        clean_name = " ".join(words[:name_pattern_end])
        extracted_position = " ".join(words[name_pattern_end:])
        
        # Combine with existing position
        if extracted_position and position_text:
            if extracted_position.lower() not in position_text.lower():
                position = f"{extracted_position} {position_text}"
            else:
                position = position_text
        elif extracted_position:
            position = extracted_position
        else:
            position = position_text
            
        return clean_name, position.strip()
    
    # If no pattern break found, use the keyword approach as a fallback
    # Split the name into parts
    name_parts = name_text.split()
    clean_name_parts = []
    position_parts = []
    
    # Handle common patterns where position is appended to name
    for part in name_parts:
        # Check if this part is a position keyword
        if part.lower() in position_keywords or any(keyword in part.lower() for keyword in position_keywords):
            position_parts.append(part)
        else:
            clean_name_parts.append(part)
    
    # If we didn't extract any position parts, assume it's all name
    if not position_parts:
        # Most names are 2-3 words, so if longer, check for common position patterns
        if len(clean_name_parts) > 3:
            # Look for position patterns within the name
            full_name = " ".join(clean_name_parts)
            for keyword in position_keywords:
                keyword_index = full_name.lower().find(keyword)
                if keyword_index > 0:
                    # Split at the keyword
                    clean_name = full_name[:keyword_index].strip()
                    extracted_position = full_name[keyword_index:].strip()
                    
                    # Combine with existing position
                    if position_text:
                        if extracted_position.lower() not in position_text.lower():
                            position = f"{extracted_position} {position_text}"
                        else:
                            position = position_text
                    else:
                        position = extracted_position
                        
                    return clean_name, position.strip()
                    
            # If no keywords found but still too long, just take first 2-3 words as name
            clean_name = " ".join(clean_name_parts[:3])
        else:
            clean_name = " ".join(clean_name_parts)
    else:
        clean_name = " ".join(clean_name_parts)
        
    # Combine extracted position with any existing position
    extracted_position = " ".join(position_parts)
    if extracted_position and position_text:
        # Avoid duplication
        if extracted_position.lower() not in position_text.lower():
            position = f"{extracted_position} {position_text}"
        else:
            position = position_text
    elif extracted_position:
        position = extracted_position
    else:
        position = position_text
    
    return clean_name.strip(), position.strip() 

def extract_summary(text: str, section_range: Tuple[int, int]) -> str:
    """
    Extract professional summary or objective statement with improved accuracy
    
    Args:
        text: Full resume text
        section_range: (start, end) positions of the summary section
        
    Returns:
        Extracted summary text
    """
    # Extract the summary section text
    section_text = text[section_range[0]:section_range[1]]
    
    # Skip the header line
    section_lines = section_text.split('\n')
    if len(section_lines) <= 1:
        return ""
        
    section_content = '\n'.join(section_lines[1:])
    
    # Clean the summary text
    summary = re.sub(r'\s+', ' ', section_content).strip()
    
    # Check if the summary is actually a list of bullet points
    if re.search(r'(?:\n|^)[•\*\-]\s', section_content):
        bullet_points = re.findall(r'[•\*\-]\s+([^\n•\*\-]+)', section_content)
        if bullet_points:
            # Transform bullet points into a coherent paragraph
            summary = ' '.join([point.strip() for point in bullet_points])
    
    # If summary is too short, try to get more content
    # Sometimes the section detection isn't perfect and cuts off the summary
    if len(summary) < 100 and section_range[1] < len(text) and section_range[1] + 500 < len(text):
        # Try to extract a larger chunk of text
        extended_text = text[section_range[0]:section_range[1] + 500]
        
        # Find the next section header if any
        next_section_match = re.search(r'\n[A-Z][A-Z\s]+:?(?:\n|$)', extended_text)
        if next_section_match:
            extended_text = extended_text[:next_section_match.start()]
        
        # Clean up the extended text
        extended_lines = extended_text.split('\n')
        if len(extended_lines) > 1:
            extended_content = '\n'.join(extended_lines[1:])
            
            # Check for bullet points in the extended content
            if re.search(r'(?:\n|^)[•\*\-]\s', extended_content):
                bullet_points = re.findall(r'[•\*\-]\s+([^\n•\*\-]+)', extended_content)
                if bullet_points:
                    summary = ' '.join([point.strip() for point in bullet_points])
            else:
                # Clean the extended summary
                summary = re.sub(r'\s+', ' ', extended_content).strip()
    
    # Sometimes summaries are outside the specific "summary" section
    # If our summary is too short, try to find it elsewhere
    if len(summary) < 50:
        # Try to find a summary at the beginning of the resume (common location)
        first_section_match = re.search(r'\n[A-Z][A-Z\s]+:?(?:\n|$)', text[:500])
        
        if first_section_match:
            # If summary wasn't the first section, check the text before the first section
            top_text = text[:first_section_match.start()].strip()
            
            # Skip contact information which is often at the top
            if not re.search(r'@|[0-9]{3}[-.]?[0-9]{3}[-.]?[0-9]{4}', top_text):
                # This might be a summary or objective that wasn't labeled as such
                if len(top_text) > 50:
                    return top_text
        
        # Try to find a labeled summary or objective elsewhere in the resume
        # This handles cases where the section detection didn't identify it properly
        common_summary_headers = [
            r'SUMMARY', r'PROFESSIONAL SUMMARY', r'CAREER SUMMARY', 
            r'OBJECTIVE', r'CAREER OBJECTIVE', r'PROFESSIONAL OBJECTIVE',
            r'PROFILE', r'PROFESSIONAL PROFILE', r'ABOUT ME'
        ]
        
        for header in common_summary_headers:
            # Look for the header followed by text
            summary_match = re.search(r'(?:\n|^)' + header + r'[:\s]*\n+(.+?)(?=\n\n|\n[A-Z][A-Z\s]+:?|\Z)', 
                                    text, re.IGNORECASE | re.DOTALL)
            if summary_match:
                alt_summary = summary_match.group(1).strip()
                if alt_summary and len(alt_summary) > len(summary):
                    # Check if it's a list of bullet points
                    if re.search(r'(?:\n|^)[•\*\-]\s', alt_summary):
                        bullet_points = re.findall(r'[•\*\-]\s+([^\n•\*\-]+)', alt_summary)
                        if bullet_points:
                            alt_summary = ' '.join([point.strip() for point in bullet_points])
                    
                    summary = re.sub(r'\s+', ' ', alt_summary).strip()
                    break
    
    # Final cleanup and validation
    
    # Remove unnecessary words like "Summary:" that might be included
    summary = re.sub(r'^(?:Summary|Objective|Profile|About):\s*', '', summary, flags=re.IGNORECASE)
    
    # Ensure the summary is a complete sentence or paragraph
    if summary and not summary.endswith(('.', '!', '?')):
        summary += '.'
    
    # If summary is too short or empty, check the first 1000 characters of the resume
    # for a paragraph that might be a summary
    if len(summary) < 50:
        intro_text = text[:1000]
        paragraphs = re.split(r'\n\s*\n', intro_text)
        
        for para in paragraphs:
            # Skip contact info, very short paragraphs, or obvious headers
            if re.search(r'@|[0-9]{3}[-.]?[0-9]{3}[-.]?[0-9]{4}', para) or len(para) < 50 or para.isupper():
                continue
                
            if not re.match(r'(?:EXPERIENCE|EDUCATION|SKILLS|PROJECTS|WORK|EMPLOYMENT)\b', para, re.IGNORECASE):
                # This could be a summary
                potential_summary = re.sub(r'\s+', ' ', para).strip()
                
                # Use this if it's longer than what we have
                if len(potential_summary) > len(summary):
                    summary = potential_summary
                    break
    
    # Ensure the summary is a reasonable length for ATS
    if len(summary) > 1000:
        # Truncate at a sentence boundary
        sentences = re.split(r'(?<=[.!?])\s+', summary[:1000])
        summary = ' '.join(sentences[:-1])
    
    return summary 