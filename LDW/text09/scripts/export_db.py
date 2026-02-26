import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
import json
import datetime
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# .env 환경 변수 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# 데이터베이스 접속 정보 (server.py의 설정과 일치)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'interview_db_backup.json')

# 내보낼 테이블 목록 (의존성을 고려한 순서 지정)
TABLES = [
    'users',
    'interview_announcement',
    'job_question_pool', 
    'interview_information',
    'Interview_Progress',
    'interview_answer' # 이 테이블이 존재하고 데이터가 있을 경우를 대비
]

def json_serial(obj):
    """기본 json 모듈로 직렬화할 수 없는 객체들을 위한 JSON 직렬화 함수"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def export_data():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        all_data = {}
        
        print(f"[{DB_NAME}] 데이터베이스에서 내보내기 시작...")
        
        for table in TABLES:
            try:
                print(f"[{table}] 테이블 내보내는 중...")
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                # RealDictRow 결과를 일반 딕셔너리로 변환
                all_data[table] = [dict(row) for row in rows]
                print(f"  - {len(rows)}개 레코드 내보내기 완료.")
            except psycopg2.errors.UndefinedTable:
                print(f"  - {table} 테이블을 찾을 수 없습니다. 건너뜁니다.")
                conn.rollback() # 트랜잭션 초기화
            except Exception as e:
                print(f"  - {table} 테이블 내보내기 중 오류 발생: {e}")
                conn.rollback()

        # JSON 파일로 저장
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, default=json_serial, ensure_ascii=False, indent=4)
            
        print(f"\n성공적으로 내보내기 완료! 데이터가 '{OUTPUT_FILE}' 경로에 저장되었습니다.")
        print("참고: 이 백업 파일에는 데이터베이스 레코드만 포함되어 있습니다. 첨부 파일 등은 'uploads' 폴더를 수동으로 복사해주세요.")

    except Exception as e:
        print(f"데이터베이스 연결 오류: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    export_data()
