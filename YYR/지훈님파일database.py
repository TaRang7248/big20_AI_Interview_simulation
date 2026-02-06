# 🔌 2단계: DB 연결 및 테이블 생성

# models.py에서 정의한 테이블을 실제 PostgreSQL에 생성(Create Table)하는 설정 파일

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from YJH.models import Base

load_dotenv()

# .env에서 주소 가져오기
SQLALCHEMY_DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING")

# 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 세션 로컬 생성 (실제 DB 작업용)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """테이블 생성 함수 (최초 1회 실행 필요)"""
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블 생성 완료!")

# DB 세션 의존성 주입용 함수 (FastAPI에서 사용)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    # 이 파일을 직접 실행하면 테이블을 생성합니다.
    init_db()

