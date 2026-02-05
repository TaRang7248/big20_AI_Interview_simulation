import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from db.models import Base
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# Force asyncpg driver
if "postgresql+psycopg2://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
elif "postgresql://" in DATABASE_URL and "asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)

async def init_models():
    async with engine.begin() as conn:
        print("Initializing database...")
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Drop tables to ensure fresh schema matching models.py
        # WARNING: This deletes data. Only for setup/dev.
        print("Dropping old tables...")
        await conn.run_sync(Base.metadata.drop_all)
        
        # Create tables
        print("Creating new tables...")
        await conn.run_sync(Base.metadata.create_all)

    print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_models())
