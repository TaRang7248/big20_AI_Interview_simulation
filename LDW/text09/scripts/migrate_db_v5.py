import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def migrate():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        c = conn.cursor()
        
        print("Adding applicant_id column to Interview_Progress and Interview_Result...")
        try:
            # Add applicant_id to Interview_Progress
            c.execute("ALTER TABLE Interview_Progress ADD COLUMN IF NOT EXISTS applicant_id TEXT")
            # Add applicant_id to Interview_Result
            c.execute("ALTER TABLE Interview_Result ADD COLUMN IF NOT EXISTS applicant_id TEXT")
            
            conn.commit()
            print("Columns added successfully.")
        except Exception as e:
            print(f"Error adding columns: {e}")
            conn.rollback()

        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
