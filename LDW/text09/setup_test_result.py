import psycopg2
import uuid
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def setup_test_result():
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Create a dummy user (Applicant)
        test_id = "test_applicant_01"
        c.execute("DELETE FROM users WHERE id_name = %s", (test_id,))
        c.execute("""
            INSERT INTO users (id_name, pw, name, type, email) 
            VALUES (%s, '1234', '테스트지원자', 'applicant', 'test@example.com')
        """, (test_id,))
        
        # 2. Create a dummy interview result
        interview_number = str(uuid.uuid4())
        c.execute("""
            INSERT INTO Interview_Result (
                interview_number, 
                tech_score, tech_eval, 
                problem_solving_score, problem_solving_eval, 
                communication_score, communication_eval, 
                non_verbal_score, non_verbal_eval, 
                pass_fail,
                title, announcement_job,
                id_name, session_name,
                created_at
            ) VALUES (
                %s, 
                85, '기술 스택에 대한 이해도가 높고, 관련 프레임워크 경험이 풍부합니다. 다만 최신 트렌드에 대한 언급이 다소 부족했습니다.',
                78, '문제를 논리적으로 분해하여 접근하는 방식이 인상적입니다. 예외 처리에 대한 고려가 조금 더 필요해 보입니다.',
                92, '자신의 생각을 매우 명확하고 조리 있게 전달합니다. 질문의 의도를 정확히 파악하고 답변했습니다.',
                88, '면접 전반에 걸쳐 자신감 있고 성실한 태도를 보였습니다. 시선 처리와 목소리 톤이 안정적입니다.',
                '합격',
                '2024년 하반기 공채', '백엔드 개발자',
                %s, '면접-테스트',
                CURRENT_TIMESTAMP
            )
        """, (interview_number, test_id))
        
        conn.commit()
        print(f"Test data inserted successfully.")
        print(f"Applicant ID: {test_id}")
        print(f"Interview Number: {interview_number}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_test_result()
