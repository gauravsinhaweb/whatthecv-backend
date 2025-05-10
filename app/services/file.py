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
    if not file_content:
        return ""
    return await extract_pdf_with_fallbacks(file_content)

async def extract_text_from_docx(file_content: bytes) -> str:
    if not file_content:
        return ""
    try:
        result = mammoth.extract_raw_text({"binary": file_content})
        return result.value
    except Exception:
        # Return empty string on error, will be handled by caller
        return ""

async def extract_text_from_bytes(content: bytes) -> str:
    """
    Extract text from binary content without requiring a file object.
    This function detects the file type from the content and applies the appropriate extraction method.
    
    Args:
        content: Binary content of the file
        
    Returns:
        Extracted text as a string
    """
    if not content:
        return ""
        
    try:
        # Determine file type from content signature
        if content.startswith(b'%PDF-'):
            # PDF file
            text = await extract_text_from_pdf(content)
        elif content.startswith(b'PK\x03\x04'):
            # Likely a ZIP-based format like DOCX
            text = await extract_text_from_docx(content)
        else:
            # Try different text encodings
            text = ""
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii', 'utf-16']:
                try:
                    decoded = content.decode(encoding)
                    if decoded.strip():
                        text = decoded
                        break
                except:
                    continue
                    
            # If still no text extracted, try as PDF and DOCX as last resort
            if not text:
                try:
                    text = await extract_text_from_pdf(content)
                except:
                    pass
                    
            if not text:
                try:
                    text = await extract_text_from_docx(content)
                except:
                    pass
        
        return text.strip()
    except Exception as e:
        # Log error but return empty string
        import logging
        logging.error(f"Error extracting text from bytes: {str(e)}")
        return ""

async def extract_text_from_file(file: UploadFile) -> str:
    if not file or not file.filename:
        return ""
        
    try:
        # Read file content once
        file_content = await file.read()
        
        # Handle empty files
        if not file_content:
            return ""
            
        # Reset file position for potential reuse
        await file.seek(0)
        
        # Determine file type from extension or content type
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # Extract text based on file type
        if file_extension in ['.pdf', ''] and (file.content_type == 'application/pdf' or not file_extension):
            text = await extract_text_from_pdf(file_content)
        elif file_extension in ['.docx', '.doc']:
            text = await extract_text_from_docx(file_content)
        elif file_extension in ['.txt', '.rtf', '.text', '.md', '.markdown']:
            # Try different encodings for text files
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii', 'utf-16']:
                try:
                    text = file_content.decode(encoding)
                    if text.strip():
                        break
                except:
                    text = ""
        else:
            # For unknown file types, try as text first
            try:
                text = file_content.decode('utf-8')
            except:
                # If not text, check PDF-like content
                if file_content.startswith(b'%PDF-'):
                    text = await extract_text_from_pdf(file_content)
                else:
                    # Last resort, try as docx
                    try:
                        text = await extract_text_from_docx(file_content)
                    except:
                        text = ""
        
        # Return extracted text or empty string
        return text.strip()
    except Exception:
        # Return empty on any error
        return ""
    finally:
        # Always reset file position
        try:
            await file.seek(0)
        except:
            pass 

async def extract_text_with_ocr(file_content: bytes) -> str:
    """
    Extract text from binary file content using OCR for better accuracy.
    Falls back to standard extraction if OCR is not available.
    
    Args:
        file_content: Binary content of the file
        
    Returns:
        Extracted text from the file
    """
    try:
        # Check if we have OCR libraries installed
        try:
            import pytesseract
            from PIL import Image
            import io
            import pdf2image
            has_ocr = True
        except ImportError:
            has_ocr = False
            
        if not has_ocr:
            # Fall back to standard extraction if OCR libraries not available
            from .file import extract_text_from_bytes
            return await extract_text_from_bytes(file_content)
            
        # Get file type
        import magic
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(file_content)
        
        extracted_text = ""
        
        # Process based on file type
        if "pdf" in file_type:
            # Convert PDF to images
            pdf_pages = pdf2image.convert_from_bytes(file_content)
            
            # Process each page
            for page_num, page in enumerate(pdf_pages):
                # Extract text with pytesseract
                page_text = pytesseract.image_to_string(page)
                extracted_text += f"\n\n--- Page {page_num+1} ---\n\n{page_text}"
                
        elif "image" in file_type:
            # Process image directly
            image = Image.open(io.BytesIO(file_content))
            extracted_text = pytesseract.image_to_string(image)
            
        else:
            # For other file types, fall back to standard extraction
            from .file import extract_text_from_bytes
            extracted_text = await extract_text_from_bytes(file_content)
            
        return extracted_text
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"OCR extraction failed: {str(e)}", exc_info=True)
        
        # Fall back to standard extraction
        from .file import extract_text_from_bytes
        return await extract_text_from_bytes(file_content) 