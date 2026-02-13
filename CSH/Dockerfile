# =============================================================================
# FastAPI 백엔드 Dockerfile
# =============================================================================
# AI 모의면접 시스템의 Core API + Signaling Server 컨테이너
#
# 빌드: docker build -t interview-fastapi -f CSH/Dockerfile .
# 실행: docker-compose up (docker-compose.yml에서 자동 빌드)
# =============================================================================

# Python 3.11 슬림 이미지 기반 (용량 최적화)
FROM python:3.11-slim

# 시스템 의존성 설치
# - gcc, libpq-dev: psycopg2 (PostgreSQL 드라이버) 빌드에 필요
# - ffmpeg: 미디어 녹화/인코딩에 필요
# - curl: 헬스 체크에 사용
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 (Docker 레이어 캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY CSH/ ./

# 업로드 디렉토리 생성
RUN mkdir -p uploads

# 환경변수 기본값 설정
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

# 포트 노출 (FastAPI)
EXPOSE 8000

# 헬스 체크 설정 — NGINX에서 upstream 상태 모니터링에 활용
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# uvicorn으로 FastAPI 실행
# --workers 2: 멀티 워커 (프로덕션에서는 CPU 코어 수에 맞춰 조절)
# --forwarded-allow-ips '*': NGINX 프록시의 X-Forwarded-* 헤더 신뢰
CMD ["python", "-m", "uvicorn", "integrated_interview_server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", \
     "--forwarded-allow-ips", "*"]
