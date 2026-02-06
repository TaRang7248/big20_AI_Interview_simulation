import asyncio
import os
from sqlalchemy import text
from IMH.IMH_with_api.database import engine
from dotenv import load_dotenv

load_dotenv()

async def verify_db():
    print("--- DB 연결 및 구조 검증 시작 ---")
    try:
        async with engine.connect() as conn:
            # 1. 연결 테스트
            result = await conn.execute(text("SELECT 1"))
            print("[OK] DB 연결 성공")

            # 2. PGVector 확장 확인
            result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            ext = result.fetchone()
            if ext:
                print("[OK] PGVector 확장 활성화 확인")
            else:
                print("[ERROR] PGVector 확장이 활성화되지 않았습니다.")

            # 3. 테이블 존재 여부 확인
            expected_tables = [
                "users", "user_info", "resumes", "interviews", 
                "messages", "questions", "interview_evaluations", 
                "evaluation_scores", "whiteboard_notes"
            ]
            
            result = await conn.execute(text("""
                SELECT tablename FROM pg_catalog.pg_tables 
                WHERE schemaname = 'public';
            """))
            actual_tables = [row[0] for row in result]
            
            for table in expected_tables:
                if table in actual_tables:
                    print(f"[OK] 테이블 확인: {table}")
                else:
                    print(f"[ERROR] 테이블 누락: {table}")

            # 4. 주요 컬럼 구조 확인 (샘플: interviews)
            print("\n--- 'interviews' 테이블 구조 확인 ---")
            result = await conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'interviews';
            """))
            for row in result:
                print(f"  - {row[0]}: {row[1]}")

            print("\n--- 'questions' 테이블 벡터 컬럼 확인 ---")
            result = await conn.execute(text("""
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'questions' AND column_name = 'embedding';
            """))
            row = result.fetchone()
            if row:
                print(f"  - {row[0]}: {row[1]} (udt: {row[2]})")

    except Exception as e:
        print(f"[CRITICAL ERROR] 검증 중 오류 발생: {e}")
    finally:
        await engine.dispose()
        print("--- 검증 종료 ---")

if __name__ == "__main__":
    asyncio.run(verify_db())
