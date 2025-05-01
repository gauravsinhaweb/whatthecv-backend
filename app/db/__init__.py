from app.db.base import Base, engine, get_db

def init_db():
    Base.metadata.create_all(bind=engine)
