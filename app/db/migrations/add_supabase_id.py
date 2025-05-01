from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Always use SQLite for migrations to ensure they work
# This avoids issues with Supabase configuration during initial setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
if "SUPABASE" in DATABASE_URL:
    print("Using SQLite for migrations instead of Supabase for safety")
    DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def column_exists(table_name, column_name):
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns

def migrate():
    print("Starting migration to add supabase_id to User table...")
    
    # Create the column if it doesn't exist
    try:
        # Check if the column already exists
        if not column_exists("users", "supabase_id"):
            print("Adding supabase_id column to users table...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN supabase_id VARCHAR"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_supabase_id ON users (supabase_id)"))
                conn.commit()
            print("Column added successfully!")
        else:
            print("supabase_id column already exists in users table. Skipping migration.")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        print("You may need to manually add the supabase_id column to your users table.")
        return False
    
    print("Migration completed successfully!")
    return True

if __name__ == "__main__":
    migrate() 