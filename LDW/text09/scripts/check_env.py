"""
check_env.py - AI 면접 시뮬레이션 실행 환경 점검 스크립트

사용법:
    python scripts/check_env.py

점검 항목:
  1. Python 버전
  2. 필수 패키지 설치 여부
  3. FFmpeg 경로 존재 여부
  4. PostgreSQL 접속 가능 여부
  5. 필수 폴더/파일 존재 여부
"""

import sys
import os
import importlib

# ─────────────────────────────────────────────
# 실행 위치를 프로젝트 루트(text09/)로 고정
# ─────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# ─────────────────────────────────────────────
# 결과 출력 헬퍼 함수
# ─────────────────────────────────────────────
def ok(msg):
    print(f"  [OK   ] {msg}")

def warn(msg):
    print(f"  [WARN ] {msg}")

def error(msg):
    print(f"  [ERROR] {msg}")


# ─────────────────────────────────────────────
# 1. Python 버전 확인
# ─────────────────────────────────────────────
def check_python_version():
    print("\n[1] Python 버전 확인")
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 10:
        ok(f"Python {ver_str} (3.10 이상 - 권장)")
    elif v.major == 3 and v.minor >= 8:
        warn(f"Python {ver_str} (3.10 미만 - 일부 기능이 동작하지 않을 수 있습니다)")
    else:
        error(f"Python {ver_str} (지원되지 않는 버전입니다. Python 3.10 이상을 사용하세요)")


# ─────────────────────────────────────────────
# 2. 필수 패키지 설치 여부 확인
# ─────────────────────────────────────────────
def check_packages():
    print("\n[2] 필수 패키지 설치 여부 확인")

    # (패키지 import 이름, 표시 이름) 목록
    packages = [
        ("fastapi",            "FastAPI"),
        ("uvicorn",            "Uvicorn"),
        ("pydantic",           "Pydantic"),
        ("psycopg2",           "psycopg2 (PostgreSQL 드라이버)"),
        ("dotenv",             "python-dotenv"),
        ("sqlalchemy",         "SQLAlchemy"),
        ("google.generativeai","google-generativeai (Gemini)"),
        ("openai",             "OpenAI"),
        ("langchain",          "LangChain"),
        ("edge_tts",           "Edge-TTS"),
        ("cv2",                "OpenCV"),
        ("numpy",              "NumPy"),
        ("librosa",            "Librosa"),
        ("soundfile",          "SoundFile"),
        ("torch",              "PyTorch"),
        ("tqdm",               "tqdm"),
        ("pypdf",              "pypdf (PDF 파싱)"),
    ]

    for import_name, display_name in packages:
        try:
            importlib.import_module(import_name)
            ok(f"{display_name}")
        except ImportError:
            warn(f"{display_name} - 설치되지 않았습니다. (pip install 필요)")


# ─────────────────────────────────────────────
# 3. FFmpeg 경로 확인
# ─────────────────────────────────────────────
def check_ffmpeg():
    print("\n[3] FFmpeg 경로 확인")
    ffmpeg_path = r"C:\ffmpeg\bin"
    ffmpeg_exe  = os.path.join(ffmpeg_path, "ffmpeg.exe")

    if os.path.exists(ffmpeg_exe):
        ok(f"FFmpeg 발견: {ffmpeg_exe}")
    else:
        warn(
            f"FFmpeg 가 {ffmpeg_path} 에 없습니다.\n"
            "       오디오/비디오 분석 기능이 제한될 수 있습니다.\n"
            "       설치: https://www.gyan.dev/ffmpeg/builds/ 에서 다운로드 후\n"
            "       C:\\ffmpeg 폴더에 압축 해제하세요."
        )

    # 시스템 PATH에서도 ffmpeg 탐색
    ffmpeg_in_path = any(
        os.path.exists(os.path.join(p, "ffmpeg.exe"))
        for p in os.environ.get("PATH", "").split(os.pathsep)
    )
    if ffmpeg_in_path:
        ok("FFmpeg 가 시스템 PATH 에서도 발견되었습니다.")


# ─────────────────────────────────────────────
# 4. PostgreSQL 접속 가능 여부 확인
# ─────────────────────────────────────────────
def check_postgres():
    print("\n[4] PostgreSQL 접속 확인")
    try:
        import psycopg2
        from dotenv import load_dotenv

        # .env 로드 (프로젝트 루트 상위 2단계: .../big20/.env)
        env_path = os.path.join(os.path.dirname(os.path.dirname(PROJECT_ROOT)), ".env")
        load_dotenv(env_path)

        db_host = os.getenv("DB_HOST", "localhost")
        db_name = os.getenv("DB_NAME", "interview_db")
        db_user = os.getenv("DB_USER", "postgres")
        db_pass = os.getenv("POSTGRES_PASSWORD", "013579")
        db_port = os.getenv("DB_PORT", "5432")

        conn = psycopg2.connect(
            host=db_host, database=db_name,
            user=db_user, password=db_pass,
            port=db_port, connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0].split(",")[0]
        conn.close()
        ok(f"PostgreSQL 접속 성공: {ver}")
        ok(f"데이터베이스: {db_name}  (호스트: {db_host}:{db_port})")
    except ImportError:
        warn("psycopg2 가 설치되지 않아 DB 접속을 확인할 수 없습니다.")
    except Exception as e:
        error(f"PostgreSQL 접속 실패: {e}")
        print("       DB가 실행 중인지 확인하고, .env 파일의 접속 정보를 점검하세요.")


# ─────────────────────────────────────────────
# 5. 필수 폴더/파일 존재 여부 확인
# ─────────────────────────────────────────────
def check_directories():
    print("\n[5] 필수 폴더/파일 존재 여부 확인")

    # (경로, 설명) 목록
    paths = [
        ("static",                     "정적 파일 폴더 (index.html, app.js, styles.css)"),
        ("static/index.html",          "메인 HTML 파일"),
        ("uploads",                    "업로드 파일 저장 폴더"),
        ("uploads/resumes",            "이력서 저장 폴더"),
        ("uploads/audio",              "오디오 답변 저장 폴더"),
        ("uploads/tts_audio",          "TTS 음성 저장 폴더"),
        ("data",                       "데이터 폴더"),
        ("app/main.py",                "FastAPI 애플리케이션 메인"),
        ("app/config.py",              "설정 파일"),
        ("app/database.py",            "데이터베이스 연결 파일"),
        ("requirements.txt",           "패키지 의존성 목록"),
        ("server.py",                  "서버 실행 진입점"),
    ]

    for rel_path, description in paths:
        full_path = os.path.join(PROJECT_ROOT, rel_path)
        if os.path.exists(full_path):
            ok(f"{rel_path}  ({description})")
        else:
            warn(f"{rel_path} 가 없습니다.  ({description})")


# ─────────────────────────────────────────────
# 메인 실행부
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI 면접 시뮬레이션 - 실행 환경 점검")
    print("=" * 55)

    check_python_version()
    check_packages()
    check_ffmpeg()
    check_postgres()
    check_directories()

    print("\n" + "=" * 55)
    print("  환경 점검 완료.")
    print("  [OK] 항목은 정상, [WARN] 은 주의, [ERROR] 는 오류입니다.")
    print("=" * 55)
