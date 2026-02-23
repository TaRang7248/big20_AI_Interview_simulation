import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def create_tables():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # 1. users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id_name TEXT PRIMARY KEY,
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

        # 2. interview_announcement table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS interview_announcement (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                job TEXT,
                deadline TEXT,
                content TEXT,
                qualifications TEXT,
                preferred_qualifications TEXT,
                benefits TEXT,
                hiring_process TEXT,
                number_of_hires TEXT,
                id_name TEXT REFERENCES users(id_name),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. interview_information table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS interview_information (
                id SERIAL PRIMARY KEY,
                id_name TEXT REFERENCES users(id_name),
                job TEXT,
                resume TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 4. interview_progress table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS interview_progress (
                id SERIAL PRIMARY KEY,
                interview_number TEXT,
                applicant_name TEXT,
                resume TEXT,
                job_title TEXT,
                create_question TEXT,
                question_answer TEXT,
                answer_time TEXT,
                answer_evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                id_name TEXT REFERENCES users(id_name) ON DELETE CASCADE,
                session_name TEXT
            )
        ''')

        # 5. interview_result table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS interview_result (
                id SERIAL PRIMARY KEY,
                interview_number TEXT,
                tech_score INTEGER,
                tech_eval TEXT,
                problem_solving_score INTEGER,
                problem_solving_eval TEXT,
                communication_score INTEGER,
                communication_eval TEXT,
                non_verbal_score INTEGER,
                non_verbal_eval TEXT,
                pass_fail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                announcement_job TEXT,
                id_name TEXT REFERENCES users(id_name) ON DELETE CASCADE,
                session_name TEXT
            )
        ''')

        conn.commit()
        print("All tables checked/created successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_tables()
