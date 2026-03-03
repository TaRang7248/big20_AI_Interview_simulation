# AI 면접 시뮬레이션 구동을 위한 메인 서버 스크립트
# 서버 실행 및 웹 브라우저 자동 열기 기능만 포함되어 있습니다.

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버 접근을 위한 호스트와 포트 설정
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """서버가 구동되어 응답할 때까지 대기한 후 사용자의 기본 웹 브라우저를 실행하는 함수입니다."""
    while True:
        try:
            # 설정한 호스트와 포트로 소켓 연결을 시도하여 서버가 열렸는지 확인합니다 (타임아웃 1초).
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            # 연결에 실패하면 서버가 아직 준비되지 않은 것이므로 1초 대기 후 다시 시도합니다.
            time.sleep(1)
            continue
    
    # 서버 준비가 완료되면 터미널에 알리고 브라우저를 엽니다.
    print(f"[알림] 서버가 성공적으로 준비되었습니다. 기본 브라우저를 엽니다: {URL}")
    webbrowser.open(URL)

if __name__ == "__main__":
    # 이 스크립트 파일이 위치한 폴더를 현재 작업 디렉토리(Current Working Directory)로 맞춥니다.
    # 이렇게 하면 상대 경로로 작성된 파일이나 모듈을 안정적으로 가져올 수 있습니다.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print(f"[시스템] AI 면접 시뮬레이션 서버 부팅을 시작합니다...")
    print(f"[정보] 웹 브라우저 접속 주소: {URL}")

    # 서버 구동(uvicorn)은 메인 스레드를 차단(block)하므로, 브라우저 자동 실행 로직은 별도의 백그라운드 스레드로 돌립니다.
    threading.Thread(target=wait_and_open_browser, daemon=True).start()

    # FastAPI 앱을 uvicorn WSGI 서버로 실행합니다.
    # "app.main:app"은 app 폴더 안의 main.py 파일에 있는 app 인스턴스를 의미합니다.
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False, log_level="info")
