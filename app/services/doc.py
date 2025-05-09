from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Any, Tuple

from app.models.doc import Doc, DocType, doc_relationships
from app.schemas.doc import DocCreate, DocUpdate, DocSearch, RelationshipCreate
from app.services.resume_parser import extract_personal_info
import uuid

async def create_document(
    db: Session,
    doc_data: Dict[str, Any],
    binary_content: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    file_size: Optional[int] = None
) -> Doc:
    """
    Create a new document with optional binary content
    """
    doc_id = str(uuid.uuid4())
    
    # Standardize field names (handle legacy field names)
    file_name = doc_data.get("file_name") or doc_data.get("title", "Untitled")
    extracted_text = doc_data.get("extracted_text") or doc_data.get("text_content", "")
    meta_data = doc_data.get("metadata", {}) or doc_data.get("meta_data", {})
    
    # Extract personal information for resume documents
    person_info = {}
    if doc_data.get("doc_type") == DocType.RESUME.value and extracted_text:
        person_info = await extract_personal_info(extracted_text)
        # Update metadata with personal info
        meta_data.update(person_info)
    
    # Create the document
    doc = Doc(
        id=doc_id,
        user_id=doc_data.get("user_id"),
        doc_type=DocType(doc_data["doc_type"]),
        file_name=file_name,
        extracted_text=extracted_text,
        binary_content=binary_content,
        mime_type=mime_type,
        file_size=file_size,
        meta_data=meta_data,
        
        # Store personal info in dedicated columns
        person_name=person_info.get("name"),
        person_email=person_info.get("email"),
        person_phone=person_info.get("phone"),
        person_address=person_info.get("address"),
        person_links=person_info.get("links")
    )
    
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Create relationships if specified
    await _create_relationships(db, doc_id, doc_data.get("related_doc_ids", []))
    
    return doc

async def _create_relationships(db: Session, doc_id: str, relationships: List[Dict[str, str]]) -> None:
    """Helper function to create document relationships"""
    if not relationships:
        return
        
    for rel in relationships:
        await create_document_relationship(
            db,
            {
                "source_doc_id": doc_id,
                "target_doc_id": rel["id"],
                "relationship_type": rel["relationship"]
            }
        )

async def get_document(db: Session, doc_id: str) -> Optional[Doc]:
    """
    Get a single document by ID
    """
    return db.query(Doc).filter(Doc.id == doc_id).first()

async def get_document_binary(db: Session, doc_id: str) -> Optional[Tuple[bytes, str, str]]:
    """
    Get binary content of a document
    Returns a tuple of (binary_content, mime_type, filename)
    """
    doc = db.query(Doc).filter(Doc.id == doc_id).first()
    if not doc or not doc.binary_content:
        return None
        
    filename = doc.file_name or f"document_{doc_id}"
    return (doc.binary_content, doc.mime_type or 'application/octet-stream', filename)

async def search_documents(db: Session, search_params: Dict[str, Any]) -> List[Doc]:
    """
    Search for documents based on criteria
    """
    query = db.query(Doc)
    
    # Apply filters
    if search_params.get("doc_type"):
        query = query.filter(Doc.doc_type == DocType(search_params["doc_type"]))
        
    if search_params.get("user_id"):
        query = query.filter(Doc.user_id == search_params["user_id"])
        
    if search_params.get("title_contains"):
        query = query.filter(Doc.file_name.ilike(f"%{search_params['title_contains']}%"))
        
    if search_params.get("content_contains"):
        query = query.filter(Doc.extracted_text.ilike(f"%{search_params['content_contains']}%"))
        
    if search_params.get("created_after"):
        query = query.filter(Doc.created_at >= search_params["created_after"])
        
    if search_params.get("created_before"):
        query = query.filter(Doc.created_at <= search_params["created_before"])
        
    if search_params.get("is_active") is not None:
        query = query.filter(Doc.is_active == search_params["is_active"])
    
    # Filter by related document
    if search_params.get("related_to_doc_id"):
        related_id = search_params["related_to_doc_id"]
        query = query.join(
            doc_relationships,
            or_(
                and_(Doc.id == doc_relationships.c.source_doc_id, 
                     doc_relationships.c.target_doc_id == related_id),
                and_(Doc.id == doc_relationships.c.target_doc_id, 
                     doc_relationships.c.source_doc_id == related_id)
            )
        )
    
    # Execute query
    return query.all()

async def update_document(db: Session, doc_id: str, update_data: Dict[str, Any]) -> Optional[Doc]:
    """
    Update a document's properties
    """
    doc = await get_document(db, doc_id)
    if not doc:
        return None
    
    # Handle special case for metadata
    if "metadata" in update_data and update_data["metadata"] and isinstance(doc.meta_data, dict):
        # Merge metadata instead of replacing
        doc.meta_data = {**doc.meta_data, **update_data["metadata"]}
        del update_data["metadata"]
    
    # Update other fields
    for key, value in update_data.items():
        if hasattr(doc, key):
            setattr(doc, key, value)
    
    db.commit()
    db.refresh(doc)
    return doc

async def create_document_relationship(db: Session, relationship_data: Dict[str, str]) -> bool:
    """
    Create a relationship between two documents
    """
    source_id = relationship_data["source_doc_id"]
    target_id = relationship_data["target_doc_id"]
    rel_type = relationship_data["relationship_type"]
    
    # Check if both documents exist
    source_doc = await get_document(db, source_id)
    target_doc = await get_document(db, target_id)
    
    if not source_doc or not target_doc:
        return False
    
    # Insert into relationship table
    db.execute(
        doc_relationships.insert().values(
            source_doc_id=source_id,
            target_doc_id=target_id,
            relationship_type=rel_type
        )
    )
    db.commit()
    
    return True

async def get_related_documents(db: Session, doc_id: str, relationship_type: Optional[str] = None) -> List[Doc]:
    """
    Get all documents related to the given document
    Optionally filter by relationship type
    """
    query = db.query(Doc).join(
        doc_relationships,
        or_(
            and_(Doc.id == doc_relationships.c.target_doc_id, 
                 doc_relationships.c.source_doc_id == doc_id),
            and_(Doc.id == doc_relationships.c.source_doc_id, 
                 doc_relationships.c.target_doc_id == doc_id)
        )
    )
    
    if relationship_type:
        query = query.filter(doc_relationships.c.relationship_type == relationship_type)
    
    return query.all()

async def delete_document(db: Session, doc_id: str, soft_delete: bool = True) -> bool:
    """
    Delete a document
    By default, performs a soft delete by setting is_active=False
    """
    doc = await get_document(db, doc_id)
    if not doc:
        return False
    
    if soft_delete:
        doc.is_active = False
        db.commit()
    else:
        # Hard delete - first remove relationships
        db.execute(doc_relationships.delete().where(
            or_(
                doc_relationships.c.source_doc_id == doc_id,
                doc_relationships.c.target_doc_id == doc_id
            )
        ))
        db.delete(doc)
        db.commit()
    
    return True 