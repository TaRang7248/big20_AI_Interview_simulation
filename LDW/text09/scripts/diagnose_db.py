import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
from dotenv import load_dotenv

# Load .env
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
    
    # Check columns in interview_progress table
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'interview_progress';")
    columns = cur.fetchall()
    
    print("Columns in 'users' table:")
    for col in columns:
        print(f"- {col[0]} ({col[1]})")
        
    conn.close()

except Exception as e:
    print(f"Error: {e}")
