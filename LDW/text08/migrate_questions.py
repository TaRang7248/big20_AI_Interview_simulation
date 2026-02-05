import sqlite3
import os
from openai import OpenAI
from db.postgres import SessionLocal, QuestionPool, init_db
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def migrate():
    init_db()
    
    sqlite_path = r'C:\big20\big20_AI_Interview_simulation\LDW\text08\db\interview.db'
    if not os.path.exists(sqlite_path):
        print(f"SQLite DB not found at {sqlite_path}")
        return

    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Try different table names if 'questions' doesn't exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Tables in SQLite: {tables}")
    
    # Target table is 'interview_results' based on previous inspection
    target_table = 'interview_results' if 'interview_results' in tables else ('questions' if 'questions' in tables else None)
    if not target_table:
        print("No 'questions' table found.")
        return

    # Based on read_db.py output: (id, candidate_name, job_title, question, answer, evaluation, created_at)
    # Actually, let's just select question and job_title if they exist
    cursor.execute(f"PRAGMA table_info({target_table});")
    cols = [c[1] for c in cursor.fetchall()]
    
    select_query = "SELECT question"
    if 'job_title' in cols:
        select_query += ", job_title"
    else:
        select_query += ", 'Generic' as job_title"
        
    cursor.execute(f"{select_query} FROM {target_table}")
    rows = cursor.fetchall()
    
    db = SessionLocal()
    try:
        for question_text, job in rows:
            # Check if exists
            exists = db.query(QuestionPool).filter(QuestionPool.question == question_text).first()
            if not exists:
                print(f"Migrating: {question_text[:30]}...")
                emb = get_embedding(question_text)
                q = QuestionPool(
                    question=question_text,
                    job_title=job,
                    embedding=emb
                )
                db.add(q)
        db.commit()
        print("Migration completed.")
    except Exception as e:
        print(f"Migration error: {e}")
        db.rollback()
    finally:
        db.close()
        conn.close()

if __name__ == "__main__":
    migrate()
