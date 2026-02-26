import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import json
from dotenv import load_dotenv

# .env 환경 변수 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# 데이터베이스 접속 정보
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

INPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'interview_db_backup.json')

# 가져오기를 진행할 테이블 목록 (의존성을 고려한 순서 지정)
# 1. users (기본 사용자 테이블)
# 2. interview_answer (질문의 기준점 역할)
# 3. interview_announcement (users에 종속)
# 4. job_question_pool (논리적으로 interview_answer에 종속)
# 5. interview_information (users에 종속)
# 6. Interview_Progress (users에 종속)

IMPORT_ORDER = [
    'users',
    'interview_answer',
    'interview_announcement',
    'job_question_pool',
    'interview_information',
    'Interview_Progress'
]

def import_data():
    conn = None
    try:
        if not os.path.exists(INPUT_FILE):
             print(f"오류: 시작 실패. 백업 파일 '{INPUT_FILE}'을 찾을 수 없습니다.")
             return

        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)

        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        print(f"[{DB_NAME}] 데이터베이스로 가져오기 시작...")

        for table in IMPORT_ORDER:
            rows = all_data.get(table, [])
            if not rows:
                print(f"[{table}] 테이블 건너뜀 (백업 파일에 데이터가 없음).")
                continue
            
            print(f"[{table}] 데이터 가져오는 중 ({len(rows)} 레코드)...")
            
            # 첫 번째 레코드에서 컬럼 목록 추출
            first_row = rows[0]
            columns = list(first_row.keys())
            columns_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            
            success_count = 0
            
            for row in rows:
                values = [row[col] for col in columns]
                
                # 중복 방지를 위한 ON CONFLICT DO NOTHING 구문 적용
                # 참고: 이 기능은 기본 키(PK) 제약 조건이 존재함을 전제로 합니다.
                # PK가 없는 테이블의 경우 데이터가 중복될 수 있으므로 주의해야 합니다.
                # 그러나 대부분의 대상 테이블은 PK를 가지고 있습니다.
                query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                
                try:
                    cur.execute(query, values)
                    success_count += cur.rowcount
                except Exception as e:
                    print(f"  - {table} 테이블 데이터 삽입 중 오류: {e}")
                    # 오류 발생 시에도 다음 라인으로 이어서 허용 (안정성을 위함)
            
            print(f"  - {success_count}개 레코드 삽입 성공.")
            
            # 'id' 컬럼이 존재할 경우 시퀀스(Sequence) 갱신
            if 'id' in columns:
                 try:
                     # 이 'id' 컬럼과 연관된 시퀀스의 이름을 찾음
                     cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                     seq_name = cur.fetchone()[0]
                     
                     if seq_name:
                         # 시퀀스의 값을 현재 내 최대 id 값으로 갱신
                         cur.execute(f"SELECT setval('{seq_name}', (SELECT MAX(id) FROM {table}))")
                         print(f"  - '{seq_name}' 시퀀스가 갱신되었습니다.")
                 except Exception as e:
                     # 보통은 시퀀스가 없거나(id가 serial이 아님) 할 때 발생하며, 무시 가능함
                     pass
        
        conn.commit()
        print("\n가져오기(Import) 프로세스가 성공적으로 완료되었습니다!")
        
    except psycopg2.Error as e:
        print(f"데이터베이스 오류: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"일반 오류: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_data()
