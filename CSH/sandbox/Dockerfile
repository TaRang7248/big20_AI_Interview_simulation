FROM python:3.10-slim

# ========== 컴파일러 및 런타임 설치 ==========
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    default-jdk-headless \
    nodejs \
    coreutils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ========== 보안 강화 ==========
# setuid/setgid 바이너리 제거 (권한 상승 방지)
RUN find / -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# 불필요한 네트워크 도구 제거
RUN rm -f /usr/bin/wget /usr/bin/curl 2>/dev/null || true

# 제한된 사용자 생성 (non-root)
RUN groupadd -r sandbox && \
    useradd -r -g sandbox -d /home/sandbox -s /usr/sbin/nologin sandbox && \
    mkdir -p /home/sandbox && \
    chown sandbox:sandbox /home/sandbox

# 작업 디렉토리
WORKDIR /tmp

# 비-루트 사용자로 전환
USER sandbox

# 기본 명령어
CMD ["bash"]
