import os
import psycopg2
import uuid
import json
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
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)

def verify_session_link():
    print("--- Session Name Link Verification Tool ---")
    interview_number = str(uuid.uuid4())
    applicant_id = "test_user"
    applicant_name = "테스트"
    job_title = "테스트 직무"
    session_name = "테스트-면접-1"
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Insert dummy data into Interview_Progress
        print(f"1. Inserting dummy data into Interview_Progress... (Session: {session_name})")
        c.execute("""
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Create_Question, Question_answer, session_name, applicant_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (interview_number, applicant_name, job_title, '질문입니다.', '답변입니다.', session_name, applicant_id))
        conn.commit()
        
        # 2. Mock 'analyze_interview_result' behavior manually (to avoid calling OpenAI API in test)
        # We want to verify if our server.py modification WOULD work.
        # But since we can't easily call the private function from here without importing server.py (which has side effects),
        # let's just simulate the SQL part we added.
        
        print("2. Simulating session_name retrieval and insertion into Interview_Result...")
        # Retrieval (the logic we added to server.py)
        c.execute("SELECT session_name FROM Interview_Progress WHERE Interview_Number = %s LIMIT 1", (interview_number,))
        retrieved_session = c.fetchone()[0]
        
        if retrieved_session != session_name:
            print(f"FAILED: Retrieved session name '{retrieved_session}' does not match original '{session_name}'")
            return
            
        # Insertion (the logic we added to server.py)
        c.execute("""
            INSERT INTO Interview_Result (
                interview_number, applicant_id, announcement_title, session_name, pass_fail
            ) VALUES (%s, %s, %s, %s, %s)
        """, (interview_number, applicant_id, job_title, retrieved_session, '합격'))
        conn.commit()
        
        # 3. Verify in Interview_Result
        print("3. Verifying Interview_Result...")
        c.execute("SELECT session_name FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        final_session = c.fetchone()[0]
        
        if final_session == session_name:
            print("SUCCESS: session_name correctly linked to Interview_Result!")
        else:
            print(f"FAILED: session_name in Interview_Result is '{final_session}', expected '{session_name}'")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        # Clean up
        c.execute("DELETE FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        c.execute("DELETE FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    verify_session_link()
