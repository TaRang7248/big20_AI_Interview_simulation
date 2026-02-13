import psycopg2
import json
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# DB Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

INPUT_FILE = 'interview_db_backup.json'

# Tables to import (Order matters for dependency)
# 1. users (Base)
# 2. interview_answer (Base for questions)
# 3. interview_announcement (Depends on users)
# 4. job_question_pool (Depends on interview_answer - logically)
# 5. interview_information (Depends on users)
# 6. Interview_Progress (Depends on users)

IMPORT_ORDER = [
    'users',
    'interview_answer',
    'interview_announcement',
    'job_question_pool',
    'interview_information',
    'Interview_Progress'
]

def import_data():
    conn = None
    try:
        if not os.path.exists(INPUT_FILE):
             print(f"Error: Start failed. Backup file '{INPUT_FILE}' not found.")
             return

        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)

        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        print(f"Starting import to {DB_NAME}...")

        for table in IMPORT_ORDER:
            rows = all_data.get(table, [])
            if not rows:
                print(f"Skipping {table} (No data in backup).")
                continue
            
            print(f"Importing {table} ({len(rows)} records)...")
            
            # Get columns from the first record
            first_row = rows[0]
            columns = list(first_row.keys())
            columns_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            
            success_count = 0
            
            for row in rows:
                values = [row[col] for col in columns]
                
                # Construct query with ON CONFLICT DO NOTHING to avoid duplicates
                # Note: This assumes PK constraint exists. 
                # If table has no PK, this might duplicate data so be careful.
                # However, most tables here should have PK.
                query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                
                try:
                    cur.execute(query, values)
                    success_count += cur.rowcount
                except Exception as e:
                    print(f"  - Error inserting row into {table}: {e}")
                    # Allow continuing to next row? Yes for robustness
            
            print(f"  - {success_count} records inserted successfully.")
            
            # Update Sequence if 'id' column exists
            if 'id' in columns:
                 try:
                     # Check if there is a sequence for this id column
                     # This query finds the sequence name associated with the column
                     cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                     seq_name = cur.fetchone()[0]
                     
                     if seq_name:
                         # Update sequence to max id
                         cur.execute(f"SELECT setval('{seq_name}', (SELECT MAX(id) FROM {table}))")
                         print(f"  - Sequence '{seq_name}' updated.")
                 except Exception as e:
                     # Usually means no sequence or 'id' is not serial, which is fine
                     pass
        
        conn.commit()
        print("\nImport process completed successfully!")
        
    except psycopg2.Error as e:
        print(f"Database Error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"General Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_data()
