import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def migrate():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # Add resume_image_path column if it doesn't exist
        print("Checking/Adding 'resume_image_path' column to 'interview_result' table...")
        
        # Check if column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='interview_result' AND column_name='resume_image_path';
        """)
        if not cur.fetchone():
            print("Column 'resume_image_path' does not exist. Adding...")
            cur.execute("ALTER TABLE interview_result ADD COLUMN resume_image_path TEXT;")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column 'resume_image_path' already exists.")
            
        cur.close()
        conn.close()
        print("Migration complete.")
        
    except Exception as e:
        print(f"Migration Error: {e}")

if __name__ == "__main__":
    migrate()
