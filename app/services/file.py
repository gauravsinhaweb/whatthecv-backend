import PyPDF2
from fastapi import UploadFile
import io
import os
import asyncio
import tempfile
import mammoth
import time
from typing import List

from app.utils.file import extract_pdf_with_fallbacks

async def extract_text_from_pdf(file_content: bytes) -> str:
    return await extract_pdf_with_fallbacks(file_content)

async def extract_text_from_docx(file_content: bytes) -> str:
    try:
        result = mammoth.extract_raw_text({"binary": file_content})
        return result.value
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        raise ValueError(f"Failed to extract text from DOCX: {str(e)}")

async def extract_text_from_file(file: UploadFile) -> str:
    start_time = time.time()
    
    try:
        file_content = await file.read()
        
        # Check for null or empty filename
        if file.filename is None:
            raise ValueError("Filename is missing or null")
            
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension == '.pdf':
            text = await extract_text_from_pdf(file_content)
        elif file_extension in ['.docx', '.doc']:
            text = await extract_text_from_docx(file_content)
        elif file_extension == '.txt':
            text = file_content.decode('utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        if not text.strip():
            raise ValueError("No text content could be extracted from the file")
        
        print(f"Text extraction completed in {time.time() - start_time:.2f} seconds")
        return text
    except Exception as e:
        print(f"Text extraction failed: {e}")
        raise
    finally:
        await file.seek(0)  # Reset file position for potential reuse 