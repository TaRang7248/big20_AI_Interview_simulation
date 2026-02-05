@echo off
chcp 65001 > nul
title AI 모의면접 - 사전 서비스 시작

echo ============================================================
echo 🔧 AI 모의면접 사전 서비스 시작 (Redis + Ollama)
echo ============================================================
echo.

:: Redis 시작 (새 창)
echo [1/2] Redis 시작 중...
start "Redis Server" cmd /k "redis-server"
echo ✅ Redis 시작됨

timeout /t 2 /nobreak > nul

:: Ollama 시작 (새 창)
echo [2/2] Ollama 시작 중...
start "Ollama Server" cmd /k "ollama serve"
echo ✅ Ollama 시작됨

echo.
echo ============================================================
echo ✅ 사전 서비스 시작 완료!
echo.
echo 다음 단계:
echo   1. 잠시 기다린 후 (약 10초)
echo   2. start_interview.bat 실행
echo ============================================================
echo.

timeout /t 5
