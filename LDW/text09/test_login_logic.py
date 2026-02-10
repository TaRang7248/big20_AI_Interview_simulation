import psycopg2
from psycopg2.extras import RealDictCursor
import os
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def test_login(id_name, pw_input):
    print(f"\n--- Testing Login for ID: {id_name}, PW: {pw_input} ---")
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        c.execute('SELECT * FROM users WHERE id_name = %s', (id_name,))
        row = c.fetchone()
        
        if row:
            user = dict(row)
            print(f"User found: {user['id_name']}")
            print(f"Stored PW (repr): {repr(user['pw'])}")
            
            # Logic from server.py
            is_valid = False
            if check_password_hash(user['pw'], pw_input):
                print("check_password_hash: MATCH")
                is_valid = True
            else:
                print("check_password_hash: FAIL")
                
            if user['pw'] == pw_input:
                print("Plain text match: MATCH")
                is_valid = True
            else:
                print("Plain text match: FAIL")
                
            if is_valid:
                print(">> Login SUCCESS")
            else:
                print(">> Login FAILED (Password mismatch)")
        else:
            print(">> Login FAILED (User not found)")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    test_login("ekdnlt3022", "013579")
    test_login("tkwp3022", "013579")
    test_login("sim_user", "1234")
