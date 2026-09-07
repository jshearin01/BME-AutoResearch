import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

os.makedirs(settings.DATA_DIR, exist_ok=True)
# Handle relative sqlite path when running from backend/ vs root
db_url = settings.DATABASE_URL

engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Import models so metadata registers
    from app.modules.projects.models import Project  # noqa: F401
    from app.modules.runs.models import RunLog  # noqa: F401

    Base.metadata.create_all(bind=engine)
