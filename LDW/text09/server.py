import uvicorn
import webbrowser
import threading
import time
import socket
import os

# ─────────────────────────────────────────────
# AI 면접 시뮬레이션 서버 실행 설정
# ─────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """
    서버 포트가 활성화될 때까지 모니터링한 후 웹 브라우저를 자동으로 엽니다.
    """
    print(f"[시스템] 서버 응답 대기 중 ({URL})...")
    while True:
        try:
            # 8000번 포트로 연결 시도
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)
            continue

    print(f"[시스템] 서버 접속 확인. 브라우저를 실행합니다.")
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트 실행 위치를 현재 파일 경로로 고정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  AI 면접 시뮬레이션 서비스 시작")
    print(f"  접속 주소: {URL}")
    print("  종료하시려면 Ctrl + C 를 누르세요.")
    print("=" * 60)

    # 서버 구동 완료 시점에 자동으로 브라우저를 띄우기 위한 별도 스레드 시작
    threading.Thread(target=wait_and_open_browser, daemon=True).start()

    # FastAPI 앱 실행 (Uvicorn)
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
