import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

def migrate():
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()

        # 1. Create interview_answer table
        print("Creating 'interview_answer' table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interview_answer (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL
            );
        """)
        
        # 2. Import data from data.json
        print("Importing data from data.json...")
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'data.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check if table is empty to avoid duplicates
                cur.execute("SELECT COUNT(*) FROM interview_answer")
                count = cur.fetchone()[0]
                
                if count == 0:
                    for item in data:
                        cur.execute(
                            "INSERT INTO interview_answer (question, answer) VALUES (%s, %s)",
                            (item['question'], item['answer'])
                        )
                    print(f"Imported {len(data)} items.")
                else:
                    print(f"Table 'interview_answer' already nas {count} items. Skipping import.")
        except FileNotFoundError:
            print("Error: data.json not found.")
        except Exception as e:
            print(f"Error importing data: {e}")


        # 3. Create job_question_pool table
        print("Creating 'job_question_pool' table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_question_pool (
                id SERIAL PRIMARY KEY,
                job_title TEXT NOT NULL,
                question_id INTEGER REFERENCES interview_answer(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Update Interview_Progress table
        # We need to drop and recreate to match new schema exactly, or alter it.
        # Given the requirements, recreating is safer for 'development/simulation' context.
        print("Recreating 'Interview_Progress' table...")
        cur.execute("DROP TABLE IF EXISTS Interview_Progress")
        cur.execute("""
            CREATE TABLE Interview_Progress (
                id SERIAL PRIMARY KEY,
                Interview_Number TEXT NOT NULL,
                Applicant_Name TEXT NOT NULL,
                Resume TEXT,
                Job_Title TEXT,
                Create_Question TEXT,
                Question_answer TEXT,
                answer_time TEXT,
                Answer_Evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
