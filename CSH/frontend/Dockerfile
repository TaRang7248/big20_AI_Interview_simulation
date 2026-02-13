# =============================================================================
# Next.js 프론트엔드 Dockerfile
# =============================================================================
# AI 모의면접 시스템의 Candidate App + Recruiter Dashboard 컨테이너
#
# 빌드: docker build -t interview-nextjs -f CSH/frontend/Dockerfile CSH/frontend/
# 실행: docker-compose up (docker-compose.yml에서 자동 빌드)
# =============================================================================

# Node.js 20 LTS 기반 (안정성 우선)
FROM node:20-alpine

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 (Docker 레이어 캐싱 활용)
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# 소스 코드 복사
COPY . .

# 환경변수 설정
# NGINX 뒤에서 동작하므로 API URL을 fastapi 서비스로 지정
ENV NEXT_PUBLIC_API_URL=http://fastapi:8000
ENV NODE_ENV=production

# Next.js 빌드
RUN npm run build

# 포트 노출
EXPOSE 3000

# Next.js 프로덕션 서버 시작
CMD ["npm", "start"]
