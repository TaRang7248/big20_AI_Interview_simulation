FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Seoul \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    build-essential \
    curl \
    wget \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    git \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3.10-venv \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10

# 편의상 python/pip 명령을 python3.10/pip3.10으로 매핑
RUN ln -sf /usr/bin/python3.10 /usr/local/bin/python && \
    ln -sf /usr/local/bin/pip3.10 /usr/local/bin/pip || true

WORKDIR /workspace

# 1. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN python3.10 -m pip install --upgrade pip setuptools wheel && \
    python3.10 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    python3.10 -m pip install -r requirements.txt && \
    # ipynb 사용을 위한 Jupyter 설치 (requirements.txt에 포함되어 있으면 중복 설치되어도 무방)
    python3.10 -m pip install jupyter jupyterlab

# (선택) VS Code/Notebook에서 커널 선택이 쉬워지도록 커널 등록
RUN python -m ipykernel install --user --name=docker_env --display-name "Python (Docker)"

# 2. 소스 코드 복사 (구조에 맞게 app 폴더 전체 복사)
COPY app ./app

EXPOSE 8000 8888

# 기본은 FastAPI 실행. (docker-compose에서 command를 override해서 JupyterLab로도 실행 가능)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
