import requests
import psycopg2
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")
BASE_URL = "http://localhost:5000/api"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def test_admin_password_verify():
    conn = get_db_connection()
    c = conn.cursor()
    
    test_id = "test_admin_verify"
    test_pw = "testpass123"
    
    print(f"--- Testing Admin Password Verification ({test_id}) ---")

    try:
        # 1. Cleanup & Insert Test Admin
        c.execute("DELETE FROM users WHERE id_name = %s", (test_id,))
        c.execute("""
            INSERT INTO users (id_name, pw, name, type, email)
            VALUES (%s, %s, 'Test Admin', 'admin', 'admin@test.com')
        """, (test_id, test_pw))
        conn.commit()
        print("[Setup] Test admin created.")

        # 2. Test Correct Password
        resp = requests.post(f"{BASE_URL}/verify-password", json={
            "id_name": test_id,
            "pw": test_pw
        })
        if resp.status_code == 200 and resp.json().get("success"):
            print("[PASS] Correct password verification succeeded.")
        else:
            print(f"[FAIL] Correct password verification failed: {resp.text}")

        # 3. Test Incorrect Password
        resp = requests.post(f"{BASE_URL}/verify-password", json={
            "id_name": test_id,
            "pw": "wrongpassword"
        })
        if resp.status_code == 401:
            print("[PASS] Incorrect password verification failed as expected (401).")
        else:
            print(f"[FAIL] Incorrect password verification unexpected response: {resp.status_code} {resp.text}")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        # 4. Cleanup
        c.execute("DELETE FROM users WHERE id_name = %s", (test_id,))
        conn.commit()
        conn.close()
        print("[Cleanup] Test admin deleted.")

if __name__ == "__main__":
    test_admin_password_verify()
