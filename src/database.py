import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Strongly enforce PostgreSQL as per assignment stack
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    # Fallback to local postgres test DB or raise if strict.
    # We'll allow a fallback test DB string for local dev if they didn't set .env yet.
    # But usually it's better to raise.
    SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/skillbridge"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
