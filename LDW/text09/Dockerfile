# Python 3.10 이미지 사용
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# python-multipart 추가 설치 (FastAPI 의존성)
RUN pip install --no-cache-dir python-multipart

# pip 업그레이드 및 torch CPU 버전 미리 설치 (빌드 속도 및 안정성 향상)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# requirements.txt 복사 및 설치
COPY requirements.txt .
# requirements.txt 내의 패키지 설치 (시간이 오래 걸릴 수 있음)
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
# 현재 디렉토리(LDW/text09)의 모든 파일을 컨테이너의 /app으로 복사
COPY . .

# 포트 5000 노출
EXPOSE 5000

# 서버 실행
CMD ["python", "server.py"]
