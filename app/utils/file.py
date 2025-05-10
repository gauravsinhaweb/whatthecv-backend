import PyPDF2
import io
from typing import List
import re

async def extract_pdf_with_fallbacks(file_content: bytes) -> str:
    """Enhanced PDF text extraction with multiple fallback mechanisms."""
    text = ""
    
    # Try the standard extraction first
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            except Exception:
                # Skip problematic pages
                continue
    except Exception:
        # First extraction method failed, continue to fallbacks
        pass
        
    # If first method didn't yield results, try with strict=False
    if not text.strip():
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_content), strict=False)
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
                except:
                    # Skip problematic pages
                    continue
        except Exception:
            # Second extraction method failed, continue to next fallback
            pass
    
    # Clean up the extracted text
    if text:
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove non-printable characters
        text = ''.join(c for c in text if c.isprintable() or c in ['\n', '\t'])
        # Remove very long words (likely garbage)
        text = ' '.join(word for word in text.split() if len(word) < 40)
        
    # If all extraction methods failed or returned empty results, return a generic response
    return text.strip() or "Could not extract text from PDF" 