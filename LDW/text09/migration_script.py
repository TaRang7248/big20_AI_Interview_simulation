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
        
        # 1. Update interview_progress
        print("Migrating interview_progress...")
        # Check if applicant_id exists
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'interview_progress' AND column_name = 'applicant_id';")
        if cur.fetchone():
            # Copy data if id_name has NULLs where applicant_id is not NULL
            cur.execute("""
                UPDATE interview_progress 
                SET id_name = applicant_id 
                WHERE id_name IS NULL AND applicant_id IS NOT NULL;
            """)
            # Drop applicant_id
            cur.execute("ALTER TABLE interview_progress DROP COLUMN applicant_id;")
            print("- Dropped applicant_id from interview_progress")
        
        # Add Foreign Key if not exists
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_interview_progress_users') THEN
                    ALTER TABLE interview_progress 
                    ADD CONSTRAINT fk_interview_progress_users 
                    FOREIGN KEY (id_name) REFERENCES users(id_name) ON DELETE CASCADE;
                END IF;
            END $$;
        """)
        print("- Added Foreign Key constraint to interview_progress")

        # 2. Update interview_result
        print("Migrating interview_result...")
        # Check if applicant_id exists
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'interview_result' AND column_name = 'applicant_id';")
        if cur.fetchone():
            # Copy data if id_name has NULLs where applicant_id is not NULL
            cur.execute("""
                UPDATE interview_result 
                SET id_name = applicant_id 
                WHERE id_name IS NULL AND applicant_id IS NOT NULL;
            """)
            # Drop applicant_id
            cur.execute("ALTER TABLE interview_result DROP COLUMN applicant_id;")
            print("- Dropped applicant_id from interview_result")
            
        # Add Foreign Key if not exists
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_interview_result_users') THEN
                    ALTER TABLE interview_result 
                    ADD CONSTRAINT fk_interview_result_users 
                    FOREIGN KEY (id_name) REFERENCES users(id_name) ON DELETE CASCADE;
                END IF;
            END $$;
        """)
        print("- Added Foreign Key constraint to interview_result")

        conn.commit()
        print("Migration completed successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
