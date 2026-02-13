import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def check_table(table_name):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name.lower()}';")
        columns = [row[0] for row in cur.fetchall()]
        print(f"Columns in '{table_name}':")
        for col in columns:
            print(f"- {col}")
        conn.close()
    except Exception as e:
        print(f"Error checking {table_name}: {e}")

check_table('interview_progress')
check_table('interview_result')
check_table('users')
check_table('interview_announcement')
check_table('interview_information')
