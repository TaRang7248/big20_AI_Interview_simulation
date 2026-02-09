import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    cur = conn.cursor()
    cur.execute("SELECT to_regclass('public.interview_announcement');")
    result = cur.fetchone()
    if result[0]:
        print("Table 'interview_announcement' exists.")
    else:
        print("Table 'interview_announcement' does NOT exist.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
