import psycopg2
import json
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# DB Connection settings
DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn

def setup_data():
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # 1. Create table
        print("Creating table 'interview_answer'...")
        c.execute('''
            CREATE TABLE IF NOT EXISTS interview_answer (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL
            )
        ''')
        
        # 2. Check if data exists (to avoid duplicates on re-run)
        c.execute('SELECT COUNT(*) FROM interview_answer')
        count = c.fetchone()[0]
        
        if count > 0:
            print(f"Table already has {count} records. Skipping data insertion.")
        else:
            # 3. Read JSON data
            json_path = 'data.json'
            if not os.path.exists(json_path):
                print(f"Error: {json_path} not found.")
                return

            print(f"Reading data from {json_path}...")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 4. Insert data
            print(f"Inserting {len(data)} records...")
            for item in data:
                c.execute('''
                    INSERT INTO interview_answer (question, answer)
                    VALUES (%s, %s)
                ''', (item['question'], item['answer']))
            
            conn.commit()
            print("Data insertion complete.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_data()
