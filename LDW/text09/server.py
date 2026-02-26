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

# --- 테스트 계정 자동 생성 (시스템 시작 시 호출) ---
def create_test_user():
    """테스트용 계정(test/test)이 없으면 생성합니다."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id_name FROM users WHERE id_name = 'test'")
        if not c.fetchone():
            c.execute('''
                INSERT INTO users (id_name, pw, name, dob, gender, email, address, phone, type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', ('test', 'test', '테스트계정', '1990-01-01', 'male', 'test@example.com', '서울특별시', '010-1234-5678', 'applicant'))
            conn.commit()
            print("[알림] 테스트 계정(test/test)이 생성되었습니다.")
    except Exception as e:
        print(f"[오류] 테스트 계정 생성 중 오류 발생: {e}")
    finally:
        conn.close()

# 이 로직을 app/main.py의 startup 이벤트에 넣거나, 여기서 실행할 수 있습니다.
# 하지만 server.py를 단순하게 유지하기 위해 여기서는 주석으로만 안내하거나 main.py에서 처리하는 것이 좋습니다.
