import sqlite3
import os
import json
from datetime import datetime

# Database paths as specified by the user
INTERVIEW_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text06\db\interview.db'
INTERVIEW_SAVE_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text06\db\interview_save.db'

def init_sqlite():
    """Initializes the save database and handles migrations."""
    os.makedirs(os.path.dirname(INTERVIEW_SAVE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(INTERVIEW_SAVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interview_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            job_title TEXT,
            question TEXT,
            answer TEXT,
            evaluation TEXT,
            score INTEGER,
            is_follow_up BOOLEAN,
            created_at DATETIME
        )
    ''')
    
    # Check for missing columns (Migration)
    cursor.execute("PRAGMA table_info(interview_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'score' not in columns:
        print("Migrating: Adding 'score' column to interview_logs")
        cursor.execute("ALTER TABLE interview_logs ADD COLUMN score INTEGER DEFAULT 0")
    if 'is_follow_up' not in columns:
        print("Migrating: Adding 'is_follow_up' column to interview_logs")
        cursor.execute("ALTER TABLE interview_logs ADD COLUMN is_follow_up BOOLEAN DEFAULT 0")
        
    conn.commit()
    conn.close()

def get_questions_by_job(job_title: str):
    """Reads interview questions from the source interview.db."""
    if not os.path.exists(INTERVIEW_DB_PATH):
        print(f"Warning: {INTERVIEW_DB_PATH} not found.")
        return []
        
    conn = sqlite3.connect(INTERVIEW_DB_PATH)
    cursor = conn.cursor()
    try:
        # User specified to use interview.db questions. 
        # Based on inspection, we use interview_results table.
        cursor.execute("SELECT question FROM interview_results")
        questions = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"SQLite Query Error: {e}")
        questions = []
    finally:
        conn.close()
    return questions

def log_interview_step(candidate_name, job_title, question, answer, evaluation):
    """Writes interview results to interview_save.db."""
    conn = sqlite3.connect(INTERVIEW_SAVE_DB_PATH)
    cursor = conn.cursor()
    score = evaluation.get("score", 0)
    is_follow_up = evaluation.get("is_follow_up", False)
    cursor.execute('''
        INSERT INTO interview_logs (candidate_name, job_title, question, answer, evaluation, score, is_follow_up, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (candidate_name, job_title, question, answer, json.dumps(evaluation, ensure_ascii=False), score, is_follow_up, datetime.now().isoformat()))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_sqlite()
    print("SQLite Databases initialized.")
