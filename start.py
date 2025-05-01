import os
import argparse
import subprocess
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_environment():
    """Create a minimal .env file if none exists"""
    if not Path(".env").exists():
        if Path(".env.example").exists():
            print("Creating .env file from .env.example...")
            with open(".env.example", "r") as example, open(".env", "w") as env:
                env.write(example.read())
            print("Created .env file. Please update it with your actual values.")
        else:
            print("Creating basic .env file...")
            with open(".env", "w") as env:
                env.write("SECRET_KEY=supersecretkey\n")
                env.write("ALGORITHM=HS256\n")
                env.write("ACCESS_TOKEN_EXPIRE_MINUTES=30\n")
                env.write("DATABASE_URL=sqlite:///./app.db\n")
            print("Created basic .env file. Please update it with your actual values.")

def force_sqlite_for_setup():
    """Temporarily modify DATABASE_URL to use SQLite"""
    # Save original DATABASE_URL for restoration later
    original_url = os.environ.get("DATABASE_URL")
    
    # Check if DATABASE_URL contains Supabase or PostgreSQL connection
    if original_url and ("supabase" in original_url.lower() or "postgres" in original_url.lower()):
        print("Detected PostgreSQL/Supabase in DATABASE_URL")
        print("Using SQLite for initial database setup for safety")
        os.environ["DATABASE_URL"] = "sqlite:///./app.db"
    elif not original_url:
        # If no DATABASE_URL is set, use SQLite
        os.environ["DATABASE_URL"] = "sqlite:///./app.db"
    
    return original_url

def run_migrations():
    """Create database tables and run migrations"""
    print("Running migrations...")
    
    # Store original DATABASE_URL and use SQLite temporarily
    original_db_url = force_sqlite_for_setup()
    
    try:
        # Import database models
        from app.db.base import Base, engine
        from app.models.user import User
        from app.models.otp import OTP
        from app.models.resume import Resume, JobDescription, ResumeAnalysis
        
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Base tables created successfully!")
        
        # Run Supabase migration if not already run
        try:
            import app.db.migrations.add_supabase_id
            print("Running Supabase ID migration...")
            app.db.migrations.add_supabase_id.migrate()
        except Exception as e:
            print(f"Note: Supabase migration issue (this may be normal if already run): {str(e)}")
    except Exception as e:
        print(f"Error running migrations: {str(e)}")
        print("This error may be normal if the database is already set up.")
    finally:
        # Restore original DATABASE_URL if it existed
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
    
    return True

def start_server(port=8000, reload=True):
    """Start the FastAPI server using uvicorn"""
    print(f"Starting server on port {port}...")
    args = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
    
    if reload:
        args.append("--reload")
    
    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        print("\nServer stopped")
        sys.exit(0)

def main():
    """Parse command-line arguments and run the application"""
    parser = argparse.ArgumentParser(description="WhatTheCV Backend Starter")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload on code changes")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip running migrations")
    parser.add_argument("--setup-only", action="store_true", help="Only set up environment and run migrations")
    
    args = parser.parse_args()
    
    print("WhatTheCV Backend Starter")
    print("-------------------------")
    
    # Set up environment and run migrations
    setup_environment()
    
    if not args.skip_migrations:
        run_migrations()
    
    if args.setup_only:
        print("Setup complete. Exiting.")
        return
    
    # Start the server
    start_server(port=args.port, reload=not args.no_reload)

if __name__ == "__main__":
    main() 