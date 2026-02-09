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
    
    # 1. Rename existing table
    print("Renaming existing 'users' table to 'users_backup'...")
    try:
        cur.execute("ALTER TABLE users RENAME TO users_backup;")
    except psycopg2.errors.UndefinedTable:
        print("Table 'users' does not exist, skipping rename.")
        conn.rollback()
    except Exception as e:
        print(f"Error renaming table: {e}")
        conn.rollback()
    else:
        conn.commit()

    # 2. Create new table
    print("Creating new 'users' table...")
    cur.execute('''
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            pw TEXT NOT NULL,
            name TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            email TEXT,
            address TEXT,
            phone TEXT,
            type TEXT DEFAULT 'applicant'
        )
    ''')
    conn.commit()
    print("New 'users' table created successfully.")
    
    conn.close()

except Exception as e:
    print(f"Migration Error: {e}")
