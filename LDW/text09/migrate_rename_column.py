import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def migrate():
    print("Starting migration: Rename announcement_title to title in interview_result table...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='interview_result' AND column_name='announcement_title';
        """)
        if cur.fetchone():
            cur.execute("ALTER TABLE interview_result RENAME COLUMN announcement_title TO title;")
            conn.commit()
            print("Successfully renamed 'announcement_title' to 'title'.")
        else:
            print("Column 'announcement_title' not found. Checking if 'title' already exists...")
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='interview_result' AND column_name='title';
            """)
            if cur.fetchone():
                print("Column 'title' already exists. Migration skipped.")
            else:
                print("Neither 'announcement_title' nor 'title' columns found. Please check table definition.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Migration Error: {e}")

if __name__ == "__main__":
    migrate()
