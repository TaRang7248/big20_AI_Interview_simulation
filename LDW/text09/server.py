import uvicorn
import webbrowser
from threading import Timer
from app.config import logger
from app.main import app
import os
import platform

def open_browser():
    """
    애플리케이션 URL을 크롬 브라우저로 엽니다.
    """
    url = "http://localhost:5000"
    logger.info(f"크롬 브라우저에서 {url}을 엽니다.")
    
    try:
        if platform.system() == "Windows":
            # Windows 환경의 Chrome 실행 파일 경로
            chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
            webbrowser.get(chrome_path).open(url)
        elif platform.system() == "Darwin":
            # macOS 환경의 Chrome 실행
            webbrowser.get("chrome").open(url)
        else:
            webbrowser.get("google-chrome").open(url)
    except Exception as e:
        logger.error(f"브라우저 실행 실패 (크롬을 찾을 수 없거나 오류 발생): {e}")
        # 크롬을 찾을 수 없을 때 시스템 기본 브라우저로 열기 시도
        try:
            webbrowser.open(url)
            logger.info("기본 브라우저로 열기를 시도했습니다.")
        except Exception as fallback_e:
            logger.error(f"기본 브라우저 실행 실패: {fallback_e}")

if __name__ == "__main__":
    logger.info("AI 면접 시뮬레이션 서버를 시작합니다...")
    
    # 서버 준비 시간을 보장하기 위해 1.5초 후 브라우저 열기 타이머 시작
    Timer(1.5, open_browser).start()
    
    # Uvicorn 서버 실행
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=False)
