import sys
import os
import psycopg2
from dotenv import load_dotenv

# 상위 폴더의 .env 파일을 불러오기 위함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def alter_announcement_table():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # 5개의 신규 컬럼을 추가합니다. (이미 존재할 경우 에러가 나지 않도록 처리)
        columns_to_add = [
            ("qualifications", "TEXT"),
            ("preferred_qualifications", "TEXT"),
            ("benefits", "TEXT"),
            ("hiring_process", "TEXT"),
            ("number_of_hires", "TEXT")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                cur.execute(f"ALTER TABLE interview_announcement ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                print(f"Column '{col_name}' checked/added.")
            except Exception as e:
                print(f"Error adding column {col_name}: {e}")
                # 트랜잭션 롤백 방지용
                conn.rollback()

        conn.commit()
        print("interview_announcement table updated successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection/Execution Error: {e}")

if __name__ == "__main__":
    alter_announcement_table()
