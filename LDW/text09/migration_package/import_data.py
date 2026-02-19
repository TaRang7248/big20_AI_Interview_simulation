import sys
import os
import psycopg2
import json
import datetime
from dotenv import load_dotenv

# 상위 디렉토리(../../.env)의 .env 파일 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
text09_dir = os.path.dirname(current_dir)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env')
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

SCHEMA_FILE = os.path.join(text09_dir, 'data', 'schema.sql')
DATA_FILE = os.path.join(text09_dir, 'data', 'interview_db_backup.json')

# Tables to import (Order matters for dependency)
TABLES = [
    'users',
    'interview_announcement',
    'job_question_pool', 
    'interview_information',
    'Interview_Progress',
    'interview_answer' 
]

def import_data():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        # Auto-commit enabled for DDL (schema creation)
        conn.autocommit = True
        cur = conn.cursor()

        print(f"Connecting to {DB_NAME}...")

        # 1. Import Schema
        if os.path.exists(SCHEMA_FILE):
             print(f"Importing schema from {SCHEMA_FILE}...")
             with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                 schema_sql = f.read()
                 # Execute SQL script
                 cur.execute(schema_sql)
             print("Schema import completed.")
        else:
             print(f"Warning: Schema file not found at {SCHEMA_FILE}. Assuming tables already exist.")

        # 2. Import Data
        if os.path.exists(DATA_FILE):
            print(f"Importing data from {DATA_FILE}...")
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for table in TABLES:
                if table in data:
                    rows = data[table]
                    print(f"Importing {len(rows)} records into {table}...")
                    
                    if not rows:
                        continue

                    # Insert logic
                    columns = rows[0].keys()
                    query = "INSERT INTO {} ({}) VALUES ({})".format(
                        table,
                        ','.join(columns),
                        ','.join(['%s'] * len(columns))
                    )
                    
                    for row in rows:
                        values = [row[col] for col in columns]
                        try:
                            # Handle conflicts if necessary (ON CONFLICT DO NOTHING)
                            # But since this is a fresh setup, standard INSERT is fine.
                            # For robustness, we can try-except per row or use ON CONFLICT.
                            # Here we use standard INSERT.
                            cur.execute(query, values)
                        except psycopg2.errors.UniqueViolation:
                            print(f"  - Skipping duplicate record in {table}")
                            pass
                        except Exception as e:
                             print(f"  - Error inserting record in {table}: {e}")

            print("Data import completed.")
        else:
            print(f"Warning: Data file not found at {DATA_FILE}.")

    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Wait for DB to be ready (optional, but good practice in docker)
    import time
    time.sleep(5) 
    import_data()
