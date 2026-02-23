"""
server.py - AI 면접 시뮬레이션 서버 실행 진입점

역할:
  1. FastAPI 서버(Uvicorn)를 시작합니다.
  2. 서버 준비가 완료되면 기본 웹 브라우저를 자동으로 엽니다.

비즈니스 로직은 app/ 패키지 내에서 처리합니다.
"""

import uvicorn
import webbrowser
import threading
import time
import sys
import os

# ─────────────────────────────────────────────
# 서버 기동 설정
# ─────────────────────────────────────────────
HOST = "127.0.0.1"   # 로컬 접속만 허용 (외부 공개 시 "0.0.0.0" 으로 변경)
PORT = 8000          # 서비스 포트 번호
URL  = f"http://{HOST}:{PORT}"


def open_browser():
    """
    서버가 완전히 시작된 뒤 시스템 기본 웹 브라우저를 자동으로 엽니다.
    서버 준비 시간(2초)을 기다린 후 브라우저를 실행합니다.
    """
    # 서버가 완전히 시작될 때까지 대기 (단위: 초)
    time.sleep(2)
    print(f"\n[브라우저] {URL} 을(를) 자동으로 엽니다...")
    webbrowser.open(URL)


if __name__ == "__main__":
    # ── 실행 위치를 server.py 가 있는 폴더(text09)로 고정 ──────────────────
    # uvicorn이 상대 경로(static/, uploads/ 등)를 올바로 참조하도록 설정합니다.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 55)
    print("  AI 면접 시뮬레이션 서버를 시작합니다.")
    print(f"  접속 주소: {URL}")
    print("  종료하려면 Ctrl + C 를 누르세요.")
    print("=" * 55)

    # ── 브라우저 자동 실행 스레드 시작 ───────────────────────────────────────
    # daemon=True: 메인 프로세스(서버) 종료 시 자동으로 함께 종료됩니다.
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # ── FastAPI 서버 실행 ─────────────────────────────────────────────────────
    # reload=False: reload 모드를 사용하면 Worker 프로세스가 __main__ 블록을
    # 재실행하여 브라우저가 여러 번 열리는 문제가 발생하므로 비활성화합니다.
    # 코드 수정 후 서버를 재시작하려면 Ctrl+C 후 다시 python server.py 를 실행하세요.
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=False,   # 브라우저 중복 실행 방지를 위해 reload 비활성화
        log_level="info",
    )
