"""
Compatibility layer for legacy resume models.

This module provides interfaces that match the original Resume, ResumeFile, 
JobDescription, and ResumeAnalysis models, but they use the consolidated Doc
model underneath.

This allows for a smoother migration from the legacy tables to Doc,
as code can still reference the old models while the data is stored
in the unified docs table.
"""

from sqlalchemy.orm import Session
from app.models.doc import Doc, DocType, doc_relationships

class Resume:
    """Compatibility class for the Resume model."""
    
    __tablename__ = "resumes" # For compatibility with SQLAlchemy queries
    
    @staticmethod
    def to_doc(resume_data):
        """Convert Resume data dict to Doc data dict."""
        return {
            "id": resume_data.get("id"),
            "user_id": resume_data.get("user_id"),
            "doc_type": DocType.RESUME.value,
            "file_name": resume_data.get("filename"),
            "extracted_text": resume_data.get("content"),
            "meta_data": {
                "is_resume": resume_data.get("is_resume", True),
                "score": resume_data.get("score"),
                "analysis": resume_data.get("analysis"),
            },
            "is_active": resume_data.get("is_active", True),
            "created_at": resume_data.get("created_at"),
            "updated_at": resume_data.get("updated_at"),
        }
    
    @staticmethod
    def from_doc(doc):
        """Create a Resume-like dict from Doc instance."""
        if not doc or doc.doc_type != DocType.RESUME:
            return None
            
        return {
            "id": doc.id,
            "user_id": doc.user_id,
            "filename": doc.file_name,
            "content": doc.extracted_text,
            "is_resume": doc.meta_data.get("is_resume", True) if doc.meta_data else True,
            "score": doc.meta_data.get("score") if doc.meta_data else None,
            "analysis": doc.meta_data.get("analysis") if doc.meta_data else None,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
    
    @staticmethod
    def get_docs_query(db: Session):
        """Get a query for Resume docs."""
        return db.query(Doc).filter(Doc.doc_type == DocType.RESUME)


class ResumeFile:
    """Compatibility class for the ResumeFile model.
    
    DEPRECATED: This class is maintained only for backward compatibility.
    We are no longer storing binary file content in the database.
    """
    
    __tablename__ = "resume_files" # For compatibility with SQLAlchemy queries
    
    @staticmethod
    def to_doc(file_data):
        """Convert ResumeFile data dict to Doc data dict.
        
        DEPRECATED: Binary file storage is deprecated.
        """
        return {
            "id": file_data.get("id"),
            "user_id": None,  # Resume files didn't store user_id directly
            "doc_type": DocType.RESUME.value,
            "file_name": file_data.get("filename") + " (file)" if file_data.get("filename") else "Resume File",
            # No longer storing binary content
            "meta_data": {
                "is_file": True,
                "resume_id": file_data.get("resume_id"),
            },
            "is_active": True,
            "created_at": file_data.get("created_at"),
        }
    
    @staticmethod
    def from_doc(doc):
        """Create a ResumeFile-like dict from Doc instance.
        
        DEPRECATED: Binary file storage is deprecated.
        """
        if not doc or doc.doc_type != DocType.RESUME:
            return None
            
        # Try to find the resume_id from relationships
        resume_id = None
        for rel in doc.referenced_by:
            if rel.doc_type == DocType.RESUME:
                resume_id = rel.id
                break
                
        return {
            "id": doc.id,
            "resume_id": resume_id or doc.meta_data.get("resume_id") if doc.meta_data else None,
            "filename": doc.file_name.replace(" (file)", "") if doc.file_name else None,
            "file_content": None,  # No binary content
            "file_type": None,  # No MIME type
            "file_size": 0,  # No file size
            "created_at": doc.created_at,
        }
    
    @staticmethod
    def get_docs_query(db: Session):
        """Get a query for ResumeFile docs.
        
        DEPRECATED: Binary file storage is deprecated.
        Always returns an empty query.
        """
        # Return an empty query since we don't store files anymore
        return db.query(Doc).filter(
            Doc.doc_type == DocType.RESUME,
            Doc.id == None  # This will ensure no results
        )


class JobDescription:
    """Compatibility class for the JobDescription model."""
    
    __tablename__ = "job_descriptions" # For compatibility with SQLAlchemy queries
    
    @staticmethod
    def to_doc(job_data):
        """Convert JobDescription data dict to Doc data dict."""
        return {
            "id": job_data.get("id"),
            "user_id": job_data.get("user_id"),
            "doc_type": DocType.JOB_DESCRIPTION.value,
            "file_name": job_data.get("title"),
            "extracted_text": job_data.get("content"),
            "meta_data": {
                "company": job_data.get("company"),
            },
            "is_active": True,
            "created_at": job_data.get("created_at"),
            "updated_at": job_data.get("updated_at"),
        }
    
    @staticmethod
    def from_doc(doc):
        """Create a JobDescription-like dict from Doc instance."""
        if not doc or doc.doc_type != DocType.JOB_DESCRIPTION:
            return None
            
        return {
            "id": doc.id,
            "user_id": doc.user_id,
            "title": doc.file_name,
            "company": doc.meta_data.get("company") if doc.meta_data else None,
            "content": doc.extracted_text,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
    
    @staticmethod
    def get_docs_query(db: Session):
        """Get a query for JobDescription docs."""
        return db.query(Doc).filter(Doc.doc_type == DocType.JOB_DESCRIPTION)


class ResumeAnalysis:
    """Compatibility class for the ResumeAnalysis model."""
    
    __tablename__ = "resume_analyses" # For compatibility with SQLAlchemy queries
    
    @staticmethod
    def to_doc(analysis_data):
        """Convert ResumeAnalysis data dict to Doc data dict."""
        return {
            "id": analysis_data.get("id"),
            "user_id": None,  # Analysis didn't store user_id directly
            "doc_type": DocType.ANALYSIS.value,
            "file_name": f"Analysis of Resume {analysis_data.get('resume_id')}",
            "meta_data": {
                "score": analysis_data.get("score"),
                "is_resume": analysis_data.get("is_resume", True),
                "suggestions": analysis_data.get("suggestions"),
                "keywords": analysis_data.get("keywords"),
                "resume_id": analysis_data.get("resume_id"),
                "job_description_id": analysis_data.get("job_description_id"),
            },
            "is_active": True,
            "created_at": analysis_data.get("created_at"),
        }
    
    @staticmethod
    def from_doc(doc):
        """Create a ResumeAnalysis-like dict from Doc instance."""
        if not doc or doc.doc_type != DocType.ANALYSIS:
            return None
            
        # Try to find the resume_id and job_description_id from relationships
        resume_id = None
        job_description_id = None
        
        if doc.meta_data:
            resume_id = doc.meta_data.get("resume_id")
            job_description_id = doc.meta_data.get("job_description_id")
            
        # Check relationships as well
        for rel in doc.referenced_by:
            if rel.doc_type == DocType.RESUME:
                resume_id = rel.id
            elif rel.doc_type == DocType.JOB_DESCRIPTION:
                job_description_id = rel.id
                
        return {
            "id": doc.id,
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "score": doc.meta_data.get("score") if doc.meta_data else None,
            "is_resume": doc.meta_data.get("is_resume", True) if doc.meta_data else True,
            "suggestions": doc.meta_data.get("suggestions") if doc.meta_data else None,
            "keywords": doc.meta_data.get("keywords") if doc.meta_data else None,
            "created_at": doc.created_at,
        }
    
    @staticmethod
    def get_docs_query(db: Session):
        """Get a query for ResumeAnalysis docs."""
        return db.query(Doc).filter(Doc.doc_type == DocType.ANALYSIS) 