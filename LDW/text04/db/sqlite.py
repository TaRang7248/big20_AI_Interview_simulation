import sqlite3
import os
import json
from datetime import datetime

# Database paths as specified by the user
INTERVIEW_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text04\db\interview.db'
INTERVIEW_SAVE_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text04\db\interview_save.db'

def init_sqlite():
    """Initializes the save database if it doesn't exist."""
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
            created_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def get_questions_by_job(job_title: str):
    """Reads interview questions from the source interview.db."""
    if not os.path.exists(INTERVIEW_DB_PATH):
        print(f"Warning: {INTERVIEW_DB_PATH} not found.")
        return []
        
    conn = sqlite3.connect(INTERVIEW_DB_PATH)
    cursor = conn.cursor()
    # Simple search for job title in questions or a specific job_title column if it exists
    # Assuming interview.db has a table 'questions' with 'job_title' and 'question'
    try:
        cursor.execute("SELECT question FROM questions WHERE job_title LIKE ?", (f"%{job_title}%",))
        questions = [row[0] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        # Fallback if table/column structure is different
        try:
            cursor.execute("SELECT question FROM interview_questions WHERE job LIKE ?", (f"%{job_title}%",))
            questions = [row[0] for row in cursor.fetchall()]
        except:
            questions = []
    finally:
        conn.close()
    return questions

def log_interview_step(candidate_name, job_title, question, answer, evaluation):
    """Writes interview results to interview_save.db."""
    conn = sqlite3.connect(INTERVIEW_SAVE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interview_logs (candidate_name, job_title, question, answer, evaluation, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (candidate_name, job_title, question, answer, json.dumps(evaluation, ensure_ascii=False), datetime.now().isoformat()))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_sqlite()
    print("SQLite Databases initialized.")
