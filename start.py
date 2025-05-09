import os
import argparse
import subprocess
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("whatthecv")

# Load environment variables
load_dotenv()

def setup_environment():
    """Create a minimal .env file if none exists"""
    env_path = Path(".env")
    
    if env_path.exists():
        logger.info(".env file already exists")
        return
        
    example_path = Path(".env.example")
    if example_path.exists():
        logger.info("Creating .env file from .env.example...")
        with open(example_path, "r") as example, open(env_path, "w") as env:
            env.write(example.read())
        logger.info("Created .env file. Please update it with your actual values.")
    else:
        logger.info("Creating basic .env file...")
        with open(env_path, "w") as env:
            env.write("SECRET_KEY=supersecretkey\n")
            env.write("ALGORITHM=HS256\n")
            env.write("ACCESS_TOKEN_EXPIRE_MINUTES=30\n")
            env.write("DATABASE_URL=sqlite:///./app.db\n")
        logger.info("Created basic .env file. Please update it with your actual values.")

def setup_database():
    """Create database tables"""
    logger.info("Setting up database...")
    
    try:
        # Import database models
        from app.db.base import Base, engine
        from app.models.user import User
        from app.models.otp import OTP
        from app.models.doc import Doc
        
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        logger.debug("This error may be normal if the database is already set up.", exc_info=True)
        return False

def start_server(port=8000, reload=True):
    """Start the FastAPI server using uvicorn"""
    port = int(os.environ.get("PORT", port))
    logger.info(f"Starting server on port {port}...")
    
    args = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
    
    if reload:
        args.append("--reload")
    
    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        logger.info("\nServer stopped")
        sys.exit(0)

def main():
    """Parse command-line arguments and run the application"""
    parser = argparse.ArgumentParser(description="WhatTheCV Backend Starter")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload on code changes")
    parser.add_argument("--skip-setup", action="store_true", help="Skip setting up database")
    parser.add_argument("--setup-only", action="store_true", help="Only set up environment and database")
    
    args = parser.parse_args()
    
    logger.info("WhatTheCV Backend Starter")
    logger.info("-------------------------")
    
    # Set up environment and database
    setup_environment()
    
    if not args.skip_setup:
        setup_database()
    
    if args.setup_only:
        logger.info("Setup complete. Exiting.")
        return
    
    # Start the server
    start_server(port=args.port, reload=not args.no_reload)

if __name__ == "__main__":
    main() 