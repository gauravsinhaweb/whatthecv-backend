from sqlalchemy import Column, String, ForeignKey, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine

Base = declarative_base()

def upgrade(engine: Engine):
    """
    Make the user_id field in the resumes table nullable
    to support unauthenticated uploads
    """
    # Create a connection and begin a transaction
    connection = engine.connect()
    transaction = connection.begin()
    
    try:
        # Get the existing metadata
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        # Get the resumes table
        resumes_table = metadata.tables['resumes']
        
        # SQLite doesn't support ALTER COLUMN, so we need to create a new table,
        # copy the data, and then rename it
        
        # Create a new temporary table with nullable user_id
        temp_table = Table(
            'resumes_new',
            metadata,
            Column('id', String, primary_key=True),
            Column('user_id', String, ForeignKey("users.id"), nullable=True),
            *[c.copy() for c in resumes_table.columns if c.name not in ('id', 'user_id')]
        )
        
        # Create the new table
        temp_table.create(engine)
        
        # Copy the data from the old table to the new one
        copy_sql = f"""
        INSERT INTO resumes_new
        SELECT * FROM resumes
        """
        connection.execute(copy_sql)
        
        # Drop the old table
        connection.execute("DROP TABLE resumes")
        
        # Rename the new table to the original name
        rename_sql = "ALTER TABLE resumes_new RENAME TO resumes"
        connection.execute(rename_sql)
        
        # Commit the transaction
        transaction.commit()
        
        print("Migration completed: user_id is now nullable in resumes table")
        
    except Exception as e:
        # Rollback in case of error
        transaction.rollback()
        print(f"Migration failed: {str(e)}")
        raise
    finally:
        # Close the connection
        connection.close()

def downgrade(engine: Engine):
    """
    Make the user_id field in the resumes table non-nullable again
    """
    # This is not fully implemented as it's not needed for now
    # In a real application, you would implement this to revert the changes
    pass 