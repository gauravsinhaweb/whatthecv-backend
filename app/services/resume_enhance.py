import google.generativeai as genai
from typing import Dict, List, Any, Optional
import json
import re

from app.core.config import settings

genai.configure(api_key=settings.GOOGLE_AI_API_KEY)

async def enhance_resume(resume_text: str) -> Dict[str, Any]:
    """
    Enhance a resume by extracting structured information and optimizing content for ATS compatibility
    """
    try:
        # Extract structured information from the resume
        structure = await extract_resume_structure(resume_text)

        # Calculate total number of work experiences to adjust bullet points
        total_work_experiences = len(structure.get('workExperience', []))
        # Calculate total number of projects to adjust description length
        total_projects = len(structure.get('projects', []))

        print("Enhancing resume for ATS optimization...")

        # Process each section in parallel - focus on ATS optimization of existing content
        work_experience = []
        for exp in structure.get('workExperience', []):
            enhanced_description = await enhance_resume_section('experience', exp.get('description', ''), total_work_experiences, total_projects)
            exp['description'] = enhanced_description
            work_experience.append(exp)

        # Don't process descriptions for education entries
        education = [edu for edu in structure.get('education', [])]
        
        # Extract and optimize skills for ATS recognition
        skills_text = ", ".join(structure.get('skills', []))
        skills_enhanced = await enhance_resume_section('skills', skills_text)
        
        # Parse the comma-separated skills
        skills = []
        if skills_enhanced:
            skills = [skill.strip() for skill in skills_enhanced.split(',') if skill.strip()]
            # Filter out non-skill words and duplicates
            skills = filter_skills(skills)

        # Enhance project descriptions - only keep top projects
        projects = structure.get('projects', [])
        # Sort projects by complexity (length of description and technologies)
        projects.sort(key=lambda p: (len(p.get('description', '')) + len(p.get('technologies', ''))) * 2, reverse=True)
        
        enhanced_projects = []
        for proj in projects[:2]:  # Only keep top 2 projects
            enhanced_description = await enhance_resume_section('project', proj.get('description', ''), None, total_projects)
            proj['description'] = enhanced_description
            enhanced_projects.append(proj)

        # Generate short summary for resumes with <= 2 work experiences
        summary = ""
        if total_work_experiences <= 2:
            summary = await enhance_resume_section('summary', structure.get('personalInfo', {}).get('summary', ''))

        print("Resume enhanced for ATS optimization successfully")

        # Construct the enhanced resume with ATS-optimized content
        return {
            "personalInfo": {
                **structure.get('personalInfo', {}),
                "summary": summary if total_work_experiences <= 2 else ""
            },
            "workExperience": work_experience,
            "education": education,
            "skills": skills,
            "projects": enhanced_projects
        }
    except Exception as e:
        print(f'Resume enhancement failed: {e}')
        raise

def filter_skills(skills: List[str]) -> List[str]:
    """Filter and standardize skills for ATS compatibility"""
    # Technical term mappings for common skills
    technical_term_map = {
        'rest': 'REST',
        'rest-api': 'REST API',
        'restapi': 'REST API',
        'restful': 'RESTful',
        'restful-api': 'RESTful API',
        'node.js': 'Node.js',
        'nodejs': 'Node.js',
        'node-js': 'Node.js',
        'react.js': 'React.js',
        'reactjs': 'React',
        'react-js': 'React',
        'typescript': 'TypeScript',
        'javascript': 'JavaScript',
        'vue.js': 'Vue.js',
        'vuejs': 'Vue',
        'vue-js': 'Vue',
        'angular.js': 'Angular.js',
        'angularjs': 'Angular',
        'angular-js': 'Angular',
        'express.js': 'Express.js',
        'expressjs': 'Express',
        'express-js': 'Express',
        'next.js': 'Next.js',
        'nextjs': 'Next.js',
        'next-js': 'Next.js',
        'nosql': 'NoSQL',
        'mongodb': 'MongoDB',
        'postgresql': 'PostgreSQL',
        'mysql': 'MySQL',
        'mariadb': 'MariaDB',
        'graphql': 'GraphQL',
        'docker': 'Docker',
        'kubernetes': 'Kubernetes',
        'aws': 'AWS',
        'gcp': 'GCP',
        'azure': 'Azure',
        'ci/cd': 'CI/CD',
        'cicd': 'CI/CD',
        'ci-cd': 'CI/CD',
        'react-native': 'React Native',
        'reactnative': 'React Native',
        'machine-learning': 'Machine Learning',
        'machinelearning': 'Machine Learning',
        'deep-learning': 'Deep Learning',
        'deeplearning': 'Deep Learning',
        'data-science': 'Data Science',
        'datascience': 'Data Science',
        'devops': 'DevOps',
        'git': 'Git',
        'github': 'GitHub',
        'gitlab': 'GitLab',
        'bitbucket': 'Bitbucket',
        'python-fastapi': 'Python FastAPI',
        'pythonfastapi': 'Python FastAPI',
        'expo-react-native': 'React Native',
        'exporeactnative': 'React Native',
        'fastapi': 'FastAPI',
        'java-spring': 'Java Spring',
        'javaspring': 'Java Spring',
        'spring-boot': 'Spring Boot',
        'springboot': 'Spring Boot',
    }
    
    # Common non-skill words to filter out
    non_skill_words = [
        'and', 'the', 'of', 'in', 'for', 'with', 'on', 'at', 'by', 'to',
        'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'can', 'could', 'may', 'might', 'must', 'shall', 'using', 'leveraging',
        'improving', 'creating', 'developing', 'building', 'working', 'implementing',
        'skills', 'proficient', 'experienced', 'knowledgeable', 'familiar'
    ]
    
    filtered_skills = []
    seen = set()
    
    for skill in skills:
        # Skip if empty or too short
        if not skill or len(skill) < 2:
            continue
            
        # Skip if it's just a non-alphabetic character
        if not any(c.isalpha() for c in skill):
            continue
            
        # Skip common non-skill words
        lower_skill = skill.lower()
        if lower_skill in non_skill_words:
            continue
            
        # Handle special cases and standardize technical terms
        if lower_skill in technical_term_map:
            standardized = technical_term_map[lower_skill]
        elif '-' in skill or '.' in skill or ' ' in skill:
            # For multi-word skills with proper technical capitalization
            lower_with_hyphens = skill.lower().replace(' ', '-')
            if lower_with_hyphens in technical_term_map:
                standardized = technical_term_map[lower_with_hyphens]
            elif ' ' in skill or '-' in skill:
                # For two-word combinations, prefer spaces
                words = skill.replace('-', ' ').split()
                if len(words) == 2:
                    standardized = ' '.join(word.capitalize() for word in words)
                else:
                    # Convert to PascalCase
                    standardized = skill.replace('-', ' ').replace('.', ' ')
                    standardized = ''.join(word.capitalize() for word in standardized.split())
            else:
                standardized = skill
        else:
            # Properly capitalize single-word skills, preserving acronyms
            if skill.upper() == skill and len(skill) <= 5:
                standardized = skill  # Preserve acronyms
            else:
                standardized = skill.capitalize()
                
        # Add only if not already seen (case-insensitive)
        if standardized.lower() not in seen:
            filtered_skills.append(standardized)
            seen.add(standardized.lower())
            
    # Limit to 16 skills
    return filtered_skills[:16]

async def enhance_resume_section(section_type: str, content: str, total_work_items: Optional[int] = None, total_projects: Optional[int] = None) -> str:
    """
    Enhance a specific section of a resume using AI
    """
    if not content or content.strip() == '':
        return ''
        
    # Define section-specific word limits to prevent overflow
    section_word_limits = {
        'summary': 50,        # ~2 sentences
        'experience': 100,    # ~4-5 bullet points of 20 words each
        'project': 60,        # Short concise paragraph
        'education': 60,      # Degree info + 2-3 short bullet points
        'skills': 16,         # Just counting number of skills
        'default': 100        # Default fallback
    }
    
    # Dynamically adjust experience bullet points based on total experiences
    max_bullet_points = 4  # Default
    max_words_per_bullet = 20  # Default
    
    if section_type == 'experience' and total_work_items:
        # Adjust max bullet points based on total work experiences
        if total_work_items >= 5:
            max_bullet_points = 2  # Fewer bullets for many experiences
            max_words_per_bullet = 15
        elif total_work_items >= 3:
            max_bullet_points = 3  # Medium number of bullets for average experiences
            max_words_per_bullet = 18
        else:
            max_bullet_points = 4  # More bullets for fewer experiences
            max_words_per_bullet = 20
            
        # Cap the total words proportionally
        section_word_limits['experience'] = max_bullet_points * max_words_per_bullet
        
    # Dynamically adjust project descriptions based on total projects
    if section_type == 'project' and total_projects:
        # Adjust word limit based on number of projects
        if total_projects >= 5:
            section_word_limits['project'] = 30  # Very short for many projects
        elif total_projects >= 3:
            section_word_limits['project'] = 45  # Medium length for 3-4 projects
        else:
            section_word_limits['project'] = 60  # Full length for 1-2 projects
    
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)
        
        # Create section-specific prompts with layout guidance
        if section_type == 'summary':
            prompt = f"""Create a concise professional summary for an early-career professional with limited work experience.

Format requirements:
- Create a SINGLE CONCISE PARAGRAPH (not bullet points)
- STRICT WORD LIMIT: Maximum {section_word_limits['summary']} words total
- Focus on candidate's professional identity, core skills, and career objectives
- Emphasize technical proficiency and key qualifications that make them stand out
- Include relevant industry keywords for ATS optimization
- Use strong, confident language with active voice
- Avoid clichés and generic phrases like "team player" or "hard worker"
- Highlight specialized skills, relevant education, and any notable achievements
- Keep tone professional and achievement-focused
- Do NOT use first-person pronouns (I, me, my)
- If the original contains relevant details, maintain them

Original content (if any):
{content or "No existing summary provided."}

If no content is provided, create a professional summary based on general best practices for early-career professionals.

Example format:
"Results-driven Software Engineer with expertise in JavaScript, React, and Node.js. Demonstrates strong problem-solving abilities through development of responsive web applications and API integrations. Excels in collaborative environments with a focus on clean, maintainable code and efficient user experiences."

Respond with ONLY the enhanced summary paragraph - no additional text or explanations."""
            
        elif section_type == 'skills':
            prompt = f"""Extract and enhance professional technical skills from the following resume content for maximum ATS compatibility.

Return ONLY a comma-separated list of high-value, ATS-optimized technical skills.

Guidelines:
- PRESERVE ALL TECHNICAL SKILLS mentioned in the original content
- Extract precise technical skills that directly match common job description requirements
- Prioritize in-demand, current industry skills that ATS systems frequently scan for
- Use standard technical capitalization (e.g., JavaScript, TypeScript, React, REST API, MongoDB)
- For multi-word skills, use proper technical formatting (e.g., "React Native" or "React.js")
- Include both specific technologies AND broader competency areas
- Balance programming languages, frameworks, tools, platforms, and methodologies
- Include both technical and domain-specific skills when present
- Do NOT include soft skills, traits, or general terms
- Skills should be separated by commas ONLY
- STRICT LIMIT: Return only up to 16 skills maximum
- Ensure skills appear in industry-standard terminology that an ATS will recognize

For example, high-value skills include: React, JavaScript, TypeScript, Java, Python, AWS, Docker, Kubernetes, MongoDB, PostgreSQL, REST API, GraphQL, MySQL, React Native, Node.js, DevOps, CI/CD, System Design.

Example good output: "JavaScript, React, TypeScript, Python, AWS, Docker, REST API, MongoDB"
Example bad output: "coding, development, programming, etc."

Original content to optimize for ATS:
{content}

Respond with ONLY the comma-separated list of skills - no additional text, bullets, or descriptions."""
            
        elif section_type == 'experience':
            prompt = f"""Enhance the following experience section from a resume to maximize ATS compatibility while preserving the original meaning and key details.

Format requirements:
- Use bullet points starting with "•" (NOT dashes, asterisks, or numbers)
- Each bullet point must start on a new line
- Each bullet point should be a single accomplishment or responsibility (not paragraphs)
- STRICT WORD LIMIT: Maximum {section_word_limits['experience']} words total across all bullet points
- {max_bullet_points} bullet points total maximum (fewer if needed to stay under word limit)
- Each bullet point should ideally be {max_words_per_bullet} words or less
- START EACH BULLET WITH A POWERFUL ACTION VERB in past tense (e.g., "Spearheaded", "Implemented", "Orchestrated")
- PRESERVE the factual information and key achievements from the original content
- MAINTAIN all company names, technologies, and numeric metrics from the original
- Include SPECIFIC QUANTIFIABLE METRICS (numbers, percentages, timeframes, dollar amounts, team sizes)
- Use INDUSTRY-SPECIFIC KEYWORDS and technical terms that ATS systems scan for
- Incorporate relevant HARD SKILLS and TECHNICAL COMPETENCIES
- Avoid first-person pronouns (I, me, my)
- No line breaks within individual bullet points
- Use present tense only for current positions
- Prioritize the most impressive and relevant accomplishments first
- Focus on ACHIEVEMENTS and RESULTS rather than just responsibilities
- Include CONTEXT, ACTION, and RESULT in each bullet point when possible
- Use ATS-friendly language that clearly matches job description keywords
- DO NOT INVENT achievements or metrics not mentioned in the original

Example format:
• Spearheaded development of customer portal increasing user engagement by 45% and reducing bounce rate by 30% through UI/UX improvements.
• Implemented CI/CD pipeline with Jenkins and Docker, reducing deployment time from 2 hours to 15 minutes and increasing release frequency.
• Orchestrated migration of legacy systems to cloud infrastructure, resulting in 40% cost reduction and 99.9% uptime.

Original content to optimize for ATS:
{content}

Respond with ONLY the enhanced bullet points - no additional text."""
            
        elif section_type == 'project':
            prompt = f"""Enhance the following project description for a resume to maximize ATS compatibility and keyword relevance while preserving the original content.

Format requirements:
- Create a SINGLE CONCISE PARAGRAPH (NOT bullet points)
- STRICT WORD LIMIT: Maximum {section_word_limits['project']} words total
- No line breaks within the paragraph
- PRESERVE ALL key details, technologies, and achievements from the original content
- Focus on being technical, achievement-oriented, and keyword-rich
- Begin with a STRONG ACTION VERB (e.g., "Developed", "Engineered", "Architected")
- Include ONLY technologies and tools that are actually mentioned in the original
- MAINTAIN all project names, concepts, and metrics from the original
- Emphasize PROBLEM-SOLUTION-RESULT structure when possible
- Highlight technical challenges overcome and engineering decisions
- Include MEASURABLE OUTCOMES or IMPACT only if they appear in the original text
- Use industry-standard technical terminology that ATS systems scan for
- Focus on technical implementation details rather than general descriptions
- DO NOT add any technologies, metrics, or details that aren't present in the original

Example format:
"Developed responsive e-commerce platform using React and Node.js, implementing secure payment processing with Stripe API and optimizing database schema for improved query response times. Engineered Redis caching solution for frequently accessed data, reducing page load time by 40%."

Original content to optimize for ATS:
{content}

IMPORTANT: DO NOT invent details. Only enhance what is already present.
Respond with ONLY the enhanced project paragraph - no additional text or bullet points."""
            
        else:
            prompt = f"""Enhance the following {section_type} from a resume for optimal ATS compatibility while preserving all original information.

Format requirements:
- Maintain all factual information
- STRICT WORD LIMIT: Maximum {section_word_limits.get(section_type, section_word_limits['default'])} words total
- Incorporate relevant industry keywords and terms that ATS systems scan for
- Improve grammar and sentence structure
- Use strong action verbs
- Add quantifiable metrics where possible (only if clearly implied)
- Keep a professional, concise tone
- For bullet points, use "•" character and ensure each starts on a new line
- No line breaks within paragraphs or individual bullet points
- DO NOT add information that isn't in the original content

Original content to optimize for ATS:
{content}

Respond with ONLY the enhanced content, no explanations or commentary."""
        
        result = await model.generate_content(prompt)
        enhanced_text = result.text.strip()
        
        # Post-processing of enhanced text
        
        # Ensure bullet points are properly formatted for experience and education sections
        if section_type in ['experience', 'education']:
            # Replace any non-standard bullet points with standard ones
            enhanced_text = re.sub(r'^[-*]\s+', '• ', enhanced_text, flags=re.MULTILINE)
            
            # Ensure there's no extra line breaks within bullet points
            bullet_points = [point.strip() for point in enhanced_text.split('\n') if point.strip()]
            enhanced_text = '\n'.join(['• ' + point if not point.startswith('•') else point 
                                      for point in bullet_points])
        
        # For project, ensure it's a single paragraph with no bullets
        if section_type == 'project':
            # Remove any bullet points
            enhanced_text = re.sub(r'^[\s•\-*]+|^\d+[\.\)]\s*', '', enhanced_text, flags=re.MULTILINE)
            # Remove line breaks
            enhanced_text = re.sub(r'\n+', ' ', enhanced_text)
        
        # For summary, ensure it's a clean paragraph
        if section_type == 'summary':
            # Remove any bullet points or line numbers
            enhanced_text = re.sub(r'^[\s•\-*]+|^\d+[\.\)]\s*', '', enhanced_text, flags=re.MULTILINE)
            # Remove line breaks
            enhanced_text = re.sub(r'\n+', ' ', enhanced_text)
        
        # Apply word count limits to prevent overflow
        word_limit = section_word_limits.get(section_type, section_word_limits['default'])
        
        if section_type != 'skills':  # Skills are already limited by count, not words
            words = enhanced_text.split()
            if len(words) > word_limit:
                print(f"Truncating {section_type} from {len(words)} to {word_limit} words")
                
                if section_type in ['project', 'summary']:
                    # For project or summary, just truncate to word limit and add a period if needed
                    enhanced_text = ' '.join(words[:word_limit])
                    if not enhanced_text.endswith('.'):
                        enhanced_text += '.'
                else:
                    # For bullet points, try to keep complete bullets up to the word limit
                    bullets = enhanced_text.split('\n')
                    current_words = 0
                    kept_bullets = []
                    
                    for bullet in bullets:
                        bullet_words = len(bullet.split())
                        if current_words + bullet_words <= word_limit:
                            kept_bullets.append(bullet)
                            current_words += bullet_words
                        else:
                            # If we can't fit another full bullet, we're done
                            break
                    
                    enhanced_text = '\n'.join(kept_bullets)
        
        return enhanced_text
    except Exception as e:
        print(f"Error enhancing {section_type} section for ATS: {e}")
        return content  # Return original content on error

