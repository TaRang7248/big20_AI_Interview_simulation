import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import json
import os
import datetime
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# DB Configuration (Match server.py)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'interview_db_backup.json')

# Tables to export (Order matters for dependency)
TABLES = [
    'users',
    'interview_announcement',
    'job_question_pool', 
    'interview_information',
    'Interview_Progress',
    'interview_answer' # If this table exists and has data
]

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def export_data():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        all_data = {}
        
        print(f"Starting export from {DB_NAME}...")
        
        for table in TABLES:
            try:
                print(f"Exporting table: {table}...")
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                # Convert RealDictRow to dict
                all_data[table] = [dict(row) for row in rows]
                print(f"  - {len(rows)} records exported.")
            except psycopg2.errors.UndefinedTable:
                print(f"  - Table {table} not found. Skipping.")
                conn.rollback() # Reset transaction
            except Exception as e:
                print(f"  - Error exporting {table}: {e}")
                conn.rollback()

        # Save to JSON
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, default=json_serial, ensure_ascii=False, indent=4)
            
        print(f"\nExport completed successfully! Data saved to '{OUTPUT_FILE}'")
        print("Note: This backup contains only database records. Please manually backup the 'uploads' folder for attached files.")

    except Exception as e:
        print(f"Database Connection Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_data()
