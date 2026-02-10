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
    c = conn.cursor()
    
    tables = ['interview_progress', 'interview_information', 'interview_announcement', 'users']
    
    for table in tables:
        print(f"\n--- Permission & Constraints for table: {table} ---")
        c.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
        """)
        columns = c.fetchall()
        for col in columns:
            print(f"Col: {col[0]}, Type: {col[1]}, Nullable: {col[2]}, Default: {col[3]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
