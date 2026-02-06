import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING")

async def reset_db():
    if not DATABASE_URL:
        print("DATABASE_URL not found!")
        return

    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Dropping all tables...")
        # Get all table names in the public schema
        result = await conn.execute(text("""
            SELECT tablename FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public';
        """))
        tables = [row[0] for row in result]
        
        if tables:
            # Drop all tables with CASCADE
            for table in tables:
                print(f"Dropping table {table}...")
                await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE;'))
            
            # Also drop types if any (optional but good for clean start)
            await conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE;"))
            await conn.execute(text("DROP TYPE IF EXISTS interviewstatus CASCADE;"))
            await conn.execute(text("DROP TYPE IF EXISTS speaker CASCADE;"))
            await conn.execute(text("DROP TYPE IF EXISTS eventtype CASCADE;"))
        
        print("Database reset complete.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_db())
