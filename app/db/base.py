from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "")
SUPABASE_HOST = os.getenv("SUPABASE_HOST", "")
SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
SUPABASE_PORT = os.getenv("SUPABASE_PORT", "5432") 
SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")

# Use SQLite as fallback if Supabase credentials are not provided
if SUPABASE_HOST and SUPABASE_PASSWORD:
    DATABASE_URL = f"postgresql://{SUPABASE_USER}:{SUPABASE_PASSWORD}@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"
    connect_args = {}
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 