import re
from typing import Dict, Optional, Any


async def extract_personal_info(resume_text: str) -> Dict[str, Any]:
    """
    Extract personal information from resume text including name, email, phone, address, and profile summary
    
    Args:
        resume_text: The full text of the resume
        
    Returns:
        Dictionary containing extracted personal information
    """
    result = {
        "name": None,
        "email": None,
        "phone": None,
        "address": None,
        "profile_summary": None
    }
    
    # Extract email addresses using regex
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    emails = re.findall(email_pattern, resume_text)
    if emails:
        result["email"] = emails[0]  # Take the first email found
    
    # Extract phone numbers using regex
    # This pattern covers common formats: (123) 456-7890, 123-456-7890, 123.456.7890, etc.
    phone_pattern = r'(?:\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
    phones = re.findall(phone_pattern, resume_text)
    if phones:
        result["phone"] = phones[0]  # Take the first phone number found
    
    # Extract name - assume it's at the beginning of the document
    # This is a simplified approach - in production, you might want to use NER models
    lines = resume_text.strip().split('\n')
    for i in range(min(5, len(lines))):  # Check first 5 lines
        line = lines[i].strip()
        if line and len(line) < 40 and not re.search(email_pattern, line) and not re.search(phone_pattern, line):
            # A short line at the beginning that's not email/phone is likely the name
            result["name"] = line
            break
    
    # Extract address - look for lines with common address patterns
    address_indicators = ['street', 'avenue', 'ave', 'st', 'road', 'rd', 'lane', 'drive', 'dr', 
                         'circle', 'blvd', 'boulevard', 'apt', 'apartment', 'suite']
    address_candidates = []
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Check if line contains address indicators or zip code pattern
        if (any(indicator in line_lower for indicator in address_indicators) or 
            re.search(r'\b\d{5}(?:-\d{4})?\b', line)):  # US zip code pattern
            address_candidates.append(line)
    
    if address_candidates:
        # If multiple candidates, join up to 2 consecutive lines
        if len(address_candidates) > 1 and address_candidates[0].strip() and address_candidates[1].strip():
            result["address"] = address_candidates[0] + ", " + address_candidates[1]
        else:
            result["address"] = address_candidates[0]
    
    # Extract profile summary - look for sections with keywords
    profile_keywords = ['profile', 'summary', 'objective', 'about me', 'professional summary']
    profile_section = None
    
    # First, try to find a dedicated profile section
    for i, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in profile_keywords):
            # Found a potential profile section heading
            start = i + 1
            end = start
            while end < len(lines) and len(lines[end].strip()) > 0 and end < start + 10:
                end += 1
            if end > start:
                profile_section = ' '.join(lines[start:end])
                break
    
    # If no dedicated section found, take the first paragraph that's not the name/contact info
    if not profile_section:
        for i in range(min(10, len(lines))):
            if lines[i].strip() and all(info not in lines[i].lower() for info in 
                                      [result["email"], result["phone"], result["name"]]):
                # This line doesn't contain already-extracted info, might be profile
                # Collect this and following lines as a paragraph
                start = i
                end = start
                while end < len(lines) and len(lines[end].strip()) > 0 and end < start + 5:
                    end += 1
                if end - start > 1:  # Must be at least 2 lines to be considered a paragraph
                    profile_section = ' '.join(lines[start:end])
                    break
    
    if profile_section:
        # Clean up the profile section
        profile_section = profile_section.strip()
        if len(profile_section) > 50:  # Only include if substantial content
            result["profile_summary"] = profile_section
    
    return result 