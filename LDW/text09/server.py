# AI 면접 시뮬레이션 서버 및 브라우저 실행 스크립트

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버 접속 정보 설정
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """서버가 준비될 때까지 기다린 후 웹 브라우저를 자동으로 실행합니다."""
    while True:
        try:
            # 지정된 호스트와 포트로 연결 시도
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            # 연결 실패 시 1초 대기 후 재시도
            time.sleep(1)
            continue
    
    print(f"[알림] 서버가 준비되었습니다. 브라우저를 실행합니다: {URL}")
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트가 위치한 디렉토리를 현재 작업 디렉토리로 설정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print(f"[시스템] AI 면접 시뮬레이션 서버를 시작합니다...")
    print(f"[정보] 접속 주소: {URL}")

    # 별도 스레드에서 브라우저 자동 실행 대기 로직 시작
    threading.Thread(target=wait_and_open_browser, daemon=True).start()

    # FastAPI 서버(uvicorn) 실행
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False, log_level="info")
