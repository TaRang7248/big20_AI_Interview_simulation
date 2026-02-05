@echo off
chcp 65001 > nul
title AI 모의면접 시스템 시작

echo ============================================================
echo 🎯 AI 모의면접 통합 시스템 시작
echo ============================================================
echo.

:: 현재 디렉토리를 스크립트 위치로 변경
cd /d "%~dp0"

:: Redis 실행 확인
echo [1/4] Redis 상태 확인 중...
redis-cli ping > nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Redis가 실행되지 않았습니다. Redis를 먼저 시작하세요.
    echo     Windows: Redis 서비스 시작 또는 redis-server 실행
    echo.
) else (
    echo ✅ Redis 연결됨
)

:: Ollama 실행 확인
echo [2/4] Ollama LLM 상태 확인 중...
ollama list > nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Ollama가 실행되지 않았습니다.
    echo     ollama serve 명령으로 Ollama를 먼저 시작하세요.
    echo.
) else (
    echo ✅ Ollama 실행 중
)

:: Celery Worker 시작 (새 창에서)
echo [3/4] Celery Worker 시작 중...
start "Celery Worker" cmd /k "cd /d %~dp0 && celery -A celery_app worker --pool=solo --loglevel=info"
echo ✅ Celery Worker 시작됨 (새 창)

:: 잠시 대기 (Celery 초기화 시간)
timeout /t 3 /nobreak > nul

:: FastAPI 서버 시작
echo [4/4] FastAPI 서버 시작 중...
echo.
echo ============================================================
echo 🌐 http://localhost:8000 에서 접속하세요
echo 🎤 화상 면접: http://localhost:8000/interview
echo 💻 코딩 테스트: http://localhost:8000/coding-test
echo ============================================================
echo 종료하려면 Ctrl+C를 누르세요
echo.

uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload

pause
