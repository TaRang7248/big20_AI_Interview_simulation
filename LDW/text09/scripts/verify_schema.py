import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
import uuid
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def verify():
    print("Verifying database schema and data insertion...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        c = conn.cursor()
        
        # 1. Check Columns
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'interview_result'
        """)
        columns = [row[0] for row in c.fetchall()]
        
        required_columns = ['announcement_title', 'announcement_job']
        missing = [col for col in required_columns if col not in columns]
        
        if missing:
            print(f"FAILED: Missing columns in Interview_Result: {missing}")
            return
        else:
            print("SUCCESS: New columns found in Interview_Result.")

        # 2. Test Insertion
        test_id = str(uuid.uuid4())
        test_title = "TEST_TITLE"
        test_job = "TEST_JOB_DESC"
        
        try:
            print("Attempting to insert dummy record...")
            c.execute("""
                INSERT INTO Interview_Result (
                    interview_number, 
                    tech_score, tech_eval, 
                    problem_solving_score, problem_solving_eval, 
                    communication_score, communication_eval, 
                    non_verbal_score, non_verbal_eval, 
                    pass_fail,
                    announcement_title, announcement_job
                ) VALUES (%s, 0, 'Test', 0, 'Test', 0, 'Test', 0, 'Test', '보류', %s, %s)
            """, (test_id, test_title, test_job))
            conn.commit()
            print("SUCCESS: Dummy record inserted.")
            
            # 3. Verify Data
            c.execute("SELECT announcement_title, announcement_job FROM Interview_Result WHERE interview_number = %s", (test_id,))
            row = c.fetchone()
            if row and row[0] == test_title and row[1] == test_job:
                 print("SUCCESS: Data verification matched.")
            else:
                 print(f"FAILED: Data verification failed. Got: {row}")
                 
            # Cleanup
            c.execute("DELETE FROM Interview_Result WHERE interview_number = %s", (test_id,))
            conn.commit()
            print("Cleanup complete.")
            
        except Exception as e:
            print(f"FAILED: Insertion error: {e}")
            conn.rollback()

        conn.close()
        
    except Exception as e:
        print(f"Verification script failed: {e}")

if __name__ == "__main__":
    verify()
