# AI 면접 시뮬레이션 서버 및 브라우저 자동 실행 스크립트

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버 접속 정보 설정 (호스트 및 포트)
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """
    서버 포트가 활성화될 때까지 대기한 후 자동으로 웹 브라우저를 실행하여 접속합니다.
    """
    print(f"[알림] 서버 응답을 대기 중입니다 ({URL})...")
    
    # 서버 포트가 열릴 때까지 연결 시도
    while True:
        try:
            # 소켓을 통해 포트 오픈 여부 확인
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            # 연결 실패 시 1초 대기 후 재시도
            time.sleep(1)
            continue

    print(f"[알림] 서버가 준비되었습니다. 브라우저를 실행합니다.")
    # 기본 브라우저로 접속 주소 열기
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트 실행 경로를 현재 디렉토리로 설정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  AI 면접 시뮬레이션 서비스를 실행합니다.")
    print(f"  접속 주소: {URL}")
    print("  종료하려면 [Ctrl + C]를 입력하세요.")
    print("=" * 60)

    # 백그라운드 스레드에서 브라우저 자동 실행 대기
    browser_thread = threading.Thread(target=wait_and_open_browser, daemon=True)
    browser_thread.start()

    # FastAPI 앱 실행 (Uvicorn 서버)
    # server.py는 서버 실행 및 웹 브라우저 자동 실행 기능만 유지합니다.
    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=False,
            log_level="info",
        )
    except Exception as e:
        # 실행 중 발생한 오류 출력
        print(f"[오류] 서버 실행 중 문제가 발생했습니다: {e}")
