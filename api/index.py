from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Version tracking
API_VERSION = "2.0.2"
DEPLOY_TIMESTAMP = datetime.datetime.now().isoformat()

try:
    # Import app configuration
    from app.core.config import settings
    
    # Check database configuration
    from sqlalchemy import create_engine, text
    import os
    
    # Print database configuration for debugging
    print("Checking database configuration...")
    postgres_url = os.environ.get("POSTGRES_URL", "")
    supabase_host = os.environ.get("SUPABASE_HOST", "")
    has_pg_config = bool(postgres_url or supabase_host)
    print(f"Has PostgreSQL config: {has_pg_config}")
    
    # Verify database connection
    if has_pg_config:
        try:
            if postgres_url:
                engine = create_engine(postgres_url)
                print("Using POSTGRES_URL for database connection")
            else:
                supabase_user = os.environ.get("SUPABASE_USER", "postgres")
                supabase_password = os.environ.get("SUPABASE_PASSWORD", "")
                supabase_port = os.environ.get("SUPABASE_PORT", "5432")
                supabase_db = os.environ.get("SUPABASE_DB", "postgres")
                db_url = f"postgresql://{supabase_user}:{supabase_password}@{supabase_host}:{supabase_port}/{supabase_db}"
                engine = create_engine(db_url)
                print("Using Supabase config for database connection")
                
            # Test connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print(f"Database connection test: {result.scalar()}")
            print("Database connection successful")
        except Exception as e:
            print(f"Database connection error: {str(e)}")
    else:
        print("No PostgreSQL configuration found")
    
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
            "environment": "vercel" if os.environ.get("VERCEL") == "1" else "local",
            "database": {
                "has_config": has_pg_config,
                "postgres_url": bool(postgres_url),
                "supabase": bool(supabase_host)
            }
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
    
    # Database test endpoint
    @app.get("/api/v1/debug/db")
    def debug_database():
        db_info = {
            "config": {
                "postgres_url": bool(postgres_url),
                "supabase_host": bool(supabase_host),
                "has_config": has_pg_config
            }
        }
        
        # Test connection if config exists
        if has_pg_config:
            try:
                if postgres_url:
                    engine = create_engine(postgres_url)
                else:
                    supabase_user = os.environ.get("SUPABASE_USER", "postgres")
                    supabase_password = os.environ.get("SUPABASE_PASSWORD", "")
                    supabase_port = os.environ.get("SUPABASE_PORT", "5432")
                    supabase_db = os.environ.get("SUPABASE_DB", "postgres")
                    db_url = f"postgresql://{supabase_user}:{supabase_password}@{supabase_host}:{supabase_port}/{supabase_db}"
                    engine = create_engine(db_url)
                
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    test_result = result.scalar()
                
                db_info["connection_test"] = {
                    "success": True,
                    "result": test_result
                }
            except Exception as e:
                db_info["connection_test"] = {
                    "success": False,
                    "error": str(e)
                }
        
        return db_info
    
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