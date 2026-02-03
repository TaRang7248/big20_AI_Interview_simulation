import sqlite3
import os
import json
from datetime import datetime

SQLITE_DB_PATH = r'C:\big20\big20_AI_Interview_simulation\LDW\text02\db\interview_save.db'

def init_sqlite():
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
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

def log_interview_step(candidate_name, job_title, question, answer, evaluation):
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interview_logs (candidate_name, job_title, question, answer, evaluation, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (candidate_name, job_title, question, answer, json.dumps(evaluation), datetime.now().isoformat()))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_sqlite()
    print("SQLite Database (interview_save.db) initialized.")
