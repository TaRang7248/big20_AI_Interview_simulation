import sqlite3
import psycopg2
from pgvector.psycopg2 import register_vector
import os
from dotenv import load_dotenv
import openai
import json

load_dotenv()

# Configuration
SQLITE_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text07\db\interview.db'
POSTGRES_HOST = os.getenv("DB_HOST", "127.0.0.1")
POSTGRES_DB = os.getenv("DB_NAME", "interview_db")
POSTGRES_USER = os.getenv("DB_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("DB_PASSWORD", "013579")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

def get_embedding(text):
    text = text.replace("\n", " ")
    return openai.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

def migrate_data():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite DB not found at {SQLITE_DB_PATH}")
        return

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    # Determine table name
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_list = [t[0] for t in sqlite_cursor.fetchall()]
    print(f"Tables found: {tables_list}")
    
    target_table = None
    possible_names = ['questions', 'question', 'interview_results', 'interview_result', 'question_pool']
    
    for name in possible_names:
        if name in tables_list:
            target_table = name
            break
            
    if not target_table:
        print(f"Could not find a suitable table in {possible_names}")
        return

    print(f"Migrating from table: {target_table}")

    # Inspect columns
    sqlite_cursor.execute(f"PRAGMA table_info({target_table})")
    cols_info = sqlite_cursor.fetchall()
    col_names = [c[1] for c in cols_info]
    print(f"Columns: {col_names}")
    
    # Connect to Postgres
    pg_conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    pg_conn.autocommit = True
    register_vector(pg_conn)
    pg_cursor = pg_conn.cursor()

    try:
        sqlite_cursor.execute(f"SELECT * FROM {target_table}")
        rows = sqlite_cursor.fetchall()
        print(f"Found {len(rows)} rows.")
        
        migrated_count = 0
        for row in rows:
            row_dict = dict(zip(col_names, row))
            
            # Map content
            content = None
            for key in ['content', 'question', 'text', 'question_text']:
                if key in row_dict and row_dict[key]:
                    content = row_dict[key]
                    break
            
            if not content:
                continue
                
            # Map category
            category = "General"
            for key in ['category', 'job', 'job_title']:
                if key in row_dict and row_dict[key]:
                    category = row_dict[key]
                    break

            # Deduplicate check (exact content match)
            # pg_cursor.execute("SELECT id FROM questions WHERE content = %s", (content,))
            # if pg_cursor.fetchone():
            #     continue

            try:
                embedding = get_embedding(content)
                pg_cursor.execute(
                    "INSERT INTO questions (content, category, embedding) VALUES (%s, %s, %s)",
                    (content, category, embedding)
                )
                migrated_count += 1
                if migrated_count % 10 == 0:
                    print(f"Migrated {migrated_count}...")
            except Exception as e:
                print(f"Error migrating row: {e}")

        print(f"Successfully migrated {migrated_count} questions.")

    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate_data()
