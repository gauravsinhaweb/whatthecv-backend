from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Version tracking
API_VERSION = "2.0.1"
DEPLOY_TIMESTAMP = datetime.datetime.now().isoformat()

try:
    # Import app configuration
    from app.core.config import settings
    
    # Create FastAPI app
    app = FastAPI(title=settings.PROJECT_NAME)
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Root endpoint for health check
    @app.get("/")
    def read_root():
        return {"message": "WhatthecV API is running on Vercel! 🍾"}
    
    # Version endpoint
    @app.get("/version")
    def version():
        return {
            "version": API_VERSION,
            "deployed_at": DEPLOY_TIMESTAMP,
            "environment": "vercel" if os.environ.get("VERCEL") == "1" else "local"
        }
    
    # Test endpoint
    @app.get("/api/v1/test")
    def test_endpoint():
        return {"status": "success", "message": "API is working!"}
    
    # Debug file upload endpoint
    @app.post("/api/v1/debug/upload")
    async def debug_file_upload(file: UploadFile = File(...)):
        content = await file.read()
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "working": True
        }
    
    # Import routers with a try/except to avoid potential import errors
    try:
        from app.api import auth, resume
        
        # Include API routers
        app.include_router(auth.router, prefix=settings.API_V1_STR)
        app.include_router(resume.router, prefix=settings.API_V1_STR)
        
        print("All routers loaded successfully")
    except Exception as e:
        print(f"Error loading routers: {str(e)}")
        # Add a fallback endpoint if routers fail to load
        @app.get("/api/v1/status")
        def api_status():
            return {"status": "limited", "message": "API is running with limited functionality"}
    
except Exception as e:
    # Absolute fallback in case of any initialization errors
    print(f"Critical error during startup: {str(e)}")
    app = FastAPI(title="WhatthecV API (Fallback Mode)")
    
    @app.get("/")
    def fallback_root():
        return {"message": "API is running in fallback mode", "error": str(e)} 