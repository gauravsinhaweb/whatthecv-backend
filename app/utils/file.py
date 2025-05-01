import PyPDF2
import io
from typing import List

async def extract_pdf_with_fallbacks(file_content: bytes) -> str:
    text = ""
    
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    except Exception as e:
        print(f"Primary PDF extraction failed: {e}")
        
    if not text.strip():
        print("Falling back to alternative extraction method")
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_content), strict=False)
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
                except:
                    pass
        except Exception as e:
            print(f"Secondary PDF extraction failed: {e}")
    
    return text.strip() or "No text content could be extracted from the PDF" 