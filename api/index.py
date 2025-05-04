from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.api import auth, resume
from app.db.base import Base, engine
from app.models.user import User
from app.models.otp import OTP
from app.models.resume import Resume, JobDescription, ResumeAnalysis

# Create the FastAPI app
app = FastAPI(title=settings.PROJECT_NAME)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on first request
@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    # Don't run migrations on Vercel as they run on each cold start
    # and SQLite DB is ephemeral anyway

# Include API routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(resume.router, prefix=settings.API_V1_STR)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "WhatthecV API is running on Vercel! 🍾"} 