# AI 면접 시뮬레이션 서버 및 브라우저 자동 실행 스크립트

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버 설정: 호스트와 포트 번호를 정의합니다.
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """
    서버가 정상적으로 시작될 때까지 기다렸다가 기본 웹 브라우저를 자동으로 엽니다.
    """
    print(f"[알림] 서버 응답을 대기 중입니다 ({URL})...")
    
    # 서버 포트가 열릴 때까지 1초 간격으로 연결을 시도합니다.
    while True:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(1)
            continue

    print(f"[알림] 서버가 준비되었습니다. 기본 브라우저를 실행합니다.")
    # 시스템 기본 브라우저로 접속 주소를 엽니다.
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트 파일의 위치를 기준으로 작업 디렉토리를 설정합니다.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  AI 면접 시뮬레이션 서비스를 시작합니다.")
    print(f"  접속 주소: {URL}")
    print("  서버 종료: [Ctrl + C]")
    print("=" * 60)

    # 브라우저 자동 실행을 위한 별도 스레드 시작
    browser_thread = threading.Thread(target=wait_and_open_browser, daemon=True)
    browser_thread.start()

    # FastAPI(Uvicorn) 서버 실행
    # 전용 앱 모듈인 app.main:app을 로드합니다.
    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=False,
            log_level="info",
        )
    except Exception as e:
        print(f"[오류] 서버 실행 중 문제가 발생했습니다: {e}")
