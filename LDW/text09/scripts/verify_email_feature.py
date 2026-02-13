import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import os
import uuid
import json
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def verify_email_flow():
    print("Verifying Email Flow...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # 1. Check if column exists
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='interview_result' AND column_name='email'")
        if not cur.fetchone():
            print("FAIL: 'email' column missing in 'interview_result'.")
            return
        print("PASS: 'email' column exists.")

        # 2. Simulate User with Email
        test_id = f"test_user_{uuid.uuid4().hex[:8]}"
        test_email = "test@example.com"
        print(f"Creating test user {test_id} with email {test_email}...")
        
        cur.execute("INSERT INTO users (id_name, pw, name, email) VALUES (%s, 'pass', 'TestUser', %s)", (test_id, test_email))
        conn.commit()
        
        # 3. Simulate Interview Result Insertion (Manually, mirroring server logic)
        # Note: We can't easily call server.analyze_interview_result directly without mocking OpenAI, 
        # so we will duplicate the insertion logic to verify the QUERY correctness and DB constraint.
        
        interview_number = f"int_{uuid.uuid4()}"
        print(f"Inserting interview result for {interview_number}...")
        
        # Logic from server.py (Simplified)
        cur.execute("SELECT email FROM users WHERE id_name = %s", (test_id,))
        user_row = cur.fetchone()
        fetched_email = user_row[0] if user_row else ""
        
        if fetched_email != test_email:
            print(f"FAIL: Fetched email '{fetched_email}' does not match '{test_email}'")
            return
            
        cur.execute("""
            INSERT INTO Interview_Result (
                interview_number, pass_fail, title, announcement_job, id_name, session_name, email
            ) VALUES (%s, '합격', 'Test Job', 'Test', %s, 'Session1', %s)
        """, (interview_number, test_id, fetched_email))
        conn.commit()
        print("PASS: Insert successful.")

        # 4. Retrieve via Admin Query Logic
        print("Retrieving via Admin Query...")
        cur.execute("""
            SELECT r.id_name, r.email 
            FROM Interview_Result r
            WHERE r.interview_number = %s
        """, (interview_number,))
        row = cur.fetchone()
        
        if row and row[1] == test_email:
            print("PASS: Retrieved email matches.")
        else:
            print(f"FAIL: Retrieved {row}")

        # Clean up
        cur.execute("DELETE FROM users WHERE id_name = %s", (test_id,))
        conn.commit()
        print("Cleanup done.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    verify_email_flow()