async def extract_resume_structure(resume_text: str) -> Dict[str, Any]:
    """
    Extract structured information from resume text
    """
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL_NAME)
        
        prompt = f"""Extract structured information from this resume text, optimizing for ATS compatibility.
        
Format the response as a valid JSON object with the following structure:
{{
  "personalInfo": {{
    "name": "extracted name",
    "title": "job title (use standardized industry title)",
    "email": "email address",
    "phone": "phone number",
    "location": "country name only",
    "summary": "professional summary"
  }},
  "workExperience": [
    {{
      "id": "1",
      "title": "job title (use standardized industry title)",
      "company": "company name",
      "location": "country name only",
      "startDate": "start date (e.g., 'Jan 2020')",
      "endDate": "end date or 'Present'",
      "current": true/false,
      "description": "job description with bullet points"
    }}
  ],
  "education": [
    {{
      "id": "1",
      "degree": "degree name (use standard format like 'Bachelor of Science')",
      "institution": "school name",
      "location": "country name only",
      "startDate": "start date",
      "endDate": "end date",
      "description": "additional details"
    }}
  ],
  "skills": ["skill1", "skill2", "skill3", ...],
  "projects": [
    {{
      "id": "1",
      "name": "project name",
      "description": "project description",
      "technologies": "technologies used (comma-separated technical skills)",
      "link": "project link (if available, otherwise empty string)"
    }}
  ]
}}

Important ATS optimization notes:
- Extract job titles using standardized industry terminology that ATS systems recognize
- For skills, prioritize hard technical skills and industry-specific competencies
- Use proper capitalization for technical terms (e.g., JavaScript not javascript)
- For missing information, use empty strings, don't make up information
- Extract exactly what's in the resume
- All locations should be country names only (e.g., "United States", "Canada", "Germany") - do not include cities or states
- If a location is mentioned with city/state (e.g., "San Francisco, CA"), extract only the country (e.g., "United States")
- If sections are missing entirely, include them as empty arrays
- Preserve formatting in descriptions (especially bullet points)
- For job titles, use standardized formats likely to be recognized by ATS (e.g., "Software Engineer" not "Code Ninja")
- Ensure education degrees use standard formats (e.g., "Bachelor of Science in Computer Science")

Resume text:
{resume_text}"""

        result = await model.generate_content(prompt)
        text = result.text
        
        try:
            # Try to parse the response as JSON
            json_match = re.search(r'{[\s\S]*}', text)
            json_text = json_match.group(0) if json_match else text
            resume_data = json.loads(json_text)
            
            # Ensure all required fields are present with defaults
            return {
                "personalInfo": {
                    "name": resume_data.get("personalInfo", {}).get("name", ""),
                    "title": resume_data.get("personalInfo", {}).get("title", ""),
                    "email": resume_data.get("personalInfo", {}).get("email", ""),
                    "phone": resume_data.get("personalInfo", {}).get("phone", ""),
                    "location": resume_data.get("personalInfo", {}).get("location", ""),
                    "summary": resume_data.get("personalInfo", {}).get("summary", "")
                },
                "workExperience": [
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
                    for i, exp in enumerate(resume_data.get("workExperience", []))
                ],
                "education": [
                    {
                        "id": edu.get("id", str(i+1)),
                        "degree": edu.get("degree", ""),
                        "institution": edu.get("institution", ""),
                        "location": edu.get("location", ""),
                        "startDate": edu.get("startDate", ""),
                        "endDate": edu.get("endDate", ""),
                        "description": edu.get("description", "")
                    }
                    for i, edu in enumerate(resume_data.get("education", []))
                ],
                "skills": resume_data.get("skills", []),
                "projects": [
                    {
                        "id": proj.get("id", str(i+1)),
                        "name": proj.get("name", ""),
                        "description": proj.get("description", ""),
                        "technologies": proj.get("technologies", ""),
                        "link": proj.get("link", "")
                    }
                    for i, proj in enumerate(resume_data.get("projects", []))
                ]
            }
        except Exception as e:
            print(f"Failed to parse resume structure: {e}")
            
            # Return default structure on error
            return {
                "personalInfo": {
                    "name": "",
                    "title": "",
                    "email": "",
                    "phone": "",
                    "location": "",
                    "summary": resume_text[:300]
                },
                "workExperience": [],
                "education": [],
                "skills": [],
                "projects": []
            }
    except Exception as e:
        print(f"Resume structure extraction failed: {e}")
        raise 