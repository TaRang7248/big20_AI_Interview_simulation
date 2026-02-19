import sys
import os
import psycopg2
from dotenv import load_dotenv

# 상위 디렉토리(../../.env)의 .env 파일 로드
# 현재 위치: .../LDW/text09/migration_package/export_schema.py
# .env 위치: .../LDW/.env (또는 .../big20/.env) - 기존 server.py 등의 위치 고려
# export_db.py에서는 os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 이런 식으로 3단계 위를 참조함.
# 여기서는 migration_package 안에 있으므로 4단계 위가 .env 위치일 수 있음.
# 하지만 export_db.py가 text09에 있었고 3단계 위였으므로, migration_package는 text09 안에 있으니 4단계 위가 맞음.
# 다만 안전하게 text09/export_db.py와 동일한 로직을 사용하여 .env를 찾도록 조정.

current_dir = os.path.dirname(os.path.abspath(__file__))
text09_dir = os.path.dirname(current_dir)
# big20_AI_Interview_simulation/LDW/text09 -> ../../.env 로 가정 (export_db.py 기준)

# export_db.py의 .env 로드 로직 참고:
# load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))
# text09/export_db.py -> text09 -> LDW -> big20_AI_Interview_simulation -> .env
# migration_package/export_schema.py -> migration_package -> text09 -> LDW -> big20_AI_Interview_simulation -> .env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env')
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

OUTPUT_FILE = os.path.join(text09_dir, 'data', 'schema.sql')

def export_schema():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()

        print(f"Exporting schema from {DB_NAME}...")

        # public 스키마의 테이블 목록 조회
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for table in tables:
                table_name = table[0]
                print(f"Processing table: {table_name}")
                
                # 테이블 생성 구문 가져오기 (pg_dump 없이 간단한 방식)
                # 하지만 간단하게 pg_dump를 쓸 수 없는 환경일 수 있으므로,
                # Python 코드로 컬럼 정보를 조회하여 CREATE TABLE 문을 생성하는 방식을 사용하거나,
                # 만약 pg_dump가 설치되어 있다면 subprocess로 실행하는 것이 가장 확실함.
                # 여기서는 Python 코드로 직접 생성하는 방식을 시도 (복잡할 수 있음).
                # 또는 더 간단하게, SQL 덤프가 아닌 '데이터만' 이전하고, 
                # 스키마는 '최초 실행 시 자동 생성'이 안된다면 문제가 됨.
                # 사용자가 '다른 컴퓨터에서 똑같이 컨테이너를 생성'하길 원하므로, 스키마도 필요함.
                
                # 가장 확실한 방법: pg_dump 사용 (docker exec 이용)
                pass

        # ---------------------------------------------------------
        # Python 코드만으로 완벽한 CREATE TABLE 문을 만드는 건 복잡함 (특히 제약조건).
        # 따라서 docker exec를 통해 pg_dump를 실행하는 것이 가장 좋음.
        # 사용자가 Windows 환경이므로 docker 명령어를 subprocess로 실행.
        # ---------------------------------------------------------
        
    except Exception as e:
         print(f"Error accessing DB: {e}")
         print("Switching to docker exec pg_dump approach...")
    
    finally:
        if conn:
            conn.close()

    # pg_dump 실행 (컨테이너 내부에서 실행)
    # 컨테이너 이름: interview_db_container (사용자가 언급함)
    # 스키마만 추출: -s 옵션
    try:
        container_name = "interview_db_container" # 사용자가 명시한 이름
        cmd = f"docker exec {container_name} pg_dump -U {DB_USER} -s {DB_NAME} > \"{OUTPUT_FILE}\""
        
        print(f"Running command: {cmd}")
        # Windows powershell에서 > 리다이렉션이 잘 안될 수 있으므로, 
        # subprocess.run 의 stdout 파라미터 활용 권장하지만, 
        # 여기서는 간단히 os.system 사용 (단, 인코딩 주의)
        
        # os.system은 리다이렉션 처리가 쉘에 따라 다르므로 subprocess 사용
        import subprocess
        
        # 덤프 파일 열기
        with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
             subprocess.run(["docker", "exec", container_name, "pg_dump", "-U", DB_USER, "-s", DB_NAME], 
                            stdout=outfile, check=True)
                            
        print(f"Schema exported successfully to {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"Failed to export schema via docker exec: {e}")
        print("Please ensure 'interview_db_container' is running.")


if __name__ == "__main__":
    export_schema()
