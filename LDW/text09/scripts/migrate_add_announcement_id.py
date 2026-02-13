import sys
import os
import psycopg2
from dotenv import load_dotenv

# Add parent directory to path to import config if needed, or just load .env directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def migrate():
    print("Migrating database to add announcement_id...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()

        # 1. Add announcement_id to interview_progress
        try:
            cur.execute("ALTER TABLE interview_progress ADD COLUMN announcement_id INTEGER;")
            print("Added announcement_id to interview_progress.")
        except psycopg2.errors.DuplicateColumn:
            print("announcement_id already exists in interview_progress.")
            conn.rollback()
        else:
            conn.commit()

        # 2. Add announcement_id to interview_result
        try:
            cur.execute("ALTER TABLE interview_result ADD COLUMN announcement_id INTEGER;")
            print("Added announcement_id to interview_result.")
        except psycopg2.errors.DuplicateColumn:
            print("announcement_id already exists in interview_result.")
            conn.rollback()
        else:
            conn.commit()
            
        cur.close()
        conn.close()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
