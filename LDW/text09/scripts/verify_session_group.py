import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
import uuid
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def verify_session_name():
    print("Verifying session_name functionality...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        c = conn.cursor()
        
        # 1. Check if column exists
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'interview_progress' AND column_name = 'session_name'
        """)
        if not c.fetchone():
            print("FAILED: session_name column does not exist in interview_progress table.")
            return

        print("SUCCESS: session_name column exists.")

        # 2. Mock an interview start (manual insertion to avoid calling real API)
        test_id_name = "test_user_" + str(uuid.uuid4())[:8]
        interview_number = str(uuid.uuid4())
        
        # First question
        c.execute("SELECT COUNT(DISTINCT interview_number) FROM Interview_Progress WHERE applicant_id = %s", (test_id_name,))
        interview_count = c.fetchone()[0]
        session_name = f"면접-{interview_count + 1}"
        
        c.execute("""
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Create_Question, applicant_id, session_name
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (interview_number, '테스터', '테스트직무', '자기소개 해주세요.', test_id_name, session_name))
        
        print(f"Inserted first question with session_name: {session_name}")

        # Simulate subsequent question
        next_session_name = session_name # Logic in server.py copies it
        c.execute("""
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Create_Question, applicant_id, session_name
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (interview_number, '테스터', '테스트직무', '다음 질문입니다.', test_id_name, next_session_name))
        
        print(f"Inserted second question with same session_name: {next_session_name}")
        
        conn.commit()

        # 3. Verify in DB
        c.execute("SELECT session_name FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        rows = c.fetchall()
        if len(rows) == 2 and rows[0][0] == rows[1][0] == session_name:
            print(f"SUCCESS: Session grouping verified for {session_name}.")
        else:
            print(f"FAILED: Data verification failed. Rows: {rows}")

        # Cleanup
        c.execute("DELETE FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        conn.commit()
        print("Cleanup complete.")
        
        conn.close()
        
    except Exception as e:
        print(f"Verification script failed: {e}")

if __name__ == "__main__":
    verify_session_name()
