from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Check for Vercel environment
IS_VERCEL = os.environ.get("VERCEL", "0") == "1"

# Database configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "")
SUPABASE_HOST = os.getenv("SUPABASE_HOST", "")
SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
SUPABASE_PORT = os.getenv("SUPABASE_PORT", "5432") 
SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")

# Direct PostgreSQL connection string for Vercel
POSTGRES_URL = os.getenv("POSTGRES_URL", "")

# Database URL selection logic
if POSTGRES_URL:
    # Use direct PostgreSQL URL if provided (recommended for Vercel)
    DATABASE_URL = POSTGRES_URL
    connect_args = {}
    print("Using direct PostgreSQL URL")
elif SUPABASE_HOST and SUPABASE_PASSWORD:
    # Use Supabase PostgreSQL if credentials are provided
    DATABASE_URL = f"postgresql://{SUPABASE_USER}:{SUPABASE_PASSWORD}@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"
    connect_args = {}
    print("Using Supabase PostgreSQL")
else:
    # SQLite fallback (won't work properly on Vercel)
    if IS_VERCEL:
        print("WARNING: Using SQLite on Vercel will have limited functionality due to serverless constraints")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    print(f"Using SQLite: {DATABASE_URL}")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 