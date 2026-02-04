import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pgvector.sqlalchemy import Vector
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL Connection
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "interview_db")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class QuestionPool(Base):
    __tablename__ = "question_pool"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String, index=True)
    question = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewResult(Base):
    __tablename__ = "interview_results"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, index=True)
    job_title = Column(String, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    evaluation = Column(JSON, nullable=True)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    # Make sure pgvector extension is enabled
    engine_temp = create_engine(f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres", isolation_level="AUTOCOMMIT")
    with engine_temp.connect() as conn:
        # Check if database exists
        exists = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{POSTGRES_DB}'")).fetchone()
        if not exists:
            conn.execute(text(f"CREATE DATABASE {POSTGRES_DB}"))
    
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("PostgreSQL Database initialized with pgvector.")
