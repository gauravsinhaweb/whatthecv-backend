from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict

from app.db.base import get_db
from app.models.user import User
from app.models.doc import Doc, DocType
from app.services.auth import get_current_user, get_optional_current_user
from app.services.doc import (
    create_document, get_document, search_documents, update_document,
    delete_document, get_related_documents, get_document_binary
)

from app.schemas.doc import (
    DocCreate, DocResponse, DocUpdate, DocTypeEnum
)
import io
import json

router = APIRouter(prefix="/docs", tags=["documents"])

async def check_document_access(doc: Doc, current_user: Optional[User], require_owner: bool = False):
    """Helper function to check document access permissions"""
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    if doc.user_id and doc.user_id != getattr(current_user, 'id', None):
        # If we require document ownership or user is not an admin
        if require_owner or not getattr(current_user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this document"
            )
    return True

@router.post("", response_model=DocResponse)
async def create_doc(
    doc_data: DocCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new document with text content
    """
    try:
        doc_data_dict = doc_data.dict()
        if current_user:
            doc_data_dict["user_id"] = current_user.id
            
        doc = await create_document(db, doc_data_dict)
        return doc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/upload", response_model=DocResponse)
async def upload_doc_with_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: DocTypeEnum = Form(DocTypeEnum.RESUME),
    text_content: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    related_doc_id: Optional[str] = Form(None),
    relationship_type: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload a document with binary content (file)
    Can also include text content and metadata
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Use filename as title if not provided
        if not title:
            title = file.filename or "Untitled Document"
            
        # Parse JSON metadata if provided
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in metadata field"
                )
        
        # For resume documents, extract text content if not provided
        if doc_type == DocTypeEnum.RESUME and not text_content:
            try:
                # Reset file position for reading again
                await file.seek(0)
                # Import text extraction service
                from app.services.file import extract_text_from_file
                text_content = await extract_text_from_file(file)
            except Exception as e:
                # Log the error but continue with creation
                print(f"Text extraction failed: {str(e)}")
        
        # Prepare document data - using new field names
        doc_data = {
            "file_name": title,
            "doc_type": doc_type,
            "extracted_text": text_content,
            "metadata": meta_dict,
            "user_id": current_user.id if current_user else None
        }
        
        # Add related document if provided
        if related_doc_id and relationship_type:
            doc_data["related_doc_ids"] = [
                {"id": related_doc_id, "relationship": relationship_type}
            ]
            
        # Create document with file content
        doc = await create_document(
            db,
            doc_data,
            binary_content=file_content,
            mime_type=file.content_type,
            file_size=len(file_content)
        )
        
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.get("/{doc_id}", response_model=DocResponse)
async def get_doc(
    doc_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get a document by ID
    """
    doc = await get_document(db, doc_id)
    await check_document_access(doc, current_user)
    return doc

@router.get("/{doc_id}/download", response_class=StreamingResponse)
async def download_doc(
    doc_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Download a document's binary content
    """
    doc = await get_document(db, doc_id)
    await check_document_access(doc, current_user)
        
    # Check if document has binary content
    binary_data = await get_document_binary(db, doc_id)
    if not binary_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document has no binary content"
        )
    
    content, mime_type, filename = binary_data
    
    # Return streaming response
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("", response_model=List[DocResponse])
async def list_docs(
    doc_type: Optional[DocTypeEnum] = None,
    user_id: Optional[str] = None,
    title_contains: Optional[str] = None,
    content_contains: Optional[str] = None,
    related_to_doc_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Search for documents with specified criteria
    """
    # Build search parameters
    search_params = {
        "doc_type": doc_type,
        "title_contains": title_contains,
        "content_contains": content_contains,
        "related_to_doc_id": related_to_doc_id,
        "is_active": True
    }
    
    # Handle user_id filter with permissions
    if user_id:
        # Only allow filtering by another user's documents if admin
        if user_id != getattr(current_user, 'id', None) and not getattr(current_user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view other users' documents"
            )
        search_params["user_id"] = user_id
    elif current_user:
        # Default to current user's documents if authenticated
        search_params["user_id"] = current_user.id
    
    docs = await search_documents(db, search_params)
    return docs

@router.patch("/{doc_id}", response_model=DocResponse)
async def update_doc(
    doc_id: str,
    update_data: DocUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update a document's properties
    """
    # First get the document to check permissions
    doc = await get_document(db, doc_id)
    await check_document_access(doc, current_user, require_owner=True)
    
    # Update the document
    updated_doc = await update_document(db, doc_id, update_data.dict(exclude_unset=True))
    
    if not updated_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )
        
    return updated_doc

@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    permanent: bool = Query(False, description="Permanently delete the document"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete a document
    By default, performs a soft delete
    """
    # First get the document to check permissions
    doc = await get_document(db, doc_id)
    await check_document_access(doc, current_user, require_owner=True)
    
    # Delete the document
    success = await delete_document(db, doc_id, soft_delete=not permanent)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )
        
    return {"status": "success", "message": "Document deleted successfully"}

@router.get("/{doc_id}/related", response_model=List[DocResponse])
async def get_doc_related(
    doc_id: str,
    relationship_type: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get related documents
    """
    doc = await get_document(db, doc_id)
    await check_document_access(doc, current_user)
    
    # Get related documents
    related_docs = await get_related_documents(db, doc_id, relationship_type)
    return related_docs 