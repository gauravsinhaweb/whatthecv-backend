from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Initialize database on startup
from app.db.base import Base, engine

@app.on_event("startup")
async def startup_event():
    # Create all tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Import routers after app is created
from app.api import auth, resume

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "WhatthecV API is running on Vercel! 🍾"}

# Include original API routers with full functionality
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(resume.router, prefix=settings.API_V1_STR)

# Test endpoint
@app.get("/api/v1/test")
def test_endpoint():
    return {"status": "success", "message": "API is working!"} 