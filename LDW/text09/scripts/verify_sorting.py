import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
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
        print(f"DB Connection Error: {e}")
        return None

def test_sorting_logic(user_id):
    conn = get_db_connection()
    if not conn:
        return

    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test 1: No user_id (Default sort by created_at DESC)
        print("\n--- Test 1: No user_id ---")
        c.execute("SELECT id, title, id_name, created_at FROM interview_announcement ORDER BY created_at DESC LIMIT 5")
        rows = c.fetchall()
        for r in rows:
            print(f"ID: {r['id']}, Title: {r['title']}, By: {r['id_name']}, At: {r['created_at']}")

        # Test 2: With user_id (Custom sort)
        print(f"\n--- Test 2: With user_id='{user_id}' ---")
        query = """
            SELECT id, title, id_name, created_at 
            FROM interview_announcement 
            ORDER BY (CASE WHEN id_name = %s THEN 0 ELSE 1 END), created_at DESC
            LIMIT 5
        """
        c.execute(query, (user_id,))
        rows = c.fetchall()
        for r in rows:
            print(f"ID: {r['id']}, Title: {r['title']}, By: {r['id_name']}, At: {r['created_at']}")
            
        # Verification
        if rows and rows[0]['id_name'] == user_id:
             print("\n[PASS] First item is authored by target user.")
        elif rows:
             # Check if user has any posts
             c.execute("SELECT count(*) FROM interview_announcement WHERE id_name = %s", (user_id,))
             count = c.fetchone()['count']
             if count > 0:
                 print("\n[FAIL] First item is NOT by target user, but user has posts.")
             else:
                 print("\n[WARN] Target user has no posts, so sorting cannot be fully verified.")
        else:
             print("\n[WARN] No empty table?")

    finally:
        conn.close()

if __name__ == "__main__":
    # Change this to a user_id that actually exists and has posts for better testing
    # From screenshot: 'tkwp3022' seems to be the admin
    test_user = "tkwp3022" 
    test_sorting_logic(test_user)
