import uvicorn
import webbrowser
import threading
import time
import socket
import os

# ─────────────────────────────────────────────
# 서버 기동 설정
# ─────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_for_server_and_open_browser():
    """
    서버 포트(8000)가 활성화될 때까지 체크한 후 브라우저를 엽니다.
    """
    while True:
        try:
            # 소켓을 생성하여 서버 포트에 접속 시도
            with socket.create_connection((HOST, PORT), timeout=1):
                # 접속 성공 시 서버가 준비된 것으로 간주
                break
        except (OSError, ConnectionRefusedError):
            # 서버가 아직 준비되지 않았으면 0.5초 대기 후 재시도
            time.sleep(0.5)
            continue

    print(f"\n[시스템] 서버 준비 완료. 브라우저({URL})를 실행합니다...")
    webbrowser.open(URL)

if __name__ == "__main__":
    # 실행 위치 고정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 55)
    print("  AI 면접 시뮬레이션 서버를 시작합니다.")
    print(f"  접속 주소: {URL}")
    print("  종료하려면 Ctrl + C 를 누르세요.")
    print("=" * 55)

    # ── 브라우저 감시 스레드 시작 ───────────────────────────────────────
    # 이제 10초를 기다리는 대신, 서버가 켜지는 순간을 감시합니다.
    browser_thread = threading.Thread(target=wait_for_server_and_open_browser, daemon=True)
    browser_thread.start()

    # ── FastAPI 서버 실행 ─────────────────────────────────────────────────────
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )