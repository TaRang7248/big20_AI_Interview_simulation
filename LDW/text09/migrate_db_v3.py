import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

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
        
        # Create Interview_Result Table
        print("Creating Interview_Result table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Interview_Result (
                id SERIAL PRIMARY KEY,
                interview_number VARCHAR(255) NOT NULL,
                tech_score INT,
                tech_eval TEXT,
                problem_solving_score INT,
                problem_solving_eval TEXT,
                communication_score INT,
                communication_eval TEXT,
                non_verbal_score INT,
                non_verbal_eval TEXT,
                pass_fail VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        print("Migration successful: Interview_Result table created.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
