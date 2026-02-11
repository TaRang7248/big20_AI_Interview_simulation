import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

def migrate():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        # Add session_name column to Interview_Result table if it doesn't exist
        print("Checking/Adding session_name to Interview_Result table...")
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='interview_result' AND column_name='session_name') THEN
                    ALTER TABLE Interview_Result ADD COLUMN session_name VARCHAR(255);
                    RAISE NOTICE 'Column session_name added to Interview_Result table.';
                ELSE
                    RAISE NOTICE 'Column session_name already exists in Interview_Result table.';
                END IF;
            END $$;
        """)
        
        conn.commit()
        print("Migration check completed.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
