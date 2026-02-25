# AI 면접 시뮬레이션 서버 및 브라우저 자동 실행 스크립트

import uvicorn
import webbrowser
import threading
import time
import socket
import os

# 서버가 실행될 호스트(로컬호스트)와 포트를 설정합니다.
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """
    백그라운드에서 실행되는 함수입니다.
    서버 포트가 활성화될 때까지 기다렸다가,
    서버가 응답하면 자동으로 기본 웹 브라우저를 열어 접속합니다.
    """
    print(f"[알림] 서버 응답을 대기 중입니다 ({URL})...")
    
    # 서버 포트가 정상적으로 열릴 때까지 지속적으로 연결을 시도합니다.
    while True:
        try:
            # 지정된 호스트와 포트로 소켓 연결을 확인합니다.
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            # 연결에 실패하면 1초 동안 기다린 후 다시 시도합니다.
            time.sleep(1)
            continue

    print(f"[알림] 서버가 준비되었습니다. 기본 브라우저를 실행합니다.")
    # 기본 브라우저를 사용하여 서버 주소로 접속합니다.
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트가 실행되는 경로를 현재 작업 디렉토리로 안전하게 설정합니다.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  AI 면접 시뮬레이션 서비스를 시작합니다.")
    print(f"  서비스 접속 주소: {URL}")
    print("  서버를 종료하려면 단축키 [Ctrl + C]를 입력하세요.")
    print("=" * 60)

    # 새로운 스레드를 생성하여 브라우저 자동 실행 대기 함수를 백그라운드에서 실행합니다.
    browser_thread = threading.Thread(target=wait_and_open_browser, daemon=True)
    browser_thread.start()

    # FastAPI 앱을 Uvicorn ASGI 서버를 통해 실행합니다.
    # 서버 실행과 앱 시작을 담당하는 핵심 부분입니다.
    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=False,
            log_level="info",
        )
    except Exception as e:
        # 서버 실행 중 발생할 수 있는 잠재적인 오류를 잡아내고 출력합니다.
        print(f"[오류] 서버 실행 중 다음과 같은 문제가 발생했습니다: {e}")
