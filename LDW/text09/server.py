import uvicorn
import webbrowser
import threading
import time
import os
from app.main import app

def open_browser():
    """
    서버 시작 후 기본 웹 브라우저를 자동으로 엽니다.
    """
    # 서버가 시작될 시간을 잠시 기다림
    time.sleep(3)
    url = "http://127.0.0.1:8000"
    print(f"웹 브라우저를 실행합니다: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    # 브라우저 자동 실행을 위한 별도 스레드 시작
    threading.Thread(target=open_browser, daemon=True).start()
    
    # FastAPI 서버 실행
    # host: 접속 허용 IP (127.0.0.1은 로컬 접속)
    # port: 서비스 포트 번호
    # reload: 코드 변경 시 자동 재시작 (개발 모드)
    print("AI 면접 시뮬레이션 서버를 시작합니다...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
