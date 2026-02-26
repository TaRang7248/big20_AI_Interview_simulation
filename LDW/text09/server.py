# AI 면접 시뮬레이션 서버 실행 스크립트

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버 설정
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """서버 준비 완료 후 브라우저 자동 실행"""
    while True:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(1)
            continue
    webbrowser.open(URL)

if __name__ == "__main__":
    # 작업 디렉토리 설정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print(f"[알림] AI 면접 시뮬레이션 시작: {URL}")

    # 브라우저 자동 실행 스레드
    threading.Thread(target=wait_and_open_browser, daemon=True).start()

    # 서버 실행
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False, log_level="info")
