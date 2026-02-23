"""
setup_test_user.py - 테스트 계정 초기화 스크립트

사용법:
    python scripts/setup_test_user.py

역할:
  PostgreSQL(interview_db)의 users 테이블에 다음 계정을 삽입합니다.
  이미 존재하는 경우에는 삽입을 건너뜁니다(ON CONFLICT DO NOTHING).

  ┌─────────────┬──────────┬──────────────┐
  │ id_name     │ pw       │ type         │
  ├─────────────┼──────────┼──────────────┤
  │ test        │ test     │ applicant    │
  │ admin       │ admin    │ admin        │
  └─────────────┴──────────┴──────────────┘
"""

import sys
import os

# 프로젝트 루트(text09/)를 sys.path 에 추가하여 app 패키지 임포트 가능하게 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 환경 변수 로드 (.../big20/.env)
# ─────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(os.path.dirname(PROJECT_ROOT)), ".env")
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

# ─────────────────────────────────────────────
# 삽입할 테스트 계정 목록
# ─────────────────────────────────────────────
TEST_USERS = [
    {
        "id_name": "test",
        "pw":      "test",
        "name":    "테스트 지원자",
        "dob":     "2000-01-01",
        "gender":  "M",
        "email":   "test@example.com",
        "address": "서울시 테스트구",
        "phone":   "010-0000-0001",
        "type":    "applicant",  # 지원자 계정
    },
    {
        "id_name": "admin",
        "pw":      "admin",
        "name":    "관리자",
        "dob":     "2000-01-01",
        "gender":  "M",
        "email":   "admin@example.com",
        "address": "서울시 관리구",
        "phone":   "010-0000-0002",
        "type":    "admin",      # 관리자 계정
    },
]


def setup_test_users():
    """테스트 계정을 PostgreSQL 에 삽입합니다. 이미 존재하면 스킵합니다."""
    try:
        import psycopg2
    except ImportError:
        print("[ERROR] psycopg2 가 설치되지 않았습니다. pip install psycopg2-binary 로 설치하세요.")
        sys.exit(1)

    print("=" * 55)
    print("  테스트 계정 초기화 스크립트")
    print(f"  대상 DB: {DB_NAME}  ({DB_HOST}:{DB_PORT})")
    print("=" * 55)

    try:
        # PostgreSQL 접속
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME,
            user=DB_USER, password=DB_PASS,
            port=DB_PORT, connect_timeout=5,
        )
        cur = conn.cursor()

        for u in TEST_USERS:
            # 동일한 id_name 이 이미 존재하면 INSERT 를 건너뜀 (ON CONFLICT DO NOTHING)
            cur.execute("""
                INSERT INTO users (id_name, pw, name, dob, gender, email, address, phone, type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_name) DO NOTHING
            """, (
                u["id_name"], u["pw"],    u["name"],   u["dob"],
                u["gender"],  u["email"], u["address"], u["phone"],
                u["type"],
            ))

            # 실제로 삽입됐는지 여부 확인
            if cur.rowcount > 0:
                print(f"  [생성됨] id={u['id_name']}  type={u['type']}")
            else:
                print(f"  [스킵됨] id={u['id_name']} 는 이미 존재합니다.")

        conn.commit()
        cur.close()
        conn.close()

        print("\n  테스트 계정 초기화 완료.")
        print("  시험용 로그인 정보:")
        print("    지원자 → ID: test   / PW: test")
        print("    관리자 → ID: admin  / PW: admin")
        print("=" * 55)

    except psycopg2.OperationalError as e:
        # DB 접속 실패 (PostgreSQL 미실행 등)
        print(f"[ERROR] PostgreSQL 접속 실패: {e}")
        print("  PostgreSQL 이 실행 중인지 확인하고, .env 파일의 접속 정보를 점검하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_test_users()
