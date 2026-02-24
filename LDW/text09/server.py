import uvicorn
import webbrowser
import threading
import time
import socket
import os

# ──────────────────────────────────────────────────────────
# AI 면접 시뮬레이션 서버 및 자동 브라우저 실행 스크립트
# ──────────────────────────────────────────────────────────

# 서버 접속 정보 설정 (호스트 및 포트)
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

def wait_and_open_browser():
    """
    서버의 특정 포트가 활성화될 때까지 대기한 후, 
    자동으로 기본 웹 브라우저를 통해 URL에 접속합니다.
    """
    print(f"[알림] 서버 응답을 대기 중입니다 ({URL})...")
    
    # 서버 포트가 열릴 때까지 무한 루프
    while True:
        try:
            # 지정된 호스트와 포트로 소켓 연결 시도
            with socket.create_connection((HOST, PORT), timeout=1):
                break
        except (OSError, ConnectionRefusedError):
            # 연결 실패 시 1초 대기 후 재시도
            time.sleep(1)
            continue

    print(f"[알림] 서버 연결이 확인되었습니다. 브라우저를 실행합니다.")
    # 시스템 기본 웹 브라우저로 URL 열기
    webbrowser.open(URL)

if __name__ == "__main__":
    # 스크립트 실행 경로를 현재 파일이 위치한 디렉토리로 고정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  AI 면접 시뮬레이션 서비스를 시작합니다.")
    print(f"  접속 주소: {URL}")
    print("  종료하려면 [Ctrl + C]를 누르세요.")
    print("=" * 60)

    # 별도의 백그라운드 스레드에서 브라우저 자동 호출 실행
    # 서버 실행(uvicorn.run)이 블로킹 함수이므로 스레드 사용이 필수임
    browser_thread = threading.Thread(target=wait_and_open_browser, daemon=True)
    browser_thread.start()

    # FastAPI/Uvicorn 서버 구동
    # app 패키지의 main 모듈에 정의된 FastAPI 인스턴스(app)를 실행함
    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=False,
            log_level="info",
        )
    except Exception as e:
        print(f"[오류] 서버 실행 중 에러가 발생했습니다: {e}")
