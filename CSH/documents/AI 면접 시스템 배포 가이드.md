# AI 모의면접 시스템 배포 가이드

현재 프로젝트의 인프라 구성을 전체적으로 파악했습니다. Docker, NGINX, SSL, CORS 등 배포 준비가 상당 부분 갖춰져 있습니다. 아래에 배포를 위한 체크리스트를 정리합니다.

현재 프로젝트에는 `docker-compose.yml`, `CSH/Dockerfile`, `CSH/frontend/Dockerfile`, `CSH/nginx/nginx.conf` 등 배포 인프라가 이미 갖춰져 있습니다. 아래는 **로컬 개발 → 프로덕션 배포**까지 필요한 작업 목록입니다.

---

## Phase 1: 보안 점검 (필수, 배포 전)

| # | 작업 | 현황 | 조치 |
|---|------|------|------|
| 1 | **API 키 노출 차단** | `.env`에 실제 키가 포함되어 있음 | `.env`가 `.gitignore`에 포함되어 있는지 확인. **이미 커밋된 키는 모두 로테이션(재발급)** 필요 |
| 2 | **JWT Secret 교체** | 현재 고정 값 사용 | `openssl rand -hex 32`로 새로운 시크릿 생성 |
| 3 | **AES 암호화 키 교체** | `.env`에 고정 값 | 프로덕션 전용 키 새로 생성 |
| 4 | **CORS 도메인 제한** | `ALLOWED_ORIGINS`에 `localhost` 포함 | 프로덕션 도메인만 명시 (예: `https://interview.example.com`) |
| 5 | **DEBUG 모드 비활성화** | `STT_RUNTIME_DEBUG` 등 존재 | 프로덕션에서 `NEXT_PUBLIC_STT_DEBUG=0` 확인 |

---

## Phase 2: 인프라 선택 및 준비

### Option A: 클라우드 VM (GCP/AWS/NCP) — 권장

Ollama LLM 추론에 **GPU가 필요**하므로 GPU VM이 가장 현실적입니다.

| 리소스 | 최소 사양 | 권장 사양 |
|-------|----------|----------|
| GPU | NVIDIA T4 (16GB VRAM) | A10G (24GB VRAM) |
| CPU | 8 vCPU | 16 vCPU |
| RAM | 32GB | 64GB |
| Storage | 100GB SSD | 200GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

```bash
# 서버 기본 설정
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin nvidia-driver-535 nvidia-container-toolkit
sudo systemctl enable docker

# Ollama 설치 (GPU 서버에 직접)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull exaone3.5:7.8b
ollama pull nomic-embed-text
ollama pull hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q3_K_M
```

### Option B: Docker Compose 단일 서버 (현재 구성 활용)

현재 `docker-compose.yml`이 이미 완성되어 있어, 아래 명령으로 바로 배포 가능:

```bash
# 1) 프로덕션용 .env 생성
cp CSH/.env.example .env
# → 실제 키 값 입력

# 2) SSL 인증서 생성
cd CSH/nginx && bash generate-certs.ps1  # 또는 Let's Encrypt 사용

# 3) 전체 시스템 시작
docker compose up --build -d
```

---

## Phase 3: SSL 인증서 (Let's Encrypt)

현재 `CSH/nginx/nginx.conf`에 self-signed 인증서 경로가 설정되어 있습니다. 프로덕션에서는 **Let's Encrypt** 무료 인증서를 사용합니다:

```bash
# Certbot 설치 및 인증서 발급
sudo apt install certbot
sudo certbot certonly --standalone -d interview.example.com

# nginx.conf의 인증서 경로 수정
# ssl_certificate     /etc/letsencrypt/live/interview.example.com/fullchain.pem;
# ssl_certificate_key /etc/letsencrypt/live/interview.example.com/privkey.pem;
```

또는 `docker-compose.yml`에 Certbot 컨테이너를 추가:

```yaml
certbot:
  image: certbot/certbot
  volumes:
    - ./CSH/nginx/ssl:/etc/letsencrypt
    - certbot_www:/var/www/certbot
  command: certonly --webroot -w /var/www/certbot -d interview.example.com --agree-tos -m admin@example.com
```

---

## Phase 4: 환경변수 설정

프로덕션 `.env` 파일에서 반드시 변경해야 할 항목:

```bash
# ── 반드시 변경 ──
APP_ENV=production
JWT_SECRET_KEY=<새로 생성한 시크릿>
AES_ENCRYPTION_KEY=<새로 생성한 키>
POSTGRES_PASSWORD=<강력한 비밀번호>
ALLOWED_ORIGINS=https://interview.example.com

# ── Ollama (Docker 내부 → 호스트 접근) ──
OLLAMA_HOST=http://host.docker.internal:11434  # Docker Desktop
# 또는
OLLAMA_HOST=http://172.17.0.1:11434            # Linux Docker

# ── WebSocket URL (프론트엔드) ──
# CSH/frontend/.env.local 수정
NEXT_PUBLIC_WS_URL=wss://interview.example.com
NEXT_PUBLIC_API_URL=https://interview.example.com
```

---

## Phase 5: 데이터베이스 마이그레이션

```bash
# PostgreSQL + pgvector 초기 설정 (docker-compose가 자동 생성)
# 필요 시 초기 스키마 적용:
docker compose exec fastapi python -c "
from integrated_interview_server import engine, Base
Base.metadata.create_all(bind=engine)
print('DB 테이블 생성 완료')
"
```

---

## Phase 6: 도메인 및 DNS

| 항목 | 설정 |
|------|------|
| 도메인 구매 | `interview.example.com` |
| DNS A 레코드 | `interview.example.com → <서버 IP>` |
| 방화벽 포트 | 80 (HTTP), 443 (HTTPS), 22 (SSH) |

---

## Phase 7: 모니터링 및 로그

```bash
# 컨테이너 로그 확인
docker compose logs -f fastapi
docker compose logs -f nginx

# 헬스 체크
curl https://interview.example.com/health
```

향후 고려사항:
- **로그 수집**: ELK Stack 또는 Grafana Loki
- **메트릭 모니터링**: Prometheus + Grafana
- **에러 추적**: Sentry

---

## Phase 8: CI/CD (선택)

GitHub Actions 등으로 자동 배포 파이프라인 구축:

```yaml
# .github/workflows/deploy.yml (예시)
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to server
        run: |
          ssh user@server "cd /app && git pull && docker compose up --build -d"
```

---

## 배포 순서 요약

```
1. 보안 점검 → API 키 로테이션, .env 정리
2. 서버 프로비저닝 → GPU VM + Docker + Ollama 설치
3. 도메인/DNS → A 레코드 설정
4. SSL 인증서 → Let's Encrypt 발급
5. 환경변수 → 프로덕션 .env 작성
6. 배포 → docker compose up --build -d
7. DB 초기화 → 테이블 생성/마이그레이션
8. 검증 → 헬스 체크 + 기능 테스트
```

> **⚠️ 가장 시급한 것은 Phase 1 (보안)입니다.** 현재 `.env`에 노출된 OPENAI, Deepgram, Anthropic, Hume API 키는 모두 재발급해야 합니다.
