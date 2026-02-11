import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def verify():
    print("Verifying setup...")
    
    # 1. Check DB
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.Interview_Result');")
        if cur.fetchone()[0]:
            print("✅ Interview_Result table exists.")
        else:
            print("❌ Interview_Result table MISSING.")
        conn.close()
    except Exception as e:
        print(f"❌ DB Connection Failed: {e}")

    # 2. Check Server Syntax
    try:
        import server
        print("✅ server.py imports successfully (Syntax OK).")
    except Exception as e:
        print(f"❌ server.py Import Failed: {e}")

if __name__ == "__main__":
    verify()
