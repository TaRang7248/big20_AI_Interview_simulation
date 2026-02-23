"""
AI 모의면접 통합 시스템 (메인서버)
========================
기능 통합:
1. LLM 기반 면접 질문 생성 (Ollama/Qwen3)
2. TTS 서비스 (Hume AI)
3. STT 서비스 (Deepgram)
4. 화상 면접 + 감정 분석 (DeepFace + WebRTC)
5. 이력서 RAG (PostgreSQL + PGVector)
6. STAR 기법 기반 리포트 생성

실행 방법:
    터미널에 아래 명령어를 입력
    uvicorn integrated_interview_server:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import functools
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx

# WebRTC
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole

# 환경 설정
from dotenv import load_dotenv

# FastAPI 및 웹 프레임워크
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# PostgreSQL 데이터베이스
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
sys.path.append(current_dir)

load_dotenv()

# JSON Resilience 유틸리티
from json_utils import parse_evaluation_json

# 지연 시간 측정 및 SLA 모니터링 (REQ-N-001: 초저지연 1.5초 이내)
from latency_monitor import latency_monitor
from prompt_templates import (
    EVALUATION_PROMPT as SHARED_EVALUATION_PROMPT,
)
from prompt_templates import (
    INTERVIEWER_PROMPT as SHARED_INTERVIEWER_PROMPT,
)
from prompt_templates import (
    MAX_QUESTIONS as SHARED_MAX_QUESTIONS,
)
from prompt_templates import (
    build_question_prompt,
)

# 보안 유틸리티 (bcrypt 비밀번호 해싱, JWT 토큰 인증, TLS, AES-256 파일 암호화)
from security import (
    AES_ENCRYPTION_AVAILABLE,
    create_access_token,
    decode_access_token,
    decrypt_file,
    # REQ-N-003: 저장 데이터 AES-256-GCM 암호화
    encrypt_file,
    get_current_user,
    get_current_user_optional,
    get_ssl_context,
    hash_password,
    is_encrypted_file,
    needs_rehash,
    verify_password,
)

# ========== 설정 ==========
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
DEFAULT_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
DEFAULT_LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "4096"))
# 면접 LLM 최대 생성 토큰 수 — 무한 생성 방지
# ⚡ 512토큰으로 제한: 면접 질문은 100~300토큰이면 충분하며,
#    2048 설정은 불필요한 생성 시간을 초래하여 타임아웃의 주요 원인이 됨
DEFAULT_LLM_NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT", "512"))
# 면접 LLM 호출 타임아웃 (초) — GTX 1660 VRAM 압박 시 무기한 hang 방지
# 60초 내 응답 없으면 폴백 질문으로 전환하여 사용자 대기 시간 최소화
LLM_TIMEOUT_SEC = int(os.getenv("LLM_TIMEOUT_SEC", "60"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 소셜 로그인 설정
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000")

# 업로드 디렉토리 설정
UPLOAD_DIR = os.path.join(current_dir, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ========== 비동기 처리를 위한 ThreadPoolExecutor ==========
# LLM, RAG, DeepFace 등 CPU/IO 바운드 작업을 비블로킹으로 처리
# ⚡ max_workers=2: GTX 1660(6GB VRAM) 환경에서 4개 동시 LLM 호출은
#    GPU 메모리 경합을 유발하여 전체 응답 속도가 저하됨
LLM_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm_worker")
RAG_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag_worker")
VISION_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vision_worker")


async def run_in_executor(executor: ThreadPoolExecutor, func, *args, **kwargs):
    """동기 함수를 ThreadPoolExecutor에서 비동기로 실행"""
    loop = asyncio.get_event_loop()
    if kwargs:
        func_with_kwargs = functools.partial(func, **kwargs)
        return await loop.run_in_executor(executor, func_with_kwargs, *args)
    return await loop.run_in_executor(executor, func, *args)


def sanitize_user_input(text: str) -> str:
    """사용자 입력 텍스트 정제 (STT 중복 누적 완화)

    - 공백/개행 정규화
    - 연속 중복 문장 제거
    - 연속 중복 구문(2~6어절) 제거
    """
    if not text:
        return ""

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    parts = [p.strip() for p in re.split(r"([.!?。！？])", normalized) if p.strip()]
    merged_sentences: List[str] = []
    buffer = ""
    for part in parts:
        if part in ".!?。！？":
            buffer += part
            if buffer.strip():
                merged_sentences.append(buffer.strip())
            buffer = ""
        else:
            if buffer:
                buffer += " " + part
            else:
                buffer = part
    if buffer.strip():
        merged_sentences.append(buffer.strip())

    dedup_sentences: List[str] = []
    previous = ""
    for sentence in merged_sentences:
        sentence_key = re.sub(r"\s+", " ", sentence).strip().lower()
        if sentence_key and sentence_key != previous:
            dedup_sentences.append(sentence)
            previous = sentence_key

    cleaned = " ".join(dedup_sentences) if dedup_sentences else normalized

    # 연속 중복 구문 제거 (예: "redis 캐시를 사용 redis 캐시를 사용")
    tokens = cleaned.split()
    compact_tokens: List[str] = []
    index = 0
    while index < len(tokens):
        removed = False
        for span in range(6, 1, -1):
            if index + (2 * span) <= len(tokens):
                left = tokens[index : index + span]
                right = tokens[index + span : index + (2 * span)]
                if left == right:
                    compact_tokens.extend(left)
                    index += 2 * span
                    removed = True
                    break
        if not removed:
            compact_tokens.append(tokens[index])
            index += 1

    return " ".join(compact_tokens).strip()


async def run_llm_async(llm, messages):
    """LLM invoke를 비동기로 실행 (이벤트 루프 블로킹 방지 + 타임아웃)

    GTX 1660 등 저사양 GPU에서 VRAM 압박 시 LLM이 무기한 hang할 수 있으므로
    asyncio.wait_for로 LLM_TIMEOUT_SEC 초 내에 응답을 강제합니다.
    """
    # ⚡ 재시도 제거: 타임아웃 후 재시도는 이미 GPU가 과부하 상태이므로
    #    두 번째 시도도 실패할 확률이 높고, 사용자 대기 시간만 2배(120초)로 늘어남.
    #    대신 즉시 폴백 질문으로 전환하여 사용자 대기를 최소화함.
    try:
        return await asyncio.wait_for(
            run_in_executor(LLM_EXECUTOR, llm.invoke, messages),
            timeout=LLM_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        print(f"⏰ [LLM] 타임아웃 ({LLM_TIMEOUT_SEC}초 초과) — 폴백 응답 반환")
        raise TimeoutError(f"LLM 응답 시간 초과 ({LLM_TIMEOUT_SEC}초)")


async def run_rag_async(retriever, query):
    """RAG retriever invoke를 비동기로 실행 (nomic-embed-text 최적화: search_query 접두사 적용)"""
    prefixed_query = f"search_query: {query}"
    docs = await run_in_executor(RAG_EXECUTOR, retriever.invoke, prefixed_query)
    # search_document: 접두사 제거
    for doc in docs:
        if doc.page_content.startswith("search_document: "):
            doc.page_content = doc.page_content[len("search_document: ") :]
    return docs


async def run_deepface_async(img, actions=None):
    """DeepFace analyze를 비동기로 실행 (CPU 바운드 작업)"""
    if actions is None:
        actions = ["emotion"]
    return await run_in_executor(
        VISION_EXECUTOR, DeepFace.analyze, img, actions=actions, enforce_detection=False
    )


# ========== PostgreSQL 데이터베이스 설정 ==========
# DATABASE_URL 또는 POSTGRES_CONNECTION_STRING 환경변수가 있으면 우선 사용
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")

# 없으면 개별 환경변수로 조합
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "interview_db")
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(
    f"🔗 DB 연결 시도: {DATABASE_URL.replace(DATABASE_URL.split(':')[2].split('@')[0], '****')}"
)

# DB 연결 에러 메시지 저장용
DB_ERROR_MSG = None

# DB 연결 시도
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    # 사용자 테이블 모델
    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, index=True)
        email = Column(String(255), unique=True, nullable=False)
        role = Column(
            String(20), nullable=False, default="candidate"
        )  # candidate, recruiter
        password_hash = Column(String(255), nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow)
        name = Column(String(50), nullable=True)
        birth_date = Column(String(10), nullable=True)  # DATE 타입이지만 문자열로 처리
        gender = Column(String(10), nullable=True)
        address = Column(String(500), nullable=True)
        phone = Column(String(20), nullable=True)  # 전화번호 (예: 010-1234-5678)

    # ── 사용자 이력서 영구 저장 테이블 ──
    # 이력서 메타데이터를 DB에 영구 저장하여, 서버 재시작/재로그인 시에도
    # 이전에 업로드한 이력서를 자동 복원할 수 있도록 합니다.
    class UserResume(Base):
        __tablename__ = "user_resumes"

        id = Column(Integer, primary_key=True, index=True)
        user_email = Column(
            String(255), nullable=False, index=True
        )  # 사용자 이메일 (users.email 참조)
        filename = Column(
            String(500), nullable=False
        )  # 원본 파일명 (예: 홍길동_이력서.pdf)
        file_path = Column(
            String(1000), nullable=False
        )  # 서버 저장 경로 (uploads/xxx.pdf)
        file_size = Column(Integer, nullable=True)  # 파일 크기 (bytes)
        uploaded_at = Column(DateTime, default=datetime.utcnow)  # 업로드 일시
        is_active = Column(
            Integer, nullable=False, default=1
        )  # 활성 여부 (1=사용 중, 0=삭제됨)

    # 채용 공고 테이블 모델 (ERD: job_postings)
    class JobPosting(Base):
        __tablename__ = "job_postings"

        id = Column(Integer, primary_key=True, index=True)
        recruiter_email = Column(
            String(255), nullable=False
        )  # 작성자(인사담당자) 이메일
        title = Column(String(200), nullable=False)  # 공고 제목
        company = Column(String(100), nullable=False)  # 회사명
        location = Column(String(200), nullable=True)  # 근무지
        job_category = Column(
            String(50), nullable=True
        )  # 직무 분야 (backend, frontend 등)
        experience_level = Column(
            String(30), nullable=True
        )  # 경력 수준 (신입, 1~3년 등)
        description = Column(Text, nullable=False)  # 상세 내용 (직무 설명, 자격요건 등)
        salary_info = Column(String(100), nullable=True)  # 급여 정보
        status = Column(String(20), nullable=False, default="open")  # open, closed
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        deadline = Column(String(10), nullable=True)  # 마감일 (YYYY-MM-DD)

    # 연결 테스트
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    # 테이블 자동 생성 (존재하지 않는 테이블만 생성)
    Base.metadata.create_all(bind=engine)

    DB_AVAILABLE = True
    print("✅ PostgreSQL 데이터베이스 연결됨")
except Exception as e:
    DB_AVAILABLE = False
    DB_ERROR_MSG = str(e)
    print(f"⚠️ PostgreSQL 데이터베이스 연결 실패: {e}")
    print(f"   → DATABASE_URL 확인: {DATABASE_URL[:30]}...")
    import traceback

    traceback.print_exc()
    print("   → 메모리 저장소를 사용합니다.")

# ========== FastAPI 앱 초기화 ==========
app = FastAPI(
    title="AI 모의면접 통합 시스템",
    description="TTS, STT, LLM, 화상 면접, 감정 분석을 통합한 AI 면접 시스템",
    version="1.0.0",
)


# ───── 헬스 체크 엔드포인트 ─────
@app.get("/health")
async def health_check():
    """시스템 헬스 체크 — Next.js 프록시 및 로드밸런서에서 사용"""
    return {
        "status": "healthy",
        "db_available": DB_AVAILABLE,
        "version": "1.0.0",
    }


# ───── 임시 진단 엔드포인트 (DB 연결 상태 확인) ─────
@app.get("/api/debug/db")
async def debug_db_status():
    """DB 연결 상태 진단용 (개발 전용)"""
    return {
        "db_available": DB_AVAILABLE,
        "db_error": DB_ERROR_MSG,
        "database_url_prefix": DATABASE_URL[:40] + "..." if DATABASE_URL else None,
        "env_postgres_conn": os.getenv("POSTGRES_CONNECTION_STRING", "NOT_SET")[:40],
    }


# CORS 설정 (운영 환경에서는 ALLOWED_ORIGINS 환경변수로 허용 도메인 지정)
# 예: ALLOWED_ORIGINS=https://example.com,https://app.example.com
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").strip()
if ALLOWED_ORIGINS:
    cors_origins = [
        origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()
    ]
else:
    # 개발 환경: localhost 변형만 허용
    cors_origins = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
    ]

print(f"[CORS] 허용 Origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept"],
)

# ========== Trusted Proxy 미들웨어 (SAD: API Gateway 연동) ==========
# NGINX가 전달하는 X-Forwarded-For, X-Real-IP 헤더를 신뢰하여
# 원본 클라이언트 IP를 정확히 추적합니다.
# - 로깅, Rate Limiting, 보안 감사(Audit) 시 실제 클라이언트 IP 사용
# - NGINX에서 설정한 X-Request-ID를 전파하여 분산 트레이싱 지원
TRUSTED_PROXIES = os.getenv(
    "TRUSTED_PROXIES", "127.0.0.1,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16"
).split(",")


@app.middleware("http")
async def trusted_proxy_middleware(request: Request, call_next):
    """NGINX API Gateway에서 전달된 프록시 헤더를 처리합니다.

    SAD 설계서 Gateway Layer 연동:
    - X-Real-IP: NGINX가 설정한 실제 클라이언트 IP
    - X-Forwarded-For: 프록시 체인을 통과한 IP 목록
    - X-Forwarded-Proto: 원본 요청의 프로토콜 (http/https)
    - X-Request-ID: NGINX가 부여한 요청 추적 ID (분산 트레이싱)
    """
    # NGINX가 전달한 X-Request-ID를 request.state에 저장 (로깅/트레이싱에 활용)
    nginx_request_id = request.headers.get("x-request-id")
    if nginx_request_id:
        request.state.nginx_request_id = nginx_request_id

    # X-Real-IP 헤더가 있으면 실제 클라이언트 IP로 사용
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        request.state.client_ip = real_ip
    else:
        # X-Forwarded-For에서 첫 번째 IP 추출 (최초 클라이언트)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            request.state.client_ip = forwarded_for.split(",")[0].strip()
        else:
            request.state.client_ip = (
                request.client.host if request.client else "unknown"
            )

    response = await call_next(request)

    # 응답에 X-Request-ID 전파 (프론트엔드 디버깅 지원)
    if nginx_request_id:
        response.headers["X-Request-ID"] = nginx_request_id

    return response


# ========== 지연 시간 측정 미들웨어 (REQ-N-001) ==========
@app.middleware("http")
async def latency_measurement_middleware(request: Request, call_next):
    """모든 /api/** 요청의 응답 시간을 자동으로 측정하여 SLA(1.5초) 위반을 감지합니다.

    SRS REQ-N-001: STT + LLM 추론을 포함한 전체 응답 지연이 1.5초를 초과하면 안 됨.
    - 각 요청에 고유 request_id를 부여하여 단계별(Phase) 측정과 연결
    - 정적 파일, 프록시 등 비-API 요청은 측정 대상에서 제외
    """
    path = request.url.path

    # API 요청만 측정 대상 (/api/** 경로)
    if not path.startswith("/api/"):
        return await call_next(request)

    # 모니터링 API 자체는 측정에서 제외 (재귀 방지)
    if path.startswith("/api/monitoring/"):
        return await call_next(request)

    # 고유 요청 ID 부여 (Phase 측정과 연결에 사용)
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # 지연 시간 기록 (SLA 위반 시 자동 경고 로깅)
    latency_monitor.record(
        endpoint=path,
        method=request.method,
        latency_ms=elapsed_ms,
        status_code=response.status_code,
        request_id=request_id,
    )

    # 응답 헤더에 서버 처리 시간 추가 (클라이언트 디버깅용)
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    return response


# ========== 모니터링 API (REQ-N-001 SLA 검증) ==========
@app.get("/api/monitoring/latency")
async def get_latency_dashboard():
    """
    지연 시간 모니터링 대시보드 API

    SRS REQ-N-001 준수 여부를 실시간으로 검증합니다.
    - 전체/엔드포인트별 SLA 준수율
    - 평균·최소·최대 응답 시간
    - 최근 SLA 위반 내역 및 단계별 소요 시간
    """
    return latency_monitor.get_dashboard()


@app.delete("/api/monitoring/latency/reset")
async def reset_latency_stats():
    """모니터링 통계를 초기화합니다."""
    latency_monitor.reset()
    return {"message": "지연 시간 통계가 초기화되었습니다."}


# 정적 파일 마운트
static_dir = os.path.join(current_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ========== Next.js 프론트엔드 프록시 설정 ==========
NEXTJS_URL = os.getenv("NEXTJS_URL", "http://localhost:3000")
_nextjs_process = None  # Next.js 개발 서버 프로세스


async def _proxy_to_nextjs(request: Request, path: str = ""):
    """Next.js 개발 서버로 요청을 프록시합니다."""
    # 쿼리스트링 유지
    query = str(request.url.query)
    target_url = f"{NEXTJS_URL}/{path}" + (f"?{query}" if query else "")
    # Host 헤더를 Next.js 서버에 맞게 교체, content-length 제거 (httpx가 자동 계산)
    skip_headers = {"host", "content-length"}
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in skip_headers
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # GET/POST 모두 지원
            method = request.method
            body = await request.body() if method in ("POST", "PUT", "PATCH") else None
            resp = await client.request(
                method, target_url, headers=fwd_headers, content=body
            )
            # Next.js 응답 헤더 원본 보존 (RSC, Vary, Set-Cookie 등)
            proxy_headers = {}
            for key in (
                "content-type",
                "vary",
                "x-nextjs-cache",
                "set-cookie",
                "cache-control",
                "x-action-redirect",
                "x-action-revalidate",
                "location",
                "rsc",
                "next-router-state-tree",
                "x-nextjs-matched-path",
            ):
                val = resp.headers.get(key)
                if val:
                    proxy_headers[key] = val
            if not proxy_headers.get("content-type"):
                proxy_headers["content-type"] = "text/html; charset=utf-8"
            from fastapi.responses import Response

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=proxy_headers,
            )
    except httpx.ConnectError:
        # Next.js 서버가 아직 시작되지 않았을 때 안내 페이지
        return HTMLResponse(
            content="""
        <!DOCTYPE html>
        <html lang="ko">
        <head><meta charset="utf-8"><title>Next.js 서버 대기 중</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center;
                   align-items: center; min-height: 100vh; background: #0a0a0a; color: #ededed; margin: 0; }
            .card { background: #1a1a2e; padding: 3rem; border-radius: 16px; text-align: center;
                     box-shadow: 0 8px 32px rgba(0,0,0,0.3); max-width: 500px; }
            h2 { color: #60a5fa; margin-bottom: 1rem; }
            p { color: #9ca3af; line-height: 1.6; }
            code { background: #374151; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }
            .spinner { width: 40px; height: 40px; border: 4px solid #374151; border-top-color: #60a5fa;
                       border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1.5rem; }
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
        <meta http-equiv="refresh" content="3">
        </head>
        <body>
            <div class="card">
                <div class="spinner"></div>
                <h2>Next.js 프론트엔드 시작 중...</h2>
                <p>Next.js 개발 서버가 아직 준비되지 않았습니다.<br>
                <code>cd CSH/frontend && npm run dev</code> 를 실행하거나<br>
                잠시 후 자동으로 새로고침됩니다.</p>
            </div>
        </body>
        </html>
        """,
            status_code=503,
        )
    except Exception as e:
        return HTMLResponse(content=f"<h1>프록시 오류</h1><p>{e}</p>", status_code=502)


# ========== 외부 서비스 임포트 ==========
# TTS 서비스
try:
    from hume_tts_service import HumeInterviewerVoice, HumeTTSService, create_tts_router

    tts_router = create_tts_router()
    app.include_router(tts_router)
    TTS_AVAILABLE = True
    print("✅ Hume TTS 서비스 활성화됨")
except ImportError as e:
    TTS_AVAILABLE = False
    print(f"⚠️ Hume TTS 서비스 비활성화: {e}")

# RAG 서비스
try:
    from resume_rag import QA_TABLE, RESUME_TABLE, ResumeRAG

    RAG_AVAILABLE = True
    print("✅ Resume RAG 서비스 활성화됨")
except ImportError as e:
    RAG_AVAILABLE = False
    print(f"⚠️ Resume RAG 서비스 비활성화: {e}")

# LLM 서비스
try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    LLM_AVAILABLE = True
    print("✅ LLM 서비스 활성화됨")
except ImportError as e:
    LLM_AVAILABLE = False
    print(f"⚠️ LLM 서비스 비활성화: {e}")

# LangChain Memory (선택적)
MEMORY_AVAILABLE = False
ConversationBufferMemory = None
try:
    # 최신 LangChain (v0.2+)
    from langchain_community.chat_message_histories import ChatMessageHistory

    MEMORY_AVAILABLE = True
    print("✅ LangChain Memory 모듈 활성화됨 (ChatMessageHistory)")
except ImportError:
    try:
        # 레거시 LangChain
        from langchain.memory import ConversationBufferMemory

        MEMORY_AVAILABLE = True
        print("✅ LangChain Memory 모듈 활성화됨 (ConversationBufferMemory)")
    except ImportError:
        print("⚠️ LangChain Memory 모듈 비활성화 (수동 대화 기록 사용)")

# 한국어 띄어쓰기 보정기 (STT 후처리용) — deepface보다 먼저 import해야 함
# deepface가 tf_keras를 활성화하면 tensorflow.keras.layers.TFSMLayer를 찾지 못함
print(f"🐍 현재 Python: {sys.executable}")
try:
    from stt_engine import KoreanSpacingCorrector

    _spacing_corrector = KoreanSpacingCorrector()
    SPACING_CORRECTION_AVAILABLE = _spacing_corrector.is_available
    if SPACING_CORRECTION_AVAILABLE:
        print("✅ 한국어 띄어쓰기 보정 (pykospacing) 활성화됨")
    else:
        print("⚠️ pykospacing 미설치 - 띄어쓰기 보정 비활성화")
except ImportError as e:
    _spacing_corrector = None
    SPACING_CORRECTION_AVAILABLE = False
    print(f"⚠️ 한국어 띄어쓰기 보정 비활성화 (stt_engine 모듈 없음): {e}")

# 감정 분석
try:
    import numpy as np
    from deepface import DeepFace

    EMOTION_AVAILABLE = True
    print("✅ 감정 분석 서비스 활성화됨")
except ImportError as e:
    EMOTION_AVAILABLE = False
    print(f"⚠️ 감정 분석 서비스 비활성화: {e}")

# Redis
try:
    import redis

    REDIS_AVAILABLE = True
    print("✅ Redis 서비스 활성화됨")
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis 서비스 비활성화")

# Celery 비동기 작업
try:
    from celery.result import AsyncResult
    from celery_app import celery_app, check_celery_status
    from celery_tasks import (
        analyze_emotion_task,
        batch_emotion_analysis_task,
        batch_evaluate_task,
        complete_interview_workflow_task,
        evaluate_answer_task,
        generate_question_task,
        generate_report_task,
        generate_tts_task,
        prefetch_tts_task,
        process_resume_task,
        retrieve_resume_context_task,
        save_session_to_redis_task,
    )

    CELERY_AVAILABLE = True
    print("✅ Celery 비동기 작업 서비스 활성화됨")
except ImportError as e:
    CELERY_AVAILABLE = False
    print(f"⚠️ Celery 서비스 비활성화: {e}")

# 코딩 테스트 서비스
try:
    from code_execution_service import create_coding_router

    coding_router = create_coding_router()
    app.include_router(coding_router)
    CODING_TEST_AVAILABLE = True
    print("✅ 코딩 테스트 서비스 활성화됨 (LLM 자동 출제)")
except ImportError as e:
    CODING_TEST_AVAILABLE = False
    print(f"⚠️ 코딩 테스트 서비스 비활성화: {e}")

# 화이트보드 아키텍처 서비스
try:
    from whiteboard_service import router as whiteboard_router

    app.include_router(whiteboard_router)
    WHITEBOARD_AVAILABLE = True
    print("✅ 화이트보드 아키텍처 서비스 활성화됨")
except ImportError as e:
    WHITEBOARD_AVAILABLE = False
    print(f"⚠️ 화이트보드 서비스 비활성화: {e}")

# Deepgram STT 서비스
try:
    from deepgram import DeepgramClient
    from deepgram.core.events import EventType

    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    if DEEPGRAM_API_KEY:
        deepgram_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        DEEPGRAM_AVAILABLE = True
        print("✅ Deepgram STT 서비스 활성화됨")
    else:
        DEEPGRAM_AVAILABLE = False
        deepgram_client = None
        print("⚠️ Deepgram API 키가 설정되지 않음")
except ImportError as e:
    DEEPGRAM_AVAILABLE = False
    deepgram_client = None
    EventType = None
    print(f"⚠️ Deepgram STT 서비스 비활성화: {e}")


# ========== 이벤트 기반 마이크로서비스 아키텍처 ==========
# Redis Pub/Sub 기반 EventBus + 이벤트 핸들러 등록

try:
    from event_bus import EventBus
    from event_handlers import register_all_handlers
    from events import EventFactory
    from events import EventType as AppEventType

    event_bus = EventBus.get_instance()
    EVENT_BUS_AVAILABLE = True
    print("✅ 이벤트 버스 (EventBus) 활성화됨")
except ImportError as e:
    event_bus = None
    EVENT_BUS_AVAILABLE = False
    AppEventType = None
    print(f"⚠️ 이벤트 버스 비활성화: {e}")


# ========== REQ-F-006: 발화 분석 / 시선 추적 / PDF 리포트 ==========
try:
    from speech_analysis_service import SpeechAnalysisService

    speech_service = SpeechAnalysisService()
    SPEECH_ANALYSIS_AVAILABLE = True
    print("✅ 발화 분석 서비스 (SpeechAnalysisService) 활성화됨")
except ImportError as e:
    speech_service = None
    SPEECH_ANALYSIS_AVAILABLE = False
    print(f"⚠️ 발화 분석 서비스 비활성화: {e}")

try:
    from gaze_tracking_service import GazeTrackingService

    gaze_service = GazeTrackingService()
    GAZE_TRACKING_AVAILABLE = True
    print("✅ 시선 추적 서비스 (GazeTrackingService) 활성화됨")
except ImportError as e:
    gaze_service = None
    GAZE_TRACKING_AVAILABLE = False
    print(f"⚠️ 시선 추적 서비스 비활성화: {e}")

try:
    from pdf_report_service import generate_pdf_report

    PDF_REPORT_AVAILABLE = True
    print("✅ PDF 리포트 서비스 활성화됨")
except ImportError as e:
    generate_pdf_report = None
    PDF_REPORT_AVAILABLE = False
    print(f"⚠️ PDF 리포트 서비스 비활성화: {e}")


# ========== Hume AI Prosody 음성 감정 분석 ==========
try:
    from hume_prosody_service import (
        HumeProsodyService,
        determine_emotion_adaptive_mode,
        extract_interview_indicators,
        get_prosody_service,
        is_prosody_available,
    )

    prosody_service = get_prosody_service()
    PROSODY_AVAILABLE = is_prosody_available()
    if PROSODY_AVAILABLE:
        print("✅ Hume Prosody 음성 감정 분석 서비스 활성화됨")
    else:
        print("⚠️ Hume Prosody: HUME_API_KEY 미설정 — 비활성화")
except ImportError as e:
    prosody_service = None
    PROSODY_AVAILABLE = False
    print(f"⚠️ Hume Prosody 서비스 비활성화: {e}")

# ========== Whisper 오프라인 STT 폴백 ==========
try:
    from whisper_stt_service import (
        WhisperSTTService,
        is_whisper_available,
        process_audio_with_whisper,
    )

    if is_whisper_available():
        whisper_service = WhisperSTTService()
        WHISPER_AVAILABLE = True
        print("✅ Whisper 오프라인 STT 폴백 활성화됨")
    else:
        whisper_service = None
        WHISPER_AVAILABLE = False
        print("⚠️ Whisper 모델 미설치 (faster-whisper 또는 openai-whisper 필요)")
except ImportError as e:
    whisper_service = None
    WHISPER_AVAILABLE = False
    print(f"⚠️ Whisper STT 폴백 비활성화: {e}")


# ========== 미디어 녹화/트랜스코딩 서비스 (aiortc + GStreamer 하이브리드) ==========
try:
    from media_recording_service import (
        FFMPEG_AVAILABLE as _FFM,
    )
    from media_recording_service import (
        GSTREAMER_AVAILABLE as _GST,
    )
    from media_recording_service import (
        MEDIA_TOOL,
        MediaRecordingService,
        RecordingMetadata,
        RecordingStatus,
        recording_service,
    )

    RECORDING_AVAILABLE = recording_service.available
    if RECORDING_AVAILABLE:
        _tool_name = "GStreamer" if _GST else "FFmpeg"
        print(f"✅ 미디어 녹화 서비스 활성화됨 (도구: {_tool_name})")
    else:
        print("⚠️ 미디어 녹화: GStreamer/FFmpeg 미설치 — 녹화 비활성화")
except ImportError as e:
    recording_service = None
    RECORDING_AVAILABLE = False
    RecordingStatus = None
    print(f"⚠️ 미디어 녹화 서비스 비활성화: {e}")


# ========== LangGraph 워크플로우 상태머신 ==========
try:
    from interview_workflow import (
        InterviewPhase,
        InterviewWorkflow,
        WorkflowState,
        get_workflow_instance,
        init_workflow,
    )

    LANGGRAPH_AVAILABLE = True
    print("✅ LangGraph 워크플로우 모듈 로드됨")
except ImportError as e:
    LANGGRAPH_AVAILABLE = False
    InterviewWorkflow = None
    WorkflowState = None
    InterviewPhase = None
    init_workflow = None
    get_workflow_instance = None
    print(f"⚠️ LangGraph 워크플로우 비활성화: {e}")


# ========== 전역 상태 관리 ==========

# 회원 정보 저장소 (DB 연결 실패 시 폴백용)
users_db: Dict[str, Dict] = {}


# DB 헬퍼 함수
def get_db():
    """DB 세션 생성"""
    if not DB_AVAILABLE:
        return None
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """이메일로 사용자 조회"""
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    return {
                        "id": user.id,
                        "user_id": str(user.id),  # id를 user_id로 사용
                        "email": user.email,
                        "password_hash": user.password_hash,
                        "name": user.name,
                        "birth_date": str(user.birth_date) if user.birth_date else None,
                        "address": user.address,
                        "gender": user.gender,
                        "phone": user.phone,
                        "role": user.role,
                        "created_at": user.created_at.isoformat()
                        if user.created_at
                        else None,
                    }
            except Exception as e:
                print(f"❌ [get_user_by_email] DB 쿼리 오류: {e}")
            finally:
                db.close()
    # 폴백: 메모리 저장소
    return users_db.get(email)


def create_user(user_data: Dict) -> bool:
    """사용자 생성"""
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                new_user = User(
                    email=user_data["email"],
                    password_hash=user_data["password_hash"],
                    name=user_data.get("name"),
                    birth_date=user_data.get("birth_date"),
                    address=user_data.get("address"),
                    gender=user_data.get("gender"),
                    phone=user_data.get("phone"),
                    role=user_data.get("role", "candidate"),  # 기본값: candidate
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)  # id 가져오기
                print(
                    f"✅ DB에 사용자 저장됨: {user_data['email']} (ID: {new_user.id})"
                )
                return True
            except Exception as e:
                db.rollback()
                print(f"❌ DB 저장 실패: {e}")
            finally:
                db.close()
    # 폴백: 메모리 저장소
    users_db[user_data["email"]] = user_data
    print(f"⚠️ 메모리에 사용자 저장됨: {user_data['email']}")
    return True


def update_user(email: str, update_data: Dict) -> bool:
    """사용자 정보 수정"""
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    if "name" in update_data:
                        user.name = update_data["name"]
                    if "birth_date" in update_data:
                        user.birth_date = update_data["birth_date"]
                    if "address" in update_data:
                        user.address = update_data["address"]
                    if "gender" in update_data:
                        user.gender = update_data["gender"]
                    if "phone" in update_data:
                        user.phone = update_data["phone"]
                    if "role" in update_data:
                        user.role = update_data["role"]
                    if "password_hash" in update_data:
                        user.password_hash = update_data["password_hash"]
                    db.commit()
                    print(f"✅ DB에서 사용자 정보 수정됨: {email}")
                    return True
                else:
                    print(f"❌ 사용자를 찾을 수 없음: {email}")
                    return False
            except Exception as e:
                db.rollback()
                print(f"❌ DB 수정 실패: {e}")
                return False
            finally:
                db.close()
    # 폴백: 메모리 저장소
    if email in users_db:
        users_db[email].update(update_data)
        print(f"⚠️ 메모리에서 사용자 정보 수정됨: {email}")
        return True
    return False


class InterviewState:
    """면접 세션 상태 관리"""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.pcs: Set[RTCPeerConnection] = set()
        self.pc_sessions: Dict[RTCPeerConnection, str] = {}
        self.last_emotion: Optional[Dict] = None
        self.last_prosody: Optional[Dict] = None  # Hume Prosody 최신 결과
        self.emotion_lock = asyncio.Lock()
        # WebSocket 연결 관리 (session_id -> List[WebSocket])
        self.websocket_connections: Dict[str, List[WebSocket]] = {}
        # STT 세션 관리 (session_id -> deepgram_connection)
        self.stt_connections: Dict[str, Any] = {}
        # 오디오 버퍼 (session_id -> asyncio.Queue)
        self.audio_queues: Dict[str, asyncio.Queue] = {}

    def create_session(self, session_id: str = None) -> str:
        """새 면접 세션 생성"""
        if not session_id:
            session_id = uuid.uuid4().hex

        self.sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "status": "initialized",
            "chat_history": [],
            "emotions": [],
            "answers": [],
            "current_question_idx": 0,
            "interview_mode": "text",  # text, voice, video
            "resume_uploaded": False,
            "resume_path": None,
            "resume_filename": None,
            "retriever": None,  # 세션별 RAG retriever
            # LangChain Memory
            "memory": None,  # ConversationBufferMemory 인스턴스
            # 꼬리질문 추적
            "current_topic": None,  # 현재 질문 주제
            "topic_question_count": 0,  # 해당 주제에서 진행된 질문 수
            "topic_history": [],  # 주제별 질문 이력 [{"topic": str, "count": int}]
            "follow_up_mode": False,  # 꼬리질문 모드 여부
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, data: Dict):
        if session_id in self.sessions:
            self.sessions[session_id].update(data)


state = InterviewState()


# ========== 실시간 개입 시스템 (VAD + Turn-taking) ==========
class InterviewInterventionManager:
    """
    실시간 면접 개입 관리자
    - VAD(Voice Activity Detection) 기반 발화 감지
    - Turn-taking 알고리즘으로 적절한 개입 타이밍 결정
    - 답변 길이/시간 초과, 주제 이탈 감지
    """

    # 개입 임계값 설정
    MAX_ANSWER_TIME_SECONDS = 120  # 최대 답변 시간 (2분)
    MAX_ANSWER_LENGTH = 800  # 최대 답변 길이 (글자 수)
    SOFT_WARNING_TIME = 90  # 부드러운 경고 시간 (1분 30초)
    SOFT_WARNING_LENGTH = 600  # 부드러운 경고 길이
    SILENCE_THRESHOLD_MS = 2000  # 침묵 감지 임계값 (2초)
    TOPIC_RELEVANCE_THRESHOLD = 0.3  # 주제 관련성 임계값

    # 개입 메시지 템플릿
    INTERVENTION_MESSAGES = {
        "soft_time_warning": [
            "네, 잘 듣고 있습니다. 핵심 내용을 정리해서 마무리해 주시겠어요?",
            "좋은 경험이네요. 시간 관계상 결론 부분을 말씀해 주시겠어요?",
            "알겠습니다. 간단히 정리해서 마무리해 주세요.",
        ],
        "hard_time_limit": [
            "네, 충분히 이해했습니다. 다음 질문으로 넘어가겠습니다.",
            "좋습니다. 시간 관계상 다음 질문을 드리겠습니다.",
            "감사합니다. 이제 다음 주제로 넘어가 볼까요?",
        ],
        "off_topic": [
            "좋은 말씀이시네요. 다만 질문과 조금 다른 방향인 것 같은데, 원래 질문으로 돌아가 볼까요?",
            "흥미로운 내용이지만, 질문에 좀 더 집중해서 답변해 주시겠어요?",
            "네, 이해합니다. 원래 질문의 핵심에 대해 답변 부탁드립니다.",
        ],
        "encourage_more": [
            "조금 더 구체적으로 설명해 주시겠어요?",
            "예시를 들어 설명해 주시면 좋겠습니다.",
            "그 부분에 대해 좀 더 자세히 말씀해 주세요.",
        ],
        "silence_detected": [
            "생각 정리가 필요하시면 잠시 시간을 드릴게요.",
            "천천히 생각하셔도 됩니다.",
            "준비가 되시면 말씀해 주세요.",
        ],
    }

    def __init__(self):
        self.session_states: Dict[str, Dict] = {}  # 세션별 VAD 상태
        self.intervention_history: Dict[str, List] = {}  # 개입 이력

    def init_session(self, session_id: str):
        """세션별 개입 상태 초기화"""
        self.session_states[session_id] = {
            "answer_start_time": None,
            "current_answer_text": "",
            "is_speaking": False,
            "last_speech_time": None,
            "silence_duration_ms": 0,
            "intervention_count": 0,
            "soft_warning_given": False,
            "current_question_keywords": [],
            "vad_buffer": [],  # VAD 신호 버퍼
            "turn_state": "ai_speaking",  # ai_speaking, user_speaking, silence
        }
        self.intervention_history[session_id] = []
        print(f"🎙️ [Intervention] 세션 {session_id[:8]}... 개입 시스템 초기화")

    def start_user_turn(self, session_id: str, question_keywords: List[str] = None):
        """사용자 발화 시작 (질문 후)"""
        if session_id not in self.session_states:
            self.init_session(session_id)

        state = self.session_states[session_id]
        state["answer_start_time"] = datetime.now()
        state["current_answer_text"] = ""
        state["is_speaking"] = True
        state["last_speech_time"] = datetime.now()
        state["silence_duration_ms"] = 0
        state["soft_warning_given"] = False
        state["turn_state"] = "user_speaking"

        if question_keywords:
            state["current_question_keywords"] = question_keywords

        print(f"🎤 [VAD] 세션 {session_id[:8]}... 사용자 발화 시작")

    def update_vad_signal(
        self, session_id: str, is_speech: bool, audio_level: float = 0.0
    ):
        """VAD 신호 업데이트 (실시간)"""
        if session_id not in self.session_states:
            return None

        state = self.session_states[session_id]
        current_time = datetime.now()

        # VAD 버퍼에 신호 추가
        state["vad_buffer"].append(
            {
                "timestamp": current_time,
                "is_speech": is_speech,
                "audio_level": audio_level,
            }
        )

        # 버퍼 크기 제한 (최근 100개)
        if len(state["vad_buffer"]) > 100:
            state["vad_buffer"] = state["vad_buffer"][-100:]

        if is_speech:
            state["is_speaking"] = True
            state["last_speech_time"] = current_time
            state["silence_duration_ms"] = 0
            state["turn_state"] = "user_speaking"
        else:
            # 침묵 시간 계산
            if state["last_speech_time"]:
                silence_ms = (
                    current_time - state["last_speech_time"]
                ).total_seconds() * 1000
                state["silence_duration_ms"] = silence_ms

                if silence_ms > self.SILENCE_THRESHOLD_MS:
                    state["turn_state"] = "silence"
                    state["is_speaking"] = False

        return state["turn_state"]

    def update_answer_text(self, session_id: str, text: str):
        """답변 텍스트 업데이트 (STT 결과)"""
        if session_id not in self.session_states:
            return

        self.session_states[session_id]["current_answer_text"] = text

    def check_intervention_needed(
        self, session_id: str, answer_text: str = None
    ) -> Optional[Dict]:
        """개입이 필요한지 확인"""
        if session_id not in self.session_states:
            return None

        state = self.session_states[session_id]

        if answer_text:
            state["current_answer_text"] = answer_text

        answer_length = len(state["current_answer_text"])
        elapsed_seconds = 0

        if state["answer_start_time"]:
            elapsed_seconds = (
                datetime.now() - state["answer_start_time"]
            ).total_seconds()

        intervention = None

        # 1. 강제 시간 제한 초과
        if elapsed_seconds >= self.MAX_ANSWER_TIME_SECONDS:
            intervention = {
                "type": "hard_time_limit",
                "reason": f"시간 초과 ({elapsed_seconds:.0f}초)",
                "message": self._get_random_message("hard_time_limit"),
                "action": "force_next_question",
                "priority": "high",
            }

        # 2. 소프트 시간 경고
        elif (
            elapsed_seconds >= self.SOFT_WARNING_TIME
            and not state["soft_warning_given"]
        ):
            intervention = {
                "type": "soft_time_warning",
                "reason": f"시간 경고 ({elapsed_seconds:.0f}초)",
                "message": self._get_random_message("soft_time_warning"),
                "action": "warn",
                "priority": "medium",
            }
            state["soft_warning_given"] = True

        # 3. 답변 길이 초과
        elif answer_length >= self.MAX_ANSWER_LENGTH:
            intervention = {
                "type": "hard_time_limit",
                "reason": f"답변 길이 초과 ({answer_length}자)",
                "message": self._get_random_message("hard_time_limit"),
                "action": "force_next_question",
                "priority": "high",
            }

        # 4. 소프트 길이 경고
        elif (
            answer_length >= self.SOFT_WARNING_LENGTH
            and not state["soft_warning_given"]
        ):
            intervention = {
                "type": "soft_time_warning",
                "reason": f"답변 길이 경고 ({answer_length}자)",
                "message": self._get_random_message("soft_time_warning"),
                "action": "warn",
                "priority": "medium",
            }
            state["soft_warning_given"] = True

        # 5. 주제 이탈 감지
        if intervention is None and answer_length > 100:
            relevance = self._check_topic_relevance(
                state["current_answer_text"], state["current_question_keywords"]
            )
            if relevance < self.TOPIC_RELEVANCE_THRESHOLD:
                intervention = {
                    "type": "off_topic",
                    "reason": f"주제 관련성 낮음 ({relevance:.2f})",
                    "message": self._get_random_message("off_topic"),
                    "action": "redirect",
                    "priority": "medium",
                }

        # 6. 장시간 침묵 감지
        if (
            intervention is None and state["silence_duration_ms"] > 5000
        ):  # 5초 이상 침묵
            intervention = {
                "type": "silence_detected",
                "reason": f"침묵 감지 ({state['silence_duration_ms'] / 1000:.1f}초)",
                "message": self._get_random_message("silence_detected"),
                "action": "encourage",
                "priority": "low",
            }

        if intervention:
            state["intervention_count"] += 1
            self.intervention_history[session_id].append(
                {
                    **intervention,
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_seconds": elapsed_seconds,
                    "answer_length": answer_length,
                }
            )
            print(
                f"⚠️ [Intervention] 세션 {session_id[:8]}... {intervention['type']}: {intervention['reason']}"
            )

        return intervention

    def _check_topic_relevance(
        self, answer: str, question_keywords: List[str]
    ) -> float:
        """주제 관련성 점수 계산 (0.0 ~ 1.0)"""
        if not question_keywords:
            return 1.0  # 키워드가 없으면 관련성 체크 스킵

        answer_lower = answer.lower()
        matches = sum(1 for kw in question_keywords if kw.lower() in answer_lower)

        # 기본 관련성 점수
        keyword_score = matches / len(question_keywords) if question_keywords else 0

        # 일반적인 면접 관련 키워드 체크 (보너스)
        general_keywords = [
            "경험",
            "프로젝트",
            "개발",
            "팀",
            "기술",
            "결과",
            "성과",
            "학습",
        ]
        general_matches = sum(1 for kw in general_keywords if kw in answer_lower)
        general_score = min(general_matches * 0.1, 0.3)

        return min(keyword_score + general_score, 1.0)

    def _get_random_message(self, message_type: str) -> str:
        """랜덤 개입 메시지 선택"""
        import random

        messages = self.INTERVENTION_MESSAGES.get(message_type, [])
        return random.choice(messages) if messages else ""

    def extract_question_keywords(self, question: str) -> List[str]:
        """질문에서 키워드 추출"""
        # 불용어 목록
        stopwords = [
            "무엇",
            "어떻게",
            "왜",
            "있",
            "하",
            "되",
            "을",
            "를",
            "이",
            "가",
            "은",
            "는",
            "에",
            "서",
            "로",
            "으로",
            "의",
            "와",
            "과",
            "도",
            "만",
            "까지",
            "부터",
            "말씀",
            "해주",
            "주세요",
            "싶",
            "있나요",
            "인가요",
            "대해",
            "관해",
        ]

        # 한글 단어 추출
        import re

        words = re.findall(r"[가-힣]{2,}", question)

        # 불용어 제거
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]

        # 기술 키워드 우선
        tech_keywords = [
            "python",
            "java",
            "react",
            "api",
            "서버",
            "데이터",
            "알고리즘",
            "프로젝트",
            "개발",
            "설계",
            "배포",
            "테스트",
            "협업",
        ]

        return keywords[:10]  # 상위 10개

    def get_turn_taking_signal(self, session_id: str) -> Dict:
        """Turn-taking 신호 반환"""
        if session_id not in self.session_states:
            return {"can_interrupt": False, "turn_state": "unknown"}

        state = self.session_states[session_id]

        # Turn-taking 결정 로직
        can_interrupt = False
        interrupt_reason = ""

        # 1. 긴 침묵 후 개입 가능
        if state["turn_state"] == "silence" and state["silence_duration_ms"] > 3000:
            can_interrupt = True
            interrupt_reason = "silence_pause"

        # 2. 시간/길이 초과 시 개입 가능
        if state["answer_start_time"]:
            elapsed = (datetime.now() - state["answer_start_time"]).total_seconds()
            if elapsed > self.SOFT_WARNING_TIME:
                can_interrupt = True
                interrupt_reason = "time_exceeded"

        # 3. VAD 버퍼 분석 - 발화 패턴 감지
        recent_vad = state["vad_buffer"][-20:] if state["vad_buffer"] else []
        if len(recent_vad) >= 10:
            # 최근 발화 비율 계산
            speech_ratio = sum(1 for v in recent_vad if v["is_speech"]) / len(
                recent_vad
            )
            # 발화가 줄어들고 있으면 (문장 끝) 개입 가능
            if speech_ratio < 0.3 and state["silence_duration_ms"] > 1000:
                can_interrupt = True
                interrupt_reason = "speech_ending"

        return {
            "can_interrupt": can_interrupt,
            "interrupt_reason": interrupt_reason,
            "turn_state": state["turn_state"],
            "silence_duration_ms": state["silence_duration_ms"],
            "is_speaking": state["is_speaking"],
        }

    def end_user_turn(self, session_id: str) -> Dict:
        """사용자 발화 종료"""
        if session_id not in self.session_states:
            return {}

        state = self.session_states[session_id]

        # 발화 통계 계산
        elapsed_seconds = 0
        if state["answer_start_time"]:
            elapsed_seconds = (
                datetime.now() - state["answer_start_time"]
            ).total_seconds()

        stats = {
            "total_time_seconds": elapsed_seconds,
            "answer_length": len(state["current_answer_text"]),
            "intervention_count": state["intervention_count"],
            "soft_warning_given": state["soft_warning_given"],
        }

        # 상태 리셋
        state["turn_state"] = "ai_speaking"
        state["is_speaking"] = False

        print(
            f"🎙️ [VAD] 세션 {session_id[:8]}... 사용자 발화 종료 ({elapsed_seconds:.1f}초, {stats['answer_length']}자)"
        )

        return stats

    def get_session_stats(self, session_id: str) -> Dict:
        """세션 개입 통계 반환"""
        return {
            "intervention_history": self.intervention_history.get(session_id, []),
            "total_interventions": len(self.intervention_history.get(session_id, [])),
            "state": self.session_states.get(session_id, {}),
        }


# 개입 관리자 인스턴스
intervention_manager = InterviewInterventionManager()


# ========== LLM 면접관 서비스 ==========
class AIInterviewer:
    """AI 면접관 - LangChain LLM 기반 동적 질문 생성 + 답변 분석/평가"""

    # 공통 프롬프트 템플릿 참조 (실시간/Celery 동기화)
    INTERVIEWER_PROMPT = SHARED_INTERVIEWER_PROMPT
    EVALUATION_PROMPT = SHARED_EVALUATION_PROMPT
    MAX_QUESTIONS = SHARED_MAX_QUESTIONS

    def __init__(self):
        self.llm = None
        self.question_llm = None  # 질문 생성용 LLM (높은 temperature)
        self.rag = None
        self.retriever = None
        self.tts_service = None

        self._init_services()

    def _init_services(self):
        """서비스 초기화"""
        # LLM 초기화
        if LLM_AVAILABLE:
            try:
                # 평가용 LLM (낮은 temperature, think=None으로 thinking mode 비활성화)
                # num_predict: 최대 생성 토큰 수 제한 → 불필요한 장문 생성 방지
                # num_ctx: 4096으로 축소 → VRAM 절약 (8192 → 4096: ~1.5GB 절약)
                self.llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL,
                    temperature=0.3,
                    num_ctx=DEFAULT_LLM_NUM_CTX,
                    num_predict=DEFAULT_LLM_NUM_PREDICT,
                    think=False,  # qwen3 thinking 명시적 비활성화 (None은 모델 기본값 유지 → thinking ON)
                )
                # 질문 생성용 LLM (높은 temperature, think=False로 thinking mode 명시적 비활성화)
                self.question_llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL,
                    temperature=DEFAULT_LLM_TEMPERATURE,
                    num_ctx=DEFAULT_LLM_NUM_CTX,
                    num_predict=DEFAULT_LLM_NUM_PREDICT,
                    think=False,  # qwen3 thinking 명시적 비활성화 (None은 모델 기본값 유지 → thinking ON)
                )
                print(
                    f"✅ LLM 초기화 완료 (질문 생성 + 평가): {DEFAULT_LLM_MODEL}, num_ctx={DEFAULT_LLM_NUM_CTX}, num_predict={DEFAULT_LLM_NUM_PREDICT}"
                )
            except Exception as e:
                print(f"❌ LLM 초기화 실패: {e}")

        # RAG 초기화
        if RAG_AVAILABLE:
            try:
                connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
                if connection_string:
                    self.rag = ResumeRAG(
                        connection_string=connection_string, table_name=RESUME_TABLE
                    )
                    self.retriever = self.rag.get_retriever()
                    print("✅ RAG 초기화 완료 (테이블: resume_embeddings)")
            except Exception as e:
                print(f"⚠️ RAG 초기화 실패 (resume_embeddings): {e}")

            try:
                self.qa_rag = ResumeRAG(table_name=QA_TABLE)
                print("✅ Q&A RAG 초기화 완료 (테이블: qa_embeddings)")
            except Exception as e:
                self.qa_rag = None
                print(f"⚠️ Q&A RAG 초기화 실패 (qa_embeddings): {e}")

        # TTS 초기화
        if TTS_AVAILABLE:
            try:
                self.tts_service = HumeInterviewerVoice()
                print("✅ TTS 초기화 완료")
            except Exception as e:
                print(f"⚠️ TTS 초기화 실패: {e}")

    def init_session_memory(self, session_id: str):
        """세션별 대화 기록 메모리 초기화 (수동 관리 방식)"""
        session = state.get_session(session_id)
        if not session:
            return None

        # 이미 메모리가 있으면 반환
        if session.get("memory"):
            return session["memory"]

        try:
            # 수동 대화 기록 관리 (LangChain 버전 무관)
            memory = {
                "messages": [],  # [HumanMessage, AIMessage, ...]
                "summary": "",  # 요약 (나중에 사용)
            }

            # 세션에 저장
            state.update_session(session_id, {"memory": memory})
            print(f"✅ 세션 {session_id[:8]}... Memory 초기화 완료")
            return memory
        except Exception as e:
            print(f"⚠️ Memory 초기화 실패: {e}")
            return None

    def save_to_memory(self, session_id: str, question: str, answer: str):
        """대화를 메모리에 저장"""
        session = state.get_session(session_id)
        if not session or not session.get("memory"):
            return

        memory = session["memory"]
        if isinstance(memory, dict) and "messages" in memory:
            memory["messages"].append(AIMessage(content=question))
            memory["messages"].append(HumanMessage(content=answer))

    def get_memory_messages(self, session_id: str) -> list:
        """메모리에서 대화 기록 가져오기"""
        session = state.get_session(session_id)
        if not session or not session.get("memory"):
            return []

        memory = session["memory"]
        if isinstance(memory, dict) and "messages" in memory:
            return memory["messages"]
        return []

    def detect_topic_from_answer(self, answer: str) -> str:
        """답변에서 주제를 추출 (간단한 키워드 기반)"""
        topic_keywords = {
            "project": ["프로젝트", "개발", "구현", "만들", "제작"],
            "technical": [
                "기술",
                "스택",
                "언어",
                "프레임워크",
                "도구",
                "python",
                "java",
                "react",
            ],
            "experience": ["경험", "경력", "회사", "팀", "업무"],
            "problem_solving": ["문제", "해결", "버그", "오류", "이슈", "장애"],
            "teamwork": ["팀", "협업", "동료", "커뮤니케이션", "갈등"],
            "motivation": ["지원", "이유", "동기", "관심", "목표"],
            "growth": ["성장", "발전", "학습", "공부", "목표", "계획"],
        }

        answer_lower = answer.lower()
        topic_scores = {}

        for topic, keywords in topic_keywords.items():
            score = sum(1 for kw in keywords if kw in answer_lower)
            if score > 0:
                topic_scores[topic] = score

        if topic_scores:
            return max(topic_scores, key=topic_scores.get)
        return "general"

    def should_follow_up(self, session_id: str, answer: str) -> tuple[bool, str]:
        """꼬리질문이 필요한지 판단 (답변 품질 + 주제 추적)"""
        session = state.get_session(session_id)
        if not session:
            return False, ""

        current_topic = session.get("current_topic")
        topic_count = session.get("topic_question_count", 0)

        # 답변 품질 분석 (완화된 휴리스틱)
        normalized_answer = sanitize_user_input(answer)
        answer_length = len(re.sub(r"\s+", "", normalized_answer))
        word_count = len(normalized_answer.split())
        has_numeric_detail = bool(re.search(r"\d", normalized_answer))
        has_tech_keyword = any(
            keyword in normalized_answer.lower()
            for keyword in [
                "api",
                "redis",
                "postgres",
                "docker",
                "kubernetes",
                "python",
                "fastapi",
                "react",
                "llm",
                "rag",
            ]
        )
        has_specifics = (
            any(
                word in normalized_answer
                for word in [
                    "예를 들어",
                    "구체적으로",
                    "실제로",
                    "결과적으로",
                    "%",
                    "개월",
                    "명",
                ]
            )
            or has_numeric_detail
            or has_tech_keyword
        )

        # 꼬리질문 필요 여부 결정
        needs_follow_up = False
        follow_up_reason = ""

        # 1. 답변이 매우 짧은 경우에만 꼬리질문
        if answer_length < 25 and word_count < 6:
            needs_follow_up = True
            follow_up_reason = "답변이 매우 짧음 - 핵심 경험 보강 요청"
        # 2. 길이가 다소 짧고 구체성도 부족한 경우에만 꼬리질문
        elif answer_length < 90 and word_count < 15 and not has_specifics:
            needs_follow_up = True
            follow_up_reason = "구체성 부족 - 간단한 수치/사례 보강 요청"

        # 3. 같은 주제로 2번 이상 질문했으면 꼬리질문 중단
        if topic_count >= 2:
            needs_follow_up = False
            follow_up_reason = "주제 전환 필요"

        return needs_follow_up, follow_up_reason

    def update_topic_tracking(self, session_id: str, answer: str, is_follow_up: bool):
        """주제 추적 정보 업데이트"""
        session = state.get_session(session_id)
        if not session:
            return

        detected_topic = self.detect_topic_from_answer(answer)
        current_topic = session.get("current_topic")
        topic_count = session.get("topic_question_count", 0)
        topic_history = session.get("topic_history", [])

        if is_follow_up:
            # 꼬리질문: 같은 주제 카운트 증가
            state.update_session(
                session_id,
                {"topic_question_count": topic_count + 1, "follow_up_mode": True},
            )
        else:
            # 새 질문: 주제 전환
            if current_topic:
                topic_history.append({"topic": current_topic, "count": topic_count})

            state.update_session(
                session_id,
                {
                    "current_topic": detected_topic,
                    "topic_question_count": 1,
                    "topic_history": topic_history,
                    "follow_up_mode": False,
                },
            )

    def get_initial_greeting(self, job_posting: dict = None) -> str:
        """
        초기 인사말 반환
        - job_posting이 있으면 공고 정보를 반영한 맞춤형 인사말 생성
        """
        if job_posting:
            company = job_posting.get("company", "저희 회사")
            title = job_posting.get("title", "지원 포지션")
            return (
                f"안녕하세요. {company}의 '{title}' 포지션 면접을 진행하게 된 "
                f"면접관입니다. 공고 내용을 바탕으로 질문드리겠습니다. "
                f"먼저 간단한 자기소개를 부탁드립니다."
            )
        return "안녕하세요. 오늘 면접을 진행하게 된 면접관입니다. 먼저 간단한 자기소개를 부탁드립니다."

    async def generate_llm_question(self, session_id: str, user_answer: str) -> str:
        """LLM을 사용하여 다음 질문 생성 (Memory + 꼬리질문 추적)"""
        session = state.get_session(session_id)
        if not session:
            return self.get_initial_greeting()

        question_count = session.get("question_count", 1)

        # 최대 질문 수 도달 시 면접 종료 + 백그라운드 워크플로우 시작
        if question_count >= self.MAX_QUESTIONS:
            # Celery 백그라운드 워크플로우 시작 (리포트 생성 등)
            asyncio.create_task(self.start_interview_completion_workflow(session_id))
            return "면접이 종료되었습니다. 수고하셨습니다. 결과 보고서를 확인해주세요."

        # LLM이 없으면 기본 질문 반환
        if not self.question_llm:
            fallback_questions = [
                "지원하신 포지션에 관심을 갖게 된 계기가 무엇인가요?",
                "가장 도전적이었던 프로젝트 경험에 대해 말씀해주세요.",
                "사용하시는 주요 기술 스택에 대해 설명해주세요.",
                "앞으로의 커리어 목표는 무엇인가요?",
                "마지막으로 저희 회사에 궁금한 점이 있으신가요?",
            ]
            return fallback_questions[min(question_count, len(fallback_questions) - 1)]

        try:
            # ========== 1. 세션 Memory 초기화/활용 ==========
            memory = self.init_session_memory(session_id)

            # Memory에 현재 대화 저장 (있으면)
            if memory and user_answer:
                # 마지막 질문 가져오기
                chat_history = session.get("chat_history", [])
                last_question = ""
                for msg in reversed(chat_history):
                    if msg["role"] == "assistant":
                        last_question = msg["content"]
                        break

                if last_question:
                    self.save_to_memory(session_id, last_question, user_answer)

            # ========== 2. 꼬리질문 필요 여부 판단 ==========
            needs_follow_up, follow_up_reason = self.should_follow_up(
                session_id, user_answer
            )
            current_topic = session.get("current_topic", "general")
            topic_count = session.get("topic_question_count", 0)

            # 꼬리질문 상태 로깅
            print(
                f"📊 [Session {session_id[:8]}] 주제: {current_topic}, 주제내 질문수: {topic_count}, 꼬리질문 필요: {needs_follow_up} ({follow_up_reason})"
            )

            # ========== 3. RAG 컨텍스트 병렬 조회 (이력서 + Q&A) ==========
            # ⚡ 성능 최적화: 두 RAG 검색을 asyncio.gather로 병렬 실행
            #    순차 실행 대비 대기 시간 ~50% 감소, 각 RAG에 10초 타임아웃 설정
            resume_context = ""
            qa_reference_context = ""
            session_retriever = session.get("retriever") or self.retriever

            async def _fetch_resume_rag():
                """이력서 RAG 검색 (타임아웃 10초)"""
                if not (session_retriever and user_answer):
                    return ""
                try:
                    docs = await asyncio.wait_for(
                        run_rag_async(session_retriever, user_answer),
                        timeout=10,
                    )
                    if docs:
                        print(f"📚 [RAG] {len(docs)}개 문서에서 컨텍스트 추출 (비동기)")
                        return "\n".join([d.page_content for d in docs[:3]])
                except asyncio.TimeoutError:
                    print("⏰ [RAG] 이력서 검색 타임아웃 (10초) — 컨텍스트 없이 진행")
                except Exception as e:
                    print(f"⚠️ RAG 검색 오류: {e}")
                return ""

            async def _fetch_qa_rag():
                """Q&A 참조 RAG 검색 (타임아웃 10초)"""
                if not (
                    RAG_AVAILABLE and user_answer and getattr(self, "qa_rag", None)
                ):
                    return ""
                try:
                    qa_docs = await asyncio.wait_for(
                        run_in_executor(
                            RAG_EXECUTOR, self.qa_rag.similarity_search, user_answer, 2
                        ),
                        timeout=10,
                    )
                    if qa_docs:
                        print(
                            f"📖 [Q&A RAG] {len(qa_docs)}개 참조 문서에서 모범 답변 추출"
                        )
                        return "\n".join([d.page_content for d in qa_docs[:2]])
                except asyncio.TimeoutError:
                    print("⏰ [Q&A RAG] 참조 검색 타임아웃 (10초) — 참조 없이 진행")
                except Exception as e:
                    print(f"⚠️ Q&A 참조 데이터 검색 오류 (무시): {e}")
                return ""

            # 두 RAG를 동시에 실행 — GPU/DB 부하 분산 및 대기 시간 최소화
            resume_context, qa_reference_context = await asyncio.gather(
                _fetch_resume_rag(), _fetch_qa_rag()
            )

            # ========== 4. 대화 기록을 LangChain 메시지로 변환 ==========
            chat_history = session.get("chat_history", [])
            messages = [SystemMessage(content=self.INTERVIEWER_PROMPT)]

            # ========== 4-1. 채용 공고 컨텍스트 주입 (공고 기반 면접 시) ==========
            job_posting = session.get("job_posting")
            if job_posting:
                jp_context = (
                    f"\n--- [채용 공고 정보] 이 면접의 대상 공고 ---\n"
                    f"회사명: {job_posting.get('company', 'N/A')}\n"
                    f"공고 제목: {job_posting.get('title', 'N/A')}\n"
                    f"근무지: {job_posting.get('location', 'N/A')}\n"
                    f"직무 분야: {job_posting.get('job_category', 'N/A')}\n"
                    f"경력 수준: {job_posting.get('experience_level', 'N/A')}\n"
                    f"급여: {job_posting.get('salary_info', 'N/A')}\n"
                    f"\n[공고 상세 내용]\n{job_posting.get('description', '')}\n"
                    f"------------------------------------------\n"
                    f"☝️ 위 채용 공고의 요구사항, 자격요건, 우대사항, 직무 설명을 활용하여 "
                    f"맞춤형 면접 질문을 생성하세요.\n"
                    f"예시: 공고에서 요구하는 기술 스택 경험, 해당 직무의 실무 시나리오, "
                    f"자격 요건 충족 여부 등을 질문하세요."
                )
                messages.append(SystemMessage(content=jp_context))
                print(
                    f"📋 LLM에 공고 컨텍스트 주입: [{job_posting.get('company')}] {job_posting.get('title')}"
                )

            # Memory에서 대화 기록 가져오기 (있으면)
            # ⚡ 성능 최적화: 최근 3턴(6메시지)만 포함하여 컨텍스트 윈도우 절약
            #    num_ctx=4096에서 전체 히스토리를 넣으면 5번째 질문쯤 ~3,900토큰에 도달하여
            #    토큰 처리 속도가 급락하고 타임아웃이 발생함
            MAX_HISTORY_MESSAGES = 6  # 3턴 = assistant 3개 + user 3개
            memory_messages = self.get_memory_messages(session_id)
            if memory_messages:
                # 최근 3턴만 사용하여 컨텍스트 윈도우 절약
                recent_memory = (
                    memory_messages[-MAX_HISTORY_MESSAGES:]
                    if len(memory_messages) > MAX_HISTORY_MESSAGES
                    else memory_messages
                )
                messages.extend(recent_memory)
            else:
                # Memory가 없으면 수동 chat_history 사용 — 역시 최근 3턴만
                recent_history = (
                    chat_history[-MAX_HISTORY_MESSAGES:]
                    if len(chat_history) > MAX_HISTORY_MESSAGES
                    else chat_history
                )
                for msg in recent_history:
                    if msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
                    elif msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))

            # ========== 5. 이력서 RAG 컨텍스트 추가 ==========
            if resume_context:
                context_msg = f"\n--- [RAG System] 참고용 이력서 관련 내용 ---\n{resume_context}\n------------------------------------------"
                messages.append(SystemMessage(content=context_msg))

            # ========== 5-1. 면접 Q&A 참조 데이터 컨텍스트 추가 ==========
            if qa_reference_context:
                qa_msg = f"\n--- [RAG System] 면접 참고 자료 (모범 답변 DB) ---\n{qa_reference_context}\n이 참고 자료를 바탕으로 지원자의 답변 수준을 판단하고, 더 깊은 꼬리질문을 만들어주세요.\n------------------------------------------"
                messages.append(SystemMessage(content=qa_msg))

            # ========== 6. 질문 생성 프롬프트 (꼬리질문 정보 포함) ==========
            follow_up_instruction = ""
            if needs_follow_up and topic_count < 2:
                follow_up_instruction = f"""
⚠️ 지원자의 답변이 부실합니다. ({follow_up_reason})
꼬리질문을 해주세요. 현재 주제({current_topic})에서 {topic_count}번째 질문입니다.
더 구체적인 예시, 수치, 결과를 요청하세요."""
            elif topic_count >= 2:
                follow_up_instruction = """
✅ 이 주제에서 충분히 질문했습니다. 
"알겠습니다. 다음은..." 이라며 새로운 주제로 전환하세요."""

            question_prompt = build_question_prompt(
                question_count=question_count,
                max_questions=self.MAX_QUESTIONS,
                current_topic=current_topic,
                topic_count=topic_count,
                follow_up_instruction=follow_up_instruction,
            )

            messages.append(HumanMessage(content=question_prompt))

            # ========== 7. LLM 호출 - 비동기 ==========
            # ThreadPoolExecutor로 블로킹 LLM 호출을 비동기로 실행
            response = await run_llm_async(self.question_llm, messages)
            next_question = response.content.strip()

            # ========== 8. 주제 추적 업데이트 ==========
            self.update_topic_tracking(session_id, user_answer, needs_follow_up)

            # 질문 카운트 증가 (꼬리질문이 아닐 때만)
            if not needs_follow_up:
                state.update_session(session_id, {"question_count": question_count + 1})
            else:
                # 꼬리질문도 카운트에 포함 (총 질문 수 제한을 위해)
                state.update_session(session_id, {"question_count": question_count + 1})

            return next_question

        except Exception as e:
            print(f"LLM 질문 생성 오류: {e}")
            # 폴백 질문
            fallback = [
                "그 경험에서 가장 어려웠던 점은 무엇이었나요?",
                "구체적인 예시를 들어 설명해주실 수 있나요?",
                "그 결과는 어땠나요?",
                "다른 프로젝트 경험도 공유해주시겠어요?",
                "마지막으로 하고 싶은 말씀이 있으신가요?",
            ]
            return fallback[min(question_count, len(fallback) - 1)]

    async def evaluate_answer(
        self, session_id: str, question: str, answer: str
    ) -> Dict:
        """LLM을 사용하여 답변 평가"""
        if not self.llm:
            # LLM 없으면 기본 평가 반환
            return {
                "scores": {
                    "problem_solving": 3,
                    "logic": 3,
                    "technical": 3,
                    "star": 3,
                    "communication": 3,
                },
                "total_score": 15,
                "recommendation": "불합격",
                "recommendation_reason": "LLM 서비스 미사용으로 기본 평가 적용",
                "strengths": ["답변을 완료했습니다."],
                "improvements": ["더 구체적인 예시를 들어보세요."],
                "brief_feedback": "괜찮은 답변입니다.",
            }

        try:
            # RAG 컨텍스트 가져오기 - 비동기
            session = state.get_session(session_id)
            resume_context = ""
            if session:
                session_retriever = session.get("retriever") or self.retriever
                if session_retriever:
                    try:
                        # ThreadPoolExecutor로 블로킹 RAG 검색을 비동기로 실행
                        docs = await run_rag_async(session_retriever, answer)
                        if docs:
                            resume_context = "\n".join(
                                [d.page_content for d in docs[:2]]
                            )
                    except Exception:
                        pass

            # 평가 요청
            messages = [
                SystemMessage(content=self.EVALUATION_PROMPT),
                HumanMessage(
                    content=f"""
[질문]
{question}

[지원자 답변]
{answer}

{f"[참고: 이력서 내용]{chr(10)}{resume_context}" if resume_context else ""}

위 답변을 평가해주세요. 반드시 JSON 형식으로 응답해주세요.
"""
                ),
            ]

            # ThreadPoolExecutor로 블로킹 LLM 호출을 비동기로 실행
            response = await run_llm_async(self.llm, messages)
            response_text = response.content

            # JSON Resilience 파싱
            evaluation = parse_evaluation_json(
                response_text, context="AIInterviewer.evaluate_answer"
            )
            return evaluation

        except Exception as e:
            print(f"평가 오류: {e}")
            return {
                "scores": {
                    "problem_solving": 3,
                    "logic": 3,
                    "technical": 3,
                    "star": 3,
                    "communication": 3,
                },
                "total_score": 15,
                "recommendation": "불합격",
                "recommendation_reason": "평가 오류로 기본 평가 적용",
                "strengths": ["답변을 완료했습니다."],
                "improvements": ["더 구체적인 예시를 들어보세요."],
                "brief_feedback": "답변을 분석 중입니다.",
            }

    async def generate_response(
        self, session_id: str, user_input: str, use_rag: bool = True
    ) -> str:
        """사용자 답변을 저장하고 LLM으로 다음 질문 생성

        LangGraph 워크플로우가 활성화되면 StateGraph를 통해 실행하고,
        비활성화 시 기존 절차적 로직으로 폴백합니다.
        """
        # ========== LangGraph 워크플로우 경로 ==========
        if interview_workflow is not None:
            try:
                result = await interview_workflow.run(
                    session_id=session_id,
                    user_input=user_input,
                    use_rag=use_rag,
                    celery_available=CELERY_AVAILABLE,
                    llm_available=LLM_AVAILABLE,
                )
                response_text = result.get("response", "")
                if response_text:
                    return response_text
                # response가 빈 경우 폴백
                print("⚠️ [Workflow] 응답이 비어있음 → 절차적 로직으로 폴백")
            except Exception as e:
                print(f"⚠️ [Workflow] 실행 오류 → 절차적 로직으로 폴백: {e}")

        # ========== 절차적 폴백 경로 (기존 로직) ==========
        session = state.get_session(session_id)
        if not session:
            return "세션을 찾을 수 없습니다."

        # 대화 기록 업데이트
        chat_history = session.get("chat_history", [])

        # 특수 메시지 처리: [START] - 첫 번째 질문 반환 (자기소개)
        if user_input == "[START]":
            first_question = self.get_initial_greeting()
            chat_history.append({"role": "assistant", "content": first_question})
            state.update_session(
                session_id,
                {
                    "chat_history": chat_history,
                    "question_count": 1,  # 첫 번째 질문
                },
            )
            return first_question

        # 특수 메시지 처리: [NEXT] - 다음 질문만 요청
        if user_input == "[NEXT]":
            next_question = await self.generate_llm_question(session_id, "")
            chat_history.append({"role": "assistant", "content": next_question})
            state.update_session(session_id, {"chat_history": chat_history})
            return next_question

        # 일반 답변 처리
        # 사용자 답변 저장
        chat_history.append({"role": "user", "content": user_input})
        state.update_session(session_id, {"chat_history": chat_history})

        # LLM으로 다음 질문 생성과 백그라운드 평가를 처리
        # 이전 질문 가져오기 (평가용)
        previous_question = None
        for msg in reversed(chat_history[:-1]):  # 현재 답변 제외
            if msg["role"] == "assistant":
                previous_question = msg["content"]
                break

        # ========== Celery를 활용한 백그라운드 평가 ==========
        if CELERY_AVAILABLE and previous_question:
            # 평가를 Celery Worker로 오프로드 (비동기, 논블로킹)
            try:
                task = evaluate_answer_task.delay(
                    session_id,
                    previous_question,
                    user_input,
                    "",  # RAG 컨텍스트는 Worker에서 가져옴
                )
                # 태스크 ID 저장 (나중에 결과 조회용)
                pending_tasks = session.get("pending_eval_tasks", [])
                pending_tasks.append(
                    {
                        "task_id": task.id,
                        "question": previous_question,
                        "answer": user_input,
                        "submitted_at": time.time(),
                    }
                )
                state.update_session(session_id, {"pending_eval_tasks": pending_tasks})
                print(f"🚀 [Celery] 평가 태스크 제출됨: {task.id[:8]}...")
            except Exception as e:
                print(f"⚠️ Celery 태스크 제출 실패, 로컬 평가로 폴백: {e}")

        # 다음 질문 생성 (메인 스레드에서 빠르게 처리)
        next_question = await self.generate_llm_question(session_id, user_input)

        chat_history.append({"role": "assistant", "content": next_question})

        state.update_session(session_id, {"chat_history": chat_history})

        return next_question

    async def generate_speech(self, text: str) -> Optional[str]:
        """텍스트를 음성으로 변환"""
        if self.tts_service:
            try:
                return await self.tts_service.speak(text)
            except Exception as e:
                print(f"TTS 오류: {e}")
        return None

    async def collect_celery_evaluations(self, session_id: str) -> List[Dict]:
        """
        Celery에서 완료된 평가 결과를 수집하여 세션에 저장
        """
        session = state.get_session(session_id)
        if not session or not CELERY_AVAILABLE:
            return session.get("evaluations", []) if session else []

        pending_tasks = session.get("pending_eval_tasks", [])
        evaluations = session.get("evaluations", [])
        still_pending = []

        for task_info in pending_tasks:
            try:
                from celery.result import AsyncResult

                result = AsyncResult(task_info["task_id"])

                if result.ready():
                    if result.successful():
                        eval_result = result.get(timeout=1)
                        evaluations.append(
                            {
                                "question": task_info["question"],
                                "answer": task_info["answer"],
                                **eval_result,
                            }
                        )
                        print(
                            f"✅ [Celery] 평가 완료 수집: {task_info['task_id'][:8]}..."
                        )
                    else:
                        print(f"❌ [Celery] 평가 실패: {task_info['task_id'][:8]}...")
                else:
                    # 5분 이상 지난 태스크는 제거
                    if time.time() - task_info.get("submitted_at", 0) < 300:
                        still_pending.append(task_info)
            except Exception as e:
                print(f"⚠️ [Celery] 결과 수집 오류: {e}")

        # 세션 업데이트
        state.update_session(
            session_id,
            {"evaluations": evaluations, "pending_eval_tasks": still_pending},
        )

        return evaluations

    async def start_interview_completion_workflow(
        self, session_id: str
    ) -> Optional[str]:
        """
        면접 완료 시 백그라운드 워크플로우 시작 (Celery)
        리포트 생성, 통계 집계 등을 백그라운드에서 처리
        """
        if not CELERY_AVAILABLE:
            return None

        session = state.get_session(session_id)
        if not session:
            return None

        # 먼저 대기 중인 평가 결과 수집
        await self.collect_celery_evaluations(session_id)
        session = state.get_session(session_id)  # 업데이트된 세션 가져오기

        chat_history = session.get("chat_history", [])

        try:
            # 면접 완료 워크플로우를 백그라운드에서 실행
            task = complete_interview_workflow_task.delay(
                session_id, chat_history, session.get("emotion_images", [])
            )

            # 워크플로우 태스크 ID 저장
            state.update_session(
                session_id,
                {
                    "completion_workflow_task_id": task.id,
                    "completion_started_at": time.time(),
                },
            )

            print(f"🎯 [Celery] 면접 완료 워크플로우 시작: {task.id[:8]}...")
            return task.id

        except Exception as e:
            print(f"⚠️ [Celery] 워크플로우 시작 실패: {e}")
            return None


# AI 면접관 인스턴스
interviewer = AIInterviewer()

# ========== LangGraph 워크플로우 초기화 ==========
interview_workflow = None
if LANGGRAPH_AVAILABLE:
    try:
        _eb = event_bus if EVENT_BUS_AVAILABLE else None
        interview_workflow = init_workflow(state, interviewer, event_bus=_eb)
        print("✅ LangGraph InterviewWorkflow 초기화 완료")
    except Exception as e:
        print(f"⚠️ LangGraph 워크플로우 초기화 실패 (폴백 모드): {e}")
        interview_workflow = None


# ========== 면접 리포트 생성 ==========
class InterviewReportGenerator:
    """STAR 기법 기반 면접 리포트 생성"""

    STAR_KEYWORDS = {
        "situation": [
            "상황",
            "배경",
            "당시",
            "그때",
            "환경",
            "상태",
            "문제",
            "이슈",
            "과제",
        ],
        "task": [
            "목표",
            "과제",
            "임무",
            "역할",
            "담당",
            "책임",
            "해야 할",
            "목적",
            "미션",
        ],
        "action": [
            "행동",
            "수행",
            "실행",
            "처리",
            "해결",
            "개발",
            "구현",
            "적용",
            "진행",
            "시도",
            "노력",
        ],
        "result": [
            "결과",
            "성과",
            "달성",
            "완료",
            "개선",
            "향상",
            "증가",
            "감소",
            "효과",
            "성공",
        ],
    }

    TECH_KEYWORDS = [
        "python",
        "java",
        "javascript",
        "react",
        "vue",
        "django",
        "flask",
        "spring",
        "aws",
        "azure",
        "docker",
        "kubernetes",
        "sql",
        "mongodb",
        "postgresql",
        "git",
        "ci/cd",
        "api",
        "rest",
        "machine learning",
        "deep learning",
        "tensorflow",
        "pytorch",
        "pandas",
        "LLM",
        "RAG",
        "LangChain",
        "FastAPI",
    ]

    def __init__(self, llm=None):
        self.llm = llm or interviewer.llm

    def analyze_star_structure(self, answers: List[str]) -> Dict:
        """STAR 기법 분석"""
        star_analysis = {
            key: {"count": 0, "examples": []} for key in self.STAR_KEYWORDS
        }

        for answer in answers:
            answer_lower = answer.lower()
            for element, keywords in self.STAR_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in answer_lower:
                        star_analysis[element]["count"] += 1
                        break

        return star_analysis

    def extract_keywords(self, answers: List[str]) -> Dict:
        """키워드 추출"""
        all_text = " ".join(answers).lower()

        found_tech = []
        for kw in self.TECH_KEYWORDS:
            if kw.lower() in all_text:
                count = all_text.count(kw.lower())
                found_tech.append((kw, count))

        found_tech.sort(key=lambda x: x[1], reverse=True)

        korean_words = re.findall(r"[가-힣]{2,}", all_text)
        word_freq = Counter(korean_words)

        stopwords = [
            "그래서",
            "그리고",
            "하지만",
            "그런데",
            "있습니다",
            "했습니다",
            "합니다",
        ]
        for sw in stopwords:
            word_freq.pop(sw, None)

        return {
            "tech_keywords": found_tech[:10],
            "general_keywords": word_freq.most_common(15),
        }

    def calculate_metrics(self, answers: List[str]) -> Dict:
        """답변 메트릭 계산"""
        if not answers:
            return {"total": 0, "avg_length": 0}

        return {
            "total": len(answers),
            "avg_length": round(sum(len(a) for a in answers) / len(answers), 1),
            "total_chars": sum(len(a) for a in answers),
        }

    def generate_report(
        self, session_id: str, emotion_stats: Optional[Dict] = None
    ) -> Dict:
        """종합 리포트 생성"""
        session = state.get_session(session_id)
        if not session:
            return {"error": "세션을 찾을 수 없습니다."}

        chat_history = session.get("chat_history", [])
        answers = [msg["content"] for msg in chat_history if msg["role"] == "user"]

        star_analysis = self.analyze_star_structure(answers)
        keywords = self.extract_keywords(answers)
        metrics = self.calculate_metrics(answers)

        report = {
            "session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "star_analysis": {
                key: {"count": val["count"]} for key, val in star_analysis.items()
            },
            "keywords": keywords,
            "emotion_stats": emotion_stats,
            "feedback": self._generate_feedback(star_analysis, metrics, keywords),
        }

        return report

    def _generate_feedback(
        self, star_analysis: Dict, metrics: Dict, keywords: Dict
    ) -> List[str]:
        """피드백 생성"""
        feedback = []

        # STAR 분석 피드백
        weak_elements = [k for k, v in star_analysis.items() if v["count"] < 2]
        if weak_elements:
            element_names = {
                "situation": "상황(S)",
                "task": "과제(T)",
                "action": "행동(A)",
                "result": "결과(R)",
            }
            weak_names = [element_names[e] for e in weak_elements]
            feedback.append(
                f"📝 STAR 기법에서 {', '.join(weak_names)} 요소를 더 보완하면 좋겠습니다."
            )

        # 답변 길이 피드백
        if metrics.get("avg_length", 0) < 50:
            feedback.append("💡 답변을 더 구체적이고 상세하게 작성해보세요.")

        # 기술 키워드 피드백
        if not keywords.get("tech_keywords"):
            feedback.append("🔧 기술적인 용어와 도구를 더 활용해보세요.")

        if not feedback:
            feedback.append("✅ 전반적으로 좋은 답변 구조를 보여주셨습니다!")

        return feedback


# ========== 감정 분석 ==========
_redis_client: Optional[redis.Redis] = None
_ts_available: Optional[bool] = None


def get_redis() -> Optional[redis.Redis]:
    """Redis 클라이언트 반환"""
    global _redis_client
    if not REDIS_AVAILABLE:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL)
        except Exception:
            return None
    return _redis_client


def push_timeseries(key: str, ts_ms: int, value: float, labels: Dict[str, str]):
    """시계열 데이터 저장"""
    global _ts_available
    r = get_redis()
    if not r:
        return

    try:
        if _ts_available is not False:
            args = ["TS.ADD", key, ts_ms, value, "LABELS"]
            for k, v in labels.items():
                args.extend([k, v])
            r.execute_command(*args)
            _ts_available = True
            return
    except Exception:
        _ts_available = False

    try:
        r.zadd(key, {str(ts_ms): float(value)})
    except Exception:
        pass


async def analyze_emotions(track, session_id: str):
    """영상 프레임 감정 분석 + 배치 처리용 이미지 저장"""
    if not EMOTION_AVAILABLE:
        return

    sample_period = 1.0  # 실시간 분석은 1초마다
    batch_sample_period = 10.0  # 배치용 이미지는 10초마다 저장
    last_ts = 0.0
    last_batch_ts = 0.0

    try:
        while True:
            frame = await track.recv()
            now = time.monotonic()

            if now - last_ts < sample_period:
                continue
            last_ts = now

            try:
                img = frame.to_ndarray(format="bgr24")
            except Exception:
                continue

            try:
                # ThreadPoolExecutor로 블로킹 DeepFace 분석을 비동기로 실행
                res = await run_deepface_async(img, actions=["emotion"])
                item = res[0] if isinstance(res, list) else res
                scores = item.get("emotion", {})

                # 시선 추적: DeepFace의 face region 활용
                if GAZE_TRACKING_AVAILABLE and gaze_service:
                    try:
                        face_region = item.get("region")
                        if face_region:
                            frame_h, frame_w = img.shape[:2]
                            gaze_service.add_face_detection(
                                session_id, face_region, frame_w, frame_h
                            )
                    except Exception as e:
                        print(f"[GazeTracking] 데이터 전달 오류: {e}")

                keys_map = {
                    "happy": "happy",
                    "sad": "sad",
                    "angry": "angry",
                    "surprise": "surprise",
                    "fear": "fear",
                    "disgust": "disgust",
                    "neutral": "neutral",
                }
                raw = {k: float(scores.get(src, 0.0)) for k, src in keys_map.items()}
                total = sum(raw.values()) or 1.0
                probabilities = {k: (v / total) for k, v in raw.items()}

                data = {
                    "dominant_emotion": item.get("dominant_emotion"),
                    "probabilities": probabilities,
                    "raw_scores": raw,
                }

                async with state.emotion_lock:
                    state.last_emotion = data

                # Redis 저장
                ts_ms = int(time.time() * 1000)
                for emo, prob in probabilities.items():
                    key = f"emotion:{session_id}:{emo}"
                    push_timeseries(key, ts_ms, prob, {"session_id": session_id})

                # 배치 분석용 이미지 저장 (10초마다)
                if now - last_batch_ts >= batch_sample_period:
                    last_batch_ts = now
                    try:
                        import base64

                        import cv2

                        _, buffer = cv2.imencode(
                            ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70]
                        )
                        img_base64 = base64.b64encode(buffer).decode("utf-8")

                        # 세션에 이미지 저장 (최대 30개)
                        session = state.get_session(session_id)
                        if session:
                            emotion_images = session.get("emotion_images", [])
                            if len(emotion_images) < 30:
                                emotion_images.append(img_base64)
                                state.update_session(
                                    session_id, {"emotion_images": emotion_images}
                                )
                    except Exception:
                        pass

            except Exception:
                pass

    except Exception:
        pass


# ========== API 모델 ==========
class ChatRequest(BaseModel):
    session_id: str
    message: str
    use_rag: bool = True


class ChatResponse(BaseModel):
    session_id: str
    response: str
    audio_url: Optional[str] = None
    question_number: Optional[int] = None  # 현재 질문 번호 (프론트엔드 동기화용)


class SessionInfo(BaseModel):
    session_id: str
    status: str
    created_at: str
    message_count: int


class Offer(BaseModel):
    sdp: str
    type: str


# ========== 회원가입 모델 ==========
class UserRegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    birth_date: str  # YYYY-MM-DD 형식
    address: str
    gender: str  # male, female, other
    phone: Optional[str] = None  # 전화번호 (예: 010-1234-5678)
    role: str = "candidate"  # candidate(지원자), recruiter(면접관)


class UserRegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserLoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict] = None
    access_token: Optional[str] = None


# ========== API 엔드포인트 ==========


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "")


@app.get("/coding-test", response_class=HTMLResponse)
async def coding_test_page(request: Request):
    """코딩 테스트 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "coding")


@app.get("/interview", response_class=HTMLResponse)
async def interview_page(request: Request):
    """면접 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "interview")


# ========== Next.js 추가 페이지 프록시 ==========


@app.get("/_next/{path:path}")
async def nextjs_assets(request: Request, path: str):
    """Next.js 정적 자산 프록시 (_next/static, _next/data 등)"""
    query = str(request.url.query)
    target_url = f"{NEXTJS_URL}/_next/{path}" + (f"?{query}" if query else "")
    skip_headers = {"host", "content-length"}
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in skip_headers
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(target_url, headers=fwd_headers)
            content_type = resp.headers.get("content-type", "application/octet-stream")
            from fastapi.responses import Response

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={
                    "content-type": content_type,
                    "cache-control": resp.headers.get("cache-control", ""),
                },
            )
    except Exception:
        raise HTTPException(status_code=502, detail="Next.js 서버에 연결할 수 없습니다")


@app.api_route("/__nextjs_original-stack-frame", methods=["GET"])
@app.api_route("/__nextjs_original-stack-frames", methods=["GET"])
async def nextjs_devtools(request: Request):
    """Next.js 개발 도구 내부 라우트 프록시"""
    return await _proxy_to_nextjs(request, request.url.path.lstrip("/"))


@app.get("/favicon.ico")
async def favicon(request: Request):
    """파비콘 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "favicon.ico")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """내 정보 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "profile")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """회원정보 수정 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "settings")


@app.get("/whiteboard", response_class=HTMLResponse)
async def whiteboard_page(request: Request):
    """화이트보드 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "whiteboard")


@app.get("/coding", response_class=HTMLResponse)
async def coding_page(request: Request):
    """코딩 테스트 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "coding")


# ========== 소셜 로그인 API ==========

# 소셜 로그인 토큰 저장소 (임시)
social_tokens: Dict[str, Dict] = {}


@app.get("/api/auth/social/{provider}")
async def social_login_redirect(provider: str):
    """소셜 로그인 리다이렉트"""
    from fastapi.responses import RedirectResponse

    redirect_uri = f"{OAUTH_REDIRECT_BASE}/api/auth/social/{provider}/callback"

    if provider == "kakao":
        if not KAKAO_CLIENT_ID:
            return JSONResponse(
                status_code=400,
                content={"error": "카카오 로그인이 설정되지 않았습니다."},
            )
        auth_url = (
            f"https://kauth.kakao.com/oauth/authorize"
            f"?client_id={KAKAO_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
        )

    elif provider == "google":
        if not GOOGLE_CLIENT_ID:
            return JSONResponse(
                status_code=400, content={"error": "구글 로그인이 설정되지 않았습니다."}
            )
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=email%20profile"
        )

    elif provider == "naver":
        if not NAVER_CLIENT_ID:
            return JSONResponse(
                status_code=400,
                content={"error": "네이버 로그인이 설정되지 않았습니다."},
            )
        state = uuid.uuid4().hex
        auth_url = (
            f"https://nid.naver.com/oauth2.0/authorize"
            f"?client_id={NAVER_CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&state={state}"
        )
    else:
        return JSONResponse(
            status_code=400, content={"error": f"지원하지 않는 소셜 로그인: {provider}"}
        )

    return RedirectResponse(url=auth_url)


@app.get("/api/auth/social/{provider}/callback")
async def social_login_callback(
    provider: str, code: str = None, state: str = None, error: str = None
):
    """소셜 로그인 콜백"""
    import httpx
    from fastapi.responses import RedirectResponse

    if error:
        return RedirectResponse(url=f"/?error={error}")

    if not code:
        return RedirectResponse(url="/?error=authorization_failed")

    redirect_uri = f"{OAUTH_REDIRECT_BASE}/api/auth/social/{provider}/callback"

    try:
        async with httpx.AsyncClient() as client:
            # 액세스 토큰 교환
            if provider == "kakao":
                token_response = await client.post(
                    "https://kauth.kakao.com/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": KAKAO_CLIENT_ID,
                        "client_secret": KAKAO_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")

                # 사용자 정보 조회
                user_response = await client.get(
                    "https://kapi.kakao.com/v2/user/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_data = user_response.json()

                email = user_data.get("kakao_account", {}).get(
                    "email", f"kakao_{user_data['id']}@kakao.local"
                )
                name = user_data.get("properties", {}).get("nickname", "카카오사용자")

            elif provider == "google":
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")

                # 사용자 정보 조회
                user_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_data = user_response.json()

                email = user_data.get("email", f"google_{user_data['id']}@google.local")
                name = user_data.get("name", "구글사용자")

            elif provider == "naver":
                token_response = await client.post(
                    "https://nid.naver.com/oauth2.0/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": NAVER_CLIENT_ID,
                        "client_secret": NAVER_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code": code,
                        "state": state,
                    },
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")

                # 사용자 정보 조회
                user_response = await client.get(
                    "https://openapi.naver.com/v1/nid/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_data = user_response.json()
                response_data = user_data.get("response", {})

                email = response_data.get(
                    "email", f"naver_{response_data.get('id')}@naver.local"
                )
                name = response_data.get("name") or response_data.get(
                    "nickname", "네이버사용자"
                )

            else:
                return RedirectResponse(url="/?error=invalid_provider")

            # 사용자 등록 또는 조회 (DB 우선)
            existing_user = get_user_by_email(email)
            if not existing_user:
                user_data = {
                    "email": email,
                    "password_hash": "",  # 소셜 로그인은 비밀번호 없음
                    "name": name,
                    "birth_date": None,
                    "address": None,
                    "gender": None,
                    "role": "candidate",
                }
                create_user(user_data)
                # 저장된 사용자 조회하여 ID 가져오기
                saved_user = get_user_by_email(email)
                user_id = saved_user["user_id"] if saved_user else None
                print(f"✅ 소셜 회원 가입: {name} ({email}) via {provider}")
            else:
                user_id = existing_user["user_id"]
                print(f"✅ 소셜 로그인: {name} ({email}) via {provider}")

            # 임시 토큰 생성
            temp_token = uuid.uuid4().hex
            social_tokens[temp_token] = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "provider": provider,
                "created_at": datetime.now().isoformat(),
            }

            return RedirectResponse(url=f"/?token={temp_token}")

    except Exception as e:
        print(f"❌ 소셜 로그인 오류: {e}")
        return RedirectResponse(url="/?error=login_failed")


@app.get("/api/auth/social/verify")
async def verify_social_token(token: str):
    """소셜 로그인 토큰 검증"""
    token_data = social_tokens.pop(token, None)

    if not token_data:
        return {"success": False, "message": "유효하지 않은 토큰입니다."}

    # DB에서 사용자 조회
    user = get_user_by_email(token_data["email"])
    if not user:
        return {"success": False, "message": "사용자를 찾을 수 없습니다."}

    return {
        "success": True,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "provider": user.get("provider"),
            "gender": user.get("gender"),
        },
    }


@app.get("/api/auth/social/status")
async def social_login_status():
    """소셜 로그인 설정 상태 확인"""
    return {
        "kakao": bool(KAKAO_CLIENT_ID),
        "google": bool(GOOGLE_CLIENT_ID),
        "naver": bool(NAVER_CLIENT_ID),
    }


# ========== 회원가입/로그인 API ==========


@app.get("/api/auth/check-email")
async def check_email_duplicate(email: str):
    """이메일 중복 확인 API"""
    import re

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return {"available": False, "message": "올바른 이메일 형식이 아닙니다."}

    existing_user = get_user_by_email(email)
    if existing_user:
        return {"available": False, "message": "이미 등록된 이메일입니다."}

    return {"available": True, "message": "사용 가능한 이메일입니다."}


@app.post("/api/auth/register", response_model=UserRegisterResponse)
async def register_user(request: UserRegisterRequest):
    """회원가입 API"""
    # 이메일 중복 확인 (DB 우선, 폴백으로 메모리)
    existing_user = get_user_by_email(request.email)
    if existing_user:
        return UserRegisterResponse(success=False, message="이미 등록된 이메일입니다.")

    # 이메일 형식 검증
    import re

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, request.email):
        return UserRegisterResponse(
            success=False, message="올바른 이메일 형식이 아닙니다."
        )

    # 생년월일 검증
    try:
        birth = datetime.strptime(request.birth_date, "%Y-%m-%d")
        if birth > datetime.now():
            return UserRegisterResponse(
                success=False, message="생년월일이 올바르지 않습니다."
            )
    except ValueError:
        return UserRegisterResponse(
            success=False, message="생년월일 형식이 올바르지 않습니다. (YYYY-MM-DD)"
        )

    # 성별 검증
    if request.gender not in ["male", "female"]:
        return UserRegisterResponse(success=False, message="성별을 선택해주세요.")

    # 역할 검증
    if request.role not in ["candidate", "recruiter"]:
        return UserRegisterResponse(
            success=False, message="회원 유형을 선택해주세요. (지원자 또는 면접관)"
        )

    # 비밀번호 검증
    if len(request.password) < 8:
        return UserRegisterResponse(
            success=False, message="비밀번호는 8자 이상이어야 합니다."
        )

    # 비밀번호 해싱 (bcrypt 기반 보안 해싱)
    password_hash = hash_password(request.password)

    # 회원 정보 저장 (DB 우선)
    user_data = {
        "email": request.email,
        "password_hash": password_hash,
        "name": request.name,
        "birth_date": request.birth_date,
        "address": request.address,
        "gender": request.gender,
        "phone": request.phone,  # 전화번호
        "role": request.role,  # 사용자가 선택한 역할
    }

    # DB에 저장
    create_user(user_data)

    # 저장된 사용자 조회하여 ID 가져오기
    saved_user = get_user_by_email(request.email)
    user_id = saved_user["user_id"] if saved_user else None

    role_text = "지원자" if request.role == "candidate" else "면접관"
    print(f"✅ 새 회원 가입: {request.name} ({request.email}) - {role_text}")

    return UserRegisterResponse(
        success=True, message="회원가입이 완료되었습니다.", user_id=user_id
    )


@app.post("/api/auth/login")
async def login_user(request: UserLoginRequest):
    """════ 로그인 API (이메일 + 비밀번호) ════
    성공 시: HTTP 200 + {success, user, access_token}
    실패 시: HTTP 401 + {detail: "에러 메시지"}
    """
    # DB에서 사용자 조회
    user = get_user_by_email(request.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="등록되지 않은 이메일입니다. 회원가입을 먼저 해주세요.",
        )

    # 비밀번호 검증 (bcrypt + SHA-256 하위 호환)
    if not verify_password(request.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 올바르지 않습니다.",
        )

    # SHA-256 → bcrypt 자동 마이그레이션
    if needs_rehash(user.get("password_hash", "")):
        new_hash = hash_password(request.password)
        update_user(request.email, {"password_hash": new_hash})
        print(f"🔄 비밀번호 해시 마이그레이션 완료: {request.email} (SHA-256 → bcrypt)")

    # 민감 정보 제외하고 반환 (password_hash 등 제외)
    user_info = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "birth_date": user.get("birth_date"),
        "gender": user.get("gender"),
        "address": user.get("address"),
        "phone": user.get("phone"),
        "role": user.get("role", "candidate"),
    }

    # JWT 액세스 토큰 발급
    access_token = create_access_token(
        data={
            "sub": user["email"],
            "user_id": str(user["user_id"]),
            "name": user["name"],
            "role": user.get("role", "candidate"),
        }
    )

    print(f"✅ 로그인: {user['name']} ({user['email']})")

    return {
        "success": True,
        "message": "로그인 성공",
        "user": user_info,
        "access_token": access_token,
    }


# ========== 비밀번호 찾기 모델 ==========
class PasswordVerifyRequest(BaseModel):
    email: str
    name: str
    birth_date: str  # YYYY-MM-DD


class PasswordResetRequest(BaseModel):
    email: str
    new_password: str
    name: str
    birth_date: str


@app.post("/api/auth/verify-identity")
async def verify_identity(request: PasswordVerifyRequest):
    """비밀번호 찾기 - 본인 확인 (이메일 + 이름 + 생년월일)"""
    user = get_user_by_email(request.email)

    if not user:
        return {"success": False, "message": "등록되지 않은 이메일입니다."}

    # 본인 확인: 이름과 생년월일 매칭
    if user.get("name") != request.name:
        return {"success": False, "message": "이름이 일치하지 않습니다."}

    # 생년월일 비교 (형식 정규화)
    user_birth = str(user.get("birth_date", "")).replace("-", "")
    request_birth = request.birth_date.replace("-", "")

    if user_birth != request_birth:
        return {"success": False, "message": "생년월일이 일치하지 않습니다."}

    print(f"✅ 본인 확인 성공: {request.email}")
    return {"success": True, "message": "본인 확인 완료. 새 비밀번호를 설정해주세요."}


@app.post("/api/auth/reset-password")
async def reset_password(request: PasswordResetRequest):
    """비밀번호 재설정"""
    # 다시 한번 본인 확인
    user = get_user_by_email(request.email)

    if not user:
        return {"success": False, "message": "등록되지 않은 이메일입니다."}

    # 본인 확인 재검증
    if user.get("name") != request.name:
        return {"success": False, "message": "본인 확인에 실패했습니다."}

    user_birth = str(user.get("birth_date", "")).replace("-", "")
    request_birth = request.birth_date.replace("-", "")

    if user_birth != request_birth:
        return {"success": False, "message": "본인 확인에 실패했습니다."}

    # 비밀번호 유효성 검사
    if len(request.new_password) < 8:
        return {"success": False, "message": "비밀번호는 8자 이상이어야 합니다."}

    # 새 비밀번호 해시 (bcrypt)
    new_password_hash = hash_password(request.new_password)

    # 비밀번호 업데이트
    success = update_user(request.email, {"password_hash": new_password_hash})

    if success:
        print(f"✅ 비밀번호 재설정 완료: {request.email}")
        return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}
    else:
        return {"success": False, "message": "비밀번호 변경에 실패했습니다."}


@app.get("/api/auth/user/{email}")
async def get_user_info_api(email: str, current_user: Dict = Depends(get_current_user)):
    """회원 정보 조회 (인증 필요)"""
    # 본인 정보만 조회 가능
    if current_user["email"] != email:
        raise HTTPException(status_code=403, detail="본인 정보만 조회할 수 있습니다.")
    # DB에서 사용자 조회
    user = get_user_by_email(email)

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    # 민감 정보 제외
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "birth_date": user["birth_date"],
        "address": user["address"],
        "gender": user["gender"],
        "phone": user.get("phone"),
        "created_at": user["created_at"],
    }


# ========== 프론트엔드 호환 래퍼 API (GET/PUT /api/user) ==========


@app.get("/api/user")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """현재 로그인 유저 정보 조회 (토큰 기반)"""
    user = get_user_by_email(current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "birth_date": user.get("birth_date"),
        "address": user.get("address"),
        "gender": user.get("gender"),
        "phone": user.get("phone"),
        "role": user.get("role"),
        "created_at": user.get("created_at"),
    }


@app.put("/api/user")
async def update_current_user_info(
    data: dict, current_user: Dict = Depends(get_current_user)
):
    """현재 로그인 유저 정보 수정 (토큰 기반)"""
    req = UserUpdateRequest(email=current_user["email"], **data)
    return await update_user_info(req, current_user)


# ========== 회원 정보 수정 모델 ==========
class UserUpdateRequest(BaseModel):
    email: str
    name: Optional[str] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None  # 전화번호
    role: Optional[str] = None  # candidate(지원자), recruiter(인사담당자)
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class UserUpdateResponse(BaseModel):
    success: bool
    message: str


@app.put("/api/auth/user/update")
async def update_user_info(
    request: UserUpdateRequest, current_user: Dict = Depends(get_current_user)
):
    """회원 정보 수정 API (인증 필요)"""

    # 사용자 존재 확인
    user = get_user_by_email(request.email)
    if not user:
        return UserUpdateResponse(success=False, message="사용자를 찾을 수 없습니다.")

    # 업데이트할 데이터 준비
    update_data = {}

    if request.name:
        update_data["name"] = request.name
    if request.birth_date:
        update_data["birth_date"] = request.birth_date
    if request.address is not None:
        update_data["address"] = request.address
    if request.gender:
        if request.gender not in ["male", "female"]:
            return UserUpdateResponse(
                success=False, message="올바른 성별을 선택해주세요."
            )
        update_data["gender"] = request.gender

    # 전화번호 수정
    if request.phone is not None:
        update_data["phone"] = request.phone

    # 회원 유형(role) 수정
    if request.role:
        if request.role not in ["candidate", "recruiter"]:
            return UserUpdateResponse(
                success=False,
                message="올바른 회원 유형을 선택해주세요. (지원자 또는 인사담당자)",
            )
        update_data["role"] = request.role

    # 비밀번호 변경
    if request.new_password:
        if not request.current_password:
            return UserUpdateResponse(
                success=False, message="현재 비밀번호를 입력해주세요."
            )

        # 현재 비밀번호 확인 (bcrypt + SHA-256 하위 호환)
        if not verify_password(request.current_password, user.get("password_hash", "")):
            return UserUpdateResponse(
                success=False, message="현재 비밀번호가 일치하지 않습니다."
            )

        if len(request.new_password) < 8:
            return UserUpdateResponse(
                success=False, message="새 비밀번호는 8자 이상이어야 합니다."
            )

        update_data["password_hash"] = hash_password(request.new_password)

    # 업데이트 실행
    if update_data:
        success = update_user(request.email, update_data)
        if success:
            print(f"✅ 회원 정보 수정: {request.email}")
            return UserUpdateResponse(
                success=True, message="회원정보가 수정되었습니다."
            )
        else:
            return UserUpdateResponse(
                success=False, message="회원정보 수정에 실패했습니다."
            )

    return UserUpdateResponse(success=True, message="변경된 정보가 없습니다.")


# ========== 회원 탈퇴 ==========
class UserDeleteRequest(BaseModel):
    """회원 탈퇴 요청 — 이메일과 비밀번호로 본인 확인 후 삭제"""

    email: str
    password: str


class UserDeleteResponse(BaseModel):
    success: bool
    message: str


@app.post("/api/auth/user/delete")
async def delete_user_account(
    request: UserDeleteRequest, current_user: Dict = Depends(get_current_user)
):
    """
    회원 탈퇴 API (인증 필요)
    - 이메일 + 비밀번호로 본인 확인
    - 확인되면 DB에서 사용자 레코드를 완전히 삭제
    """
    # 1) 현재 로그인한 사용자와 요청 이메일이 일치하는지 확인
    if current_user.get("email") != request.email:
        return UserDeleteResponse(
            success=False, message="본인 계정만 탈퇴할 수 있습니다."
        )

    # 2) DB에서 사용자 조회
    user = get_user_by_email(request.email)
    if not user:
        return UserDeleteResponse(success=False, message="사용자를 찾을 수 없습니다.")

    # 3) 비밀번호 확인 (bcrypt + SHA-256 하위 호환)
    if not verify_password(request.password, user.get("password_hash", "")):
        return UserDeleteResponse(
            success=False, message="비밀번호가 일치하지 않습니다."
        )

    # 4) DB에서 사용자 삭제
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                db_user = db.query(User).filter(User.email == request.email).first()
                if db_user:
                    db.delete(db_user)
                    db.commit()
                    print(f"🗑️ 회원 탈퇴 완료: {request.email}")
                    return UserDeleteResponse(
                        success=True,
                        message="회원 탈퇴가 완료되었습니다. 이용해 주셔서 감사합니다.",
                    )
            except Exception as e:
                db.rollback()
                print(f"❌ 회원 탈퇴 실패: {e}")
                return UserDeleteResponse(
                    success=False, message="회원 탈퇴 처리 중 오류가 발생했습니다."
                )
            finally:
                db.close()

    # 폴백: 메모리 저장소
    if request.email in users_db:
        del users_db[request.email]
        print(f"🗑️ (메모리) 회원 탈퇴 완료: {request.email}")
        return UserDeleteResponse(success=True, message="회원 탈퇴가 완료되었습니다.")

    return UserDeleteResponse(success=False, message="회원 탈퇴에 실패했습니다.")


# ========== GDPR '잊힐 권리' (Right to be Forgotten) 일괄 삭제 API ==========
# REQ-N-003: GDPR 대응을 위해 사용자의 모든 개인정보를 한 번에 영구 삭제
# 삭제 대상: 계정 정보, 이력서(파일+DB), 면접 세션, 녹화 파일, 감정 분석 데이터, 채팅 이력


class GDPRDeleteRequest(BaseModel):
    """GDPR 일괄 삭제 요청 — 비밀번호로 본인 확인"""

    password: str  # 본인 확인용 비밀번호
    confirm: bool = False  # 삭제 확인 (true여야 진행)


class GDPRDeleteResponse(BaseModel):
    """GDPR 일괄 삭제 응답"""

    success: bool
    message: str
    deleted_items: Optional[Dict[str, Any]] = None  # 삭제된 항목별 상세 내역


@app.post("/api/gdpr/delete-all-data")
async def gdpr_delete_all_user_data(
    request: GDPRDeleteRequest, current_user: Dict = Depends(get_current_user)
):
    """
    GDPR '잊힐 권리' (Right to be Forgotten) 일괄 삭제 API (인증 필요)

    사용자의 모든 개인 데이터를 영구적으로 삭제합니다:
    1. 이력서 파일 (uploads/ 디렉토리에서 물리적 삭제)
    2. 이력서 DB 레코드 (user_resumes 테이블)
    3. 녹화 파일 (recording 서비스)
    4. 감정 분석 데이터 (Redis 키)
    5. 면접 세션 데이터 (인메모리)
    6. 채용 공고 (본인 작성 공고)
    7. 사용자 계정 (users 테이블)

    이 작업은 되돌릴 수 없습니다.
    """
    user_email = current_user.get("email", "")
    deleted_items = {
        "resumes_files": 0,
        "resumes_db": 0,
        "recordings": 0,
        "emotion_keys": 0,
        "sessions": 0,
        "job_postings": 0,
        "account": False,
    }

    # ── 0) 사전 검증 ──
    if not request.confirm:
        return GDPRDeleteResponse(
            success=False, message="삭제를 확인하려면 confirm=true로 설정해야 합니다."
        )

    # 비밀번호 본인 확인
    user_record = get_user_by_email(user_email)
    if not user_record:
        return GDPRDeleteResponse(success=False, message="사용자를 찾을 수 없습니다.")

    if not verify_password(request.password, user_record.get("password_hash", "")):
        return GDPRDeleteResponse(
            success=False, message="비밀번호가 일치하지 않습니다."
        )

    print(f"🗑️ [GDPR] 사용자 전체 데이터 삭제 시작: {user_email}")

    # ── 1) 이력서 파일 삭제 (물리적 삭제) ──
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                resumes = (
                    db.query(UserResume)
                    .filter(UserResume.user_email == user_email)
                    .all()
                )
                for resume in resumes:
                    # 파일 시스템에서 물리적 삭제
                    if resume.file_path and os.path.exists(resume.file_path):
                        try:
                            os.remove(resume.file_path)
                            deleted_items["resumes_files"] += 1
                            print(f"  🗑️ 이력서 파일 삭제: {resume.file_path}")
                        except Exception as e:
                            print(
                                f"  ⚠️ 이력서 파일 삭제 실패: {resume.file_path} - {e}"
                            )
                    # 암호화 파일(.enc)도 함께 삭제
                    enc_path = resume.file_path + ".enc" if resume.file_path else None
                    if enc_path and os.path.exists(enc_path):
                        try:
                            os.remove(enc_path)
                            print(f"  🗑️ 암호화 이력서 삭제: {enc_path}")
                        except Exception:
                            pass
                # DB 레코드 삭제
                resume_count = (
                    db.query(UserResume)
                    .filter(UserResume.user_email == user_email)
                    .delete()
                )
                deleted_items["resumes_db"] = resume_count
                db.commit()
                print(f"  🗑️ 이력서 DB 레코드 삭제: {resume_count}건")
            except Exception as e:
                db.rollback()
                print(f"  ⚠️ 이력서 삭제 중 오류: {e}")
            finally:
                db.close()

    # ── 2) 녹화 파일 삭제 ──
    if RECORDING_AVAILABLE and recording_service:
        try:
            all_recordings = recording_service.get_all_recordings()
            for rec in all_recordings:
                # 세션 데이터에서 사용자 이메일과 매칭
                session_id = rec.get("session_id", "")
                session = state.get_session(session_id)
                if session and session.get("user_email") == user_email:
                    recording_service.delete_recording(session_id)
                    deleted_items["recordings"] += 1
                    print(f"  🗑️ 녹화 삭제: {session_id}")
        except Exception as e:
            print(f"  ⚠️ 녹화 삭제 중 오류: {e}")

    # ── 3) 감정 분석 데이터 삭제 (Redis) ──
    r = get_redis()
    if r:
        try:
            # 사용자의 세션 ID 목록 수집
            user_session_ids = [
                sid
                for sid, sess in state.sessions.items()
                if sess.get("user_email") == user_email
            ]
            for session_id in user_session_ids:
                # emotion:* 키 패턴으로 삭제
                pattern = f"emotion:{session_id}:*"
                keys = r.keys(pattern)
                if keys:
                    r.delete(*keys)
                    deleted_items["emotion_keys"] += len(keys)
                    print(
                        f"  🗑️ 감정 데이터 삭제: {len(keys)}개 키 (세션: {session_id})"
                    )
        except Exception as e:
            print(f"  ⚠️ 감정 데이터 삭제 중 오류: {e}")

    # ── 4) 면접 세션 데이터 삭제 (인메모리) ──
    sessions_to_delete = [
        sid
        for sid, sess in state.sessions.items()
        if sess.get("user_email") == user_email
    ]
    for session_id in sessions_to_delete:
        # uploads/ 내 세션별 이력서 파일도 삭제
        session = state.sessions.get(session_id, {})
        resume_path = session.get("resume_path")
        if resume_path and os.path.exists(resume_path):
            try:
                os.remove(resume_path)
                print(f"  🗑️ 세션 이력서 삭제: {resume_path}")
            except Exception:
                pass
        del state.sessions[session_id]
        deleted_items["sessions"] += 1
    print(f"  🗑️ 세션 데이터 삭제: {deleted_items['sessions']}건")

    # ── 5) 채용 공고 삭제 (본인 작성 공고) ──
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                jp_count = (
                    db.query(JobPosting)
                    .filter(JobPosting.recruiter_email == user_email)
                    .delete()
                )
                deleted_items["job_postings"] = jp_count
                db.commit()
                print(f"  🗑️ 채용 공고 삭제: {jp_count}건")
            except Exception as e:
                db.rollback()
                print(f"  ⚠️ 채용 공고 삭제 중 오류: {e}")
            finally:
                db.close()

    # ── 6) 사용자 계정 삭제 (최종 단계) ──
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                db_user = db.query(User).filter(User.email == user_email).first()
                if db_user:
                    db.delete(db_user)
                    db.commit()
                    deleted_items["account"] = True
                    print(f"  🗑️ 사용자 계정 삭제: {user_email}")
            except Exception as e:
                db.rollback()
                print(f"  ⚠️ 계정 삭제 중 오류: {e}")
            finally:
                db.close()

    # 폴백: 메모리 저장소
    if not deleted_items["account"] and user_email in users_db:
        del users_db[user_email]
        deleted_items["account"] = True

    print(f"✅ [GDPR] 사용자 전체 데이터 삭제 완료: {user_email}")
    print(f"   삭제 내역: {deleted_items}")

    return GDPRDeleteResponse(
        success=True,
        message="GDPR '잊힐 권리'에 따라 모든 개인 데이터가 영구 삭제되었습니다.",
        deleted_items=deleted_items,
    )


# ========== 채용 공고 API (Job Postings) ==========


# ── Pydantic 모델 ──
class JobPostingCreateRequest(BaseModel):
    """채용 공고 등록 요청"""

    title: str
    company: str
    location: Optional[str] = None
    job_category: Optional[str] = None
    experience_level: Optional[str] = None
    description: str
    salary_info: Optional[str] = None
    deadline: Optional[str] = None  # YYYY-MM-DD


class JobPostingUpdateRequest(BaseModel):
    """채용 공고 수정 요청 — 변경할 필드만 전송"""

    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    job_category: Optional[str] = None
    experience_level: Optional[str] = None
    description: Optional[str] = None
    salary_info: Optional[str] = None
    status: Optional[str] = None  # open / closed
    deadline: Optional[str] = None


def _job_posting_to_dict(jp) -> Dict:
    """JobPosting ORM 객체 → dict 변환 헬퍼"""
    return {
        "id": jp.id,
        "recruiter_email": jp.recruiter_email,
        "title": jp.title,
        "company": jp.company,
        "location": jp.location,
        "job_category": jp.job_category,
        "experience_level": jp.experience_level,
        "description": jp.description,
        "salary_info": jp.salary_info,
        "status": jp.status,
        "created_at": jp.created_at.isoformat() if jp.created_at else None,
        "updated_at": jp.updated_at.isoformat() if jp.updated_at else None,
        "deadline": jp.deadline,
    }


# ── 메모리 폴백 저장소 (DB 미연결 시) ──
job_postings_memory: list = []
job_posting_id_counter = 0


@app.get("/api/job-postings")
async def list_job_postings(status: Optional[str] = "open"):
    """
    채용 공고 목록 조회 (누구나 접근 가능)
    - status 파라미터로 필터링 (기본: open)
    - status=all 이면 전체 조회
    """
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                query = db.query(JobPosting)
                if status and status != "all":
                    query = query.filter(JobPosting.status == status)
                postings = query.order_by(JobPosting.created_at.desc()).all()
                return {"postings": [_job_posting_to_dict(p) for p in postings]}
            except Exception as e:
                print(f"❌ 공고 목록 조회 실패: {e}")
                raise HTTPException(status_code=500, detail="공고 목록 조회 실패")
            finally:
                db.close()
    # 메모리 폴백
    filtered = (
        job_postings_memory
        if status == "all"
        else [p for p in job_postings_memory if p["status"] == status]
    )
    return {
        "postings": sorted(
            filtered, key=lambda x: x.get("created_at", ""), reverse=True
        )
    }


@app.get("/api/job-postings/{posting_id}")
async def get_job_posting(posting_id: int):
    """채용 공고 상세 조회"""
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                jp = db.query(JobPosting).filter(JobPosting.id == posting_id).first()
                if not jp:
                    raise HTTPException(
                        status_code=404, detail="공고를 찾을 수 없습니다."
                    )
                return _job_posting_to_dict(jp)
            except HTTPException:
                raise
            except Exception as e:
                print(f"❌ 공고 상세 조회 실패: {e}")
                raise HTTPException(status_code=500, detail="공고 조회 실패")
            finally:
                db.close()
    # 메모리 폴백
    for p in job_postings_memory:
        if p["id"] == posting_id:
            return p
    raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")


@app.post("/api/job-postings")
async def create_job_posting(
    request: JobPostingCreateRequest, current_user: Dict = Depends(get_current_user)
):
    """
    채용 공고 등록 (인사담당자만 가능)
    - role이 'recruiter'인 사용자만 공고를 등록할 수 있음
    """
    # 권한 확인: 인사담당자만 공고 등록 가능
    if current_user.get("role") != "recruiter":
        raise HTTPException(
            status_code=403, detail="인사담당자만 공고를 등록할 수 있습니다."
        )

    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                jp = JobPosting(
                    recruiter_email=current_user["email"],
                    title=request.title,
                    company=request.company,
                    location=request.location,
                    job_category=request.job_category,
                    experience_level=request.experience_level,
                    description=request.description,
                    salary_info=request.salary_info,
                    deadline=request.deadline,
                    status="open",
                )
                db.add(jp)
                db.commit()
                db.refresh(jp)
                print(f"📋 공고 등록: {jp.title} (by {current_user['email']})")
                return {
                    "success": True,
                    "message": "공고가 등록되었습니다.",
                    "posting": _job_posting_to_dict(jp),
                }
            except Exception as e:
                db.rollback()
                print(f"❌ 공고 등록 실패: {e}")
                import traceback

                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"공고 등록 실패: {str(e)}")
            finally:
                db.close()

    # 메모리 폴백
    global job_posting_id_counter
    job_posting_id_counter += 1
    posting = {
        "id": job_posting_id_counter,
        "recruiter_email": current_user["email"],
        "title": request.title,
        "company": request.company,
        "location": request.location,
        "job_category": request.job_category,
        "experience_level": request.experience_level,
        "description": request.description,
        "salary_info": request.salary_info,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "deadline": request.deadline,
    }
    job_postings_memory.append(posting)
    return {"success": True, "message": "공고가 등록되었습니다.", "posting": posting}


@app.put("/api/job-postings/{posting_id}")
async def update_job_posting(
    posting_id: int,
    request: JobPostingUpdateRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    채용 공고 수정 (작성자 본인만 가능)
    """
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                jp = db.query(JobPosting).filter(JobPosting.id == posting_id).first()
                if not jp:
                    raise HTTPException(
                        status_code=404, detail="공고를 찾을 수 없습니다."
                    )
                # 작성자 본인만 수정 가능
                if jp.recruiter_email != current_user.get("email"):
                    raise HTTPException(
                        status_code=403,
                        detail="본인이 작성한 공고만 수정할 수 있습니다.",
                    )
                # 변경된 필드만 업데이트
                update_fields = request.dict(exclude_unset=True)
                for field, value in update_fields.items():
                    if value is not None:
                        setattr(jp, field, value)
                db.commit()
                db.refresh(jp)
                print(f"✏️ 공고 수정: {jp.title} (id={posting_id})")
                return {
                    "success": True,
                    "message": "공고가 수정되었습니다.",
                    "posting": _job_posting_to_dict(jp),
                }
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                print(f"❌ 공고 수정 실패: {e}")
                raise HTTPException(status_code=500, detail="공고 수정 실패")
            finally:
                db.close()

    # 메모리 폴백
    for p in job_postings_memory:
        if p["id"] == posting_id:
            if p["recruiter_email"] != current_user.get("email"):
                raise HTTPException(
                    status_code=403, detail="본인이 작성한 공고만 수정할 수 있습니다."
                )
            update_fields = request.dict(exclude_unset=True)
            for field, value in update_fields.items():
                if value is not None:
                    p[field] = value
            p["updated_at"] = datetime.utcnow().isoformat()
            return {"success": True, "message": "공고가 수정되었습니다.", "posting": p}
    raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")


@app.delete("/api/job-postings/{posting_id}")
async def delete_job_posting(
    posting_id: int, current_user: Dict = Depends(get_current_user)
):
    """
    채용 공고 삭제 (작성자 본인만 가능)
    """
    if DB_AVAILABLE:
        db = get_db()
        if db:
            try:
                jp = db.query(JobPosting).filter(JobPosting.id == posting_id).first()
                if not jp:
                    raise HTTPException(
                        status_code=404, detail="공고를 찾을 수 없습니다."
                    )
                if jp.recruiter_email != current_user.get("email"):
                    raise HTTPException(
                        status_code=403,
                        detail="본인이 작성한 공고만 삭제할 수 있습니다.",
                    )
                db.delete(jp)
                db.commit()
                print(f"🗑️ 공고 삭제: id={posting_id}")
                return {"success": True, "message": "공고가 삭제되었습니다."}
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                print(f"❌ 공고 삭제 실패: {e}")
                raise HTTPException(status_code=500, detail="공고 삭제 실패")
            finally:
                db.close()

    # 메모리 폴백
    for i, p in enumerate(job_postings_memory):
        if p["id"] == posting_id:
            if p["recruiter_email"] != current_user.get("email"):
                raise HTTPException(
                    status_code=403, detail="본인이 작성한 공고만 삭제할 수 있습니다."
                )
            job_postings_memory.pop(i)
            return {"success": True, "message": "공고가 삭제되었습니다."}
    raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")


# ========== Resume Upload API ==========


class ResumeUploadResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    filename: Optional[str] = None
    chunks_created: Optional[int] = None


@app.post("/api/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    user_email: Optional[str] = Form(None),
    current_user: Dict = Depends(get_current_user),
):
    """
    이력서 PDF 파일 업로드 및 RAG 인덱싱
    """
    # 파일 형식 검증
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    # 파일 크기 검증 (10MB 제한)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다."
        )

    # 세션 생성 또는 조회
    if not session_id:
        session_id = state.create_session()
    else:
        session = state.get_session(session_id)
        if not session:
            session_id = state.create_session(session_id)

    # 사용자 이메일을 세션에 저장 (대시보드에서 업로드 시 면접 세션과 연결하기 위해)
    if user_email:
        state.update_session(session_id, {"user_email": user_email})

    # 파일 저장
    safe_filename = f"{session_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(contents)
        print(f"✅ 이력서 저장 완료: {file_path}")

        # REQ-N-003: 저장 시 AES-256-GCM 암호화
        # 원본 파일을 암호화하고, 원본은 즉시 삭제하여 평문 데이터 노출 방지
        if AES_ENCRYPTION_AVAILABLE:
            encrypted_path = encrypt_file(file_path)
            if encrypted_path and encrypted_path != file_path:
                # 원본 평문 파일 삭제 (암호화 파일로 대체)
                os.remove(file_path)
                file_path = encrypted_path
                print(f"🔒 이력서 AES-256 암호화 완료: {file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")

    # RAG 인덱싱
    chunks_created = 0
    if RAG_AVAILABLE:
        try:
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING")

            if connection_string:
                # 이력서 전용 RAG 인스턴스 생성
                session_rag = ResumeRAG(
                    table_name=RESUME_TABLE, connection_string=connection_string
                )

                # PDF 인덱싱
                print(f"📚 이력서 인덱싱 시작: {file_path}")
                num_chunks = session_rag.load_and_index_pdf(file_path)

                # 세션에 retriever 저장
                retriever = session_rag.get_retriever()
                state.update_session(
                    session_id,
                    {
                        "resume_uploaded": True,
                        "resume_path": file_path,
                        "resume_filename": file.filename,
                        "retriever": retriever,
                    },
                )

                chunks_created = num_chunks if num_chunks else 1
                print(f"✅ RAG 인덱싱 완료: {RESUME_TABLE}")
            else:
                print("⚠️ POSTGRES_CONNECTION_STRING 미설정, RAG 비활성화")
                state.update_session(
                    session_id,
                    {
                        "resume_uploaded": True,
                        "resume_path": file_path,
                        "resume_filename": file.filename,
                    },
                )
        except Exception as e:
            print(f"❌ RAG 인덱싱 오류: {e}")
            # RAG 실패해도 파일은 저장되었으므로 성공 반환
            state.update_session(
                session_id,
                {
                    "resume_uploaded": True,
                    "resume_path": file_path,
                    "resume_filename": file.filename,
                },
            )
    else:
        # RAG 비활성화 상태에서도 파일 정보 저장
        state.update_session(
            session_id,
            {
                "resume_uploaded": True,
                "resume_path": file_path,
                "resume_filename": file.filename,
            },
        )

    # 📤 이벤트 발행: 이력서 업로드
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.RESUME_UPLOADED,
            session_id=session_id,
            user_email=user_email,
            data={"filename": file.filename, "chunks_created": chunks_created},
            source="resume_api",
        )

    # ── DB에 이력서 메타데이터 영구 저장 ──
    # 서버 재시작/재로그인 시에도 이력서를 자동 복원하기 위해 PostgreSQL에 저장합니다.
    resolved_email = user_email or current_user.get("email")
    if DB_AVAILABLE and resolved_email:
        try:
            db = SessionLocal()
            try:
                # 기존 활성 이력서를 비활성화 (한 사용자당 최신 1개만 active)
                db.query(UserResume).filter(
                    UserResume.user_email == resolved_email, UserResume.is_active == 1
                ).update({"is_active": 0})

                # 새 이력서 레코드 저장
                new_resume = UserResume(
                    user_email=resolved_email,
                    filename=file.filename,
                    file_path=file_path,
                    file_size=len(contents),
                    is_active=1,
                )
                db.add(new_resume)
                db.commit()
                print(f"✅ 이력서 DB 저장 완료: {resolved_email} → {file.filename}")
            finally:
                db.close()
        except Exception as e:
            print(f"⚠️ 이력서 DB 저장 실패 (세션에는 저장됨): {e}")

    return ResumeUploadResponse(
        success=True,
        message="이력서가 성공적으로 업로드되었습니다."
        + (" RAG 인덱싱이 완료되어 면접 질문에 반영됩니다." if RAG_AVAILABLE else ""),
        session_id=session_id,
        filename=file.filename,
        chunks_created=chunks_created if chunks_created > 0 else None,
    )


@app.get("/api/resume/status/{session_id}")
async def get_resume_status(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 이력서 업로드 상태 확인 (인증 필요)"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    return {
        "session_id": session_id,
        "resume_uploaded": session.get("resume_uploaded", False),
        "resume_filename": session.get("resume_filename"),
        "rag_enabled": session.get("retriever") is not None,
    }


@app.delete("/api/resume/{session_id}")
async def delete_resume(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 이력서 삭제 (인증 필요)"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    resume_path = session.get("resume_path")
    if resume_path and os.path.exists(resume_path):
        try:
            os.remove(resume_path)
            print(f"✅ 이력서 삭제 완료: {resume_path}")
        except Exception as e:
            print(f"❌ 이력서 삭제 실패: {e}")

    state.update_session(
        session_id,
        {
            "resume_uploaded": False,
            "resume_path": None,
            "resume_filename": None,
            "retriever": None,
        },
    )

    # DB에서도 이력서 비활성화 (영구 삭제 아닌 soft delete)
    user_email = session.get("user_email") or current_user.get("email")
    if DB_AVAILABLE and user_email:
        try:
            db = SessionLocal()
            try:
                db.query(UserResume).filter(
                    UserResume.user_email == user_email, UserResume.is_active == 1
                ).update({"is_active": 0})
                db.commit()
                print(f"✅ 이력서 DB 비활성화 완료: {user_email}")
            finally:
                db.close()
        except Exception as e:
            print(f"⚠️ 이력서 DB 비활성화 실패: {e}")

    return {"success": True, "message": "이력서가 삭제되었습니다."}


@app.get("/api/resume/user/{user_email}")
async def get_user_resume(
    user_email: str, current_user: Dict = Depends(get_current_user)
):
    """
    사용자의 영구 저장된 이력서 조회 (DB 기반).
    로그인 시 대시보드에서 호출하여 이전에 업로드한 이력서를 자동 표시합니다.
    서버 재시작 후에도 이력서 정보가 유지됩니다.
    """
    if not DB_AVAILABLE:
        return {"resume_exists": False, "message": "DB 비활성화 상태"}

    try:
        db = SessionLocal()
        try:
            # 해당 사용자의 최신 활성 이력서 조회
            resume = (
                db.query(UserResume)
                .filter(UserResume.user_email == user_email, UserResume.is_active == 1)
                .order_by(UserResume.uploaded_at.desc())
                .first()
            )

            if resume and os.path.exists(resume.file_path):
                return {
                    "resume_exists": True,
                    "filename": resume.filename,
                    "file_path": resume.file_path,
                    "file_size": resume.file_size,
                    "uploaded_at": resume.uploaded_at.isoformat()
                    if resume.uploaded_at
                    else None,
                }
            elif resume:
                # DB 레코드는 있지만 실제 파일이 없는 경우 → 비활성화
                resume.is_active = 0
                db.commit()
                return {
                    "resume_exists": False,
                    "message": "이력서 파일이 삭제되었습니다.",
                }
            else:
                return {"resume_exists": False}
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 이력서 조회 오류: {e}")
        return {"resume_exists": False, "error": str(e)}


# ========== 면접 Q&A 참조 데이터 인덱싱 API ==========

# 인덱싱 상태 추적
_qa_index_status = {"status": "idle", "indexed": 0, "total": 0, "error": None}


@app.post("/api/qa-data/index")
async def index_qa_data(current_user: Dict = Depends(get_current_user)):
    """
    Data/data.json 면접 Q&A 데이터를 RAG 시스템에 인덱싱합니다.
    인덱싱 후 LLM이 면접 시 참조 가능한 모범 답변 데이터베이스가 구축됩니다.
    (인증 필요, 관리자용)
    """
    global _qa_index_status

    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG 서비스가 비활성화 상태입니다.")

    if _qa_index_status["status"] == "indexing":
        return {
            "success": False,
            "message": "이미 인덱싱이 진행 중입니다.",
            "status": _qa_index_status,
        }

    # data.json 경로
    json_path = os.path.join(root_dir, "Data", "data.json")
    if not os.path.exists(json_path):
        raise HTTPException(
            status_code=404, detail=f"데이터 파일을 찾을 수 없습니다: {json_path}"
        )

    _qa_index_status = {"status": "indexing", "indexed": 0, "total": 0, "error": None}

    try:
        # 별도 컬렉션으로 인덱싱 (이력서 데이터와 분리)
        rag = ResumeRAG(table_name=QA_TABLE)

        # 비동기 실행 (대량 데이터이므로 ThreadPool 사용)
        indexed_count = await run_in_executor(
            RAG_EXECUTOR, rag.load_and_index_json, json_path, 100
        )

        _qa_index_status = {
            "status": "completed",
            "indexed": indexed_count,
            "total": indexed_count,
            "error": None,
        }
        print(f"✅ 면접 Q&A 데이터 인덱싱 완료: {indexed_count}개 청크")

        return {
            "success": True,
            "message": f"면접 Q&A 데이터 인덱싱 완료: {indexed_count}개 청크가 저장되었습니다.",
            "chunks_indexed": indexed_count,
        }
    except Exception as e:
        _qa_index_status = {
            "status": "error",
            "indexed": 0,
            "total": 0,
            "error": str(e),
        }
        print(f"❌ Q&A 인덱싱 실패: {e}")
        raise HTTPException(status_code=500, detail=f"인덱싱 실패: {str(e)}")


@app.get("/api/qa-data/status")
async def qa_data_status(current_user: Dict = Depends(get_current_user)):
    """Q&A 데이터 인덱싱 상태 조회 (인증 필요)"""
    return _qa_index_status


@app.get("/api/qa-data/search")
async def search_qa_data(
    q: str, k: int = 4, current_user: Dict = Depends(get_current_user)
):
    """
    인덱싱된 면접 Q&A 데이터에서 관련 내용을 검색합니다.
    질문과 유사한 모범 답변을 반환합니다.
    """
    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG 서비스가 비활성화 상태입니다.")

    try:
        rag = ResumeRAG(table_name=QA_TABLE)
        results = rag.similarity_search(q, k=k)

        return {
            "success": True,
            "query": q,
            "results": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                }
                for doc in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


# ========== 대시보드 페이지 ==========


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """대시보드 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "dashboard")


@app.get("/legacy/dashboard")
async def legacy_dashboard_page(request: Request):
    """레거시 대시보드 → Next.js 대시보드로 리디렉트"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/dashboard", status_code=302)


# ========== 면접 이력 조회 API ==========


@app.get("/api/interviews")
async def get_interviews_list(
    email: str, current_user: Dict = Depends(get_current_user)
):
    """면접 이력 목록 조회 (프론트엔드 호환)"""
    return await get_interview_history(email, current_user)


@app.get("/api/interview/history")
async def get_interview_history(
    email: str, current_user: Dict = Depends(get_current_user)
):
    """사용자 이메일 기준 면접 이력 조회 (인증 필요)"""
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    history = []
    for sid, session in state.sessions.items():
        if session.get("user_email") == email and session.get("status") in (
            "completed",
            "active",
        ):
            chat_history = session.get("chat_history", [])
            evaluations = session.get("evaluations", [])

            # 평균 점수 계산
            avg_score = None
            if evaluations:
                total = sum(e.get("total_score", 0) for e in evaluations)
                avg_score = round(total / len(evaluations), 1)

            # 요약 생성
            q_count = sum(1 for m in chat_history if m.get("role") == "assistant")
            a_count = sum(1 for m in chat_history if m.get("role") == "user")
            summary = f"질문 {q_count}개 · 답변 {a_count}개"

            history.append(
                {
                    "session_id": sid,
                    "date": session.get("created_at", ""),
                    "summary": summary,
                    "score": avg_score,
                    "status": session.get("status"),
                    "message_count": len(chat_history),
                }
            )

    # 최신순 정렬
    history.sort(key=lambda x: x["date"], reverse=True)

    return history


# ========== 세션 생성 요청 모델 ==========
class SessionCreateRequest(BaseModel):
    user_email: Optional[str] = None
    user_id: Optional[str] = None
    job_posting_id: Optional[int] = None  # 선택한 채용 공고 ID (공고 기반 면접 시)


# ========== Session API ==========


@app.post("/api/session/create")
@app.post("/api/session")
async def create_session(
    request: SessionCreateRequest = None, current_user: Dict = Depends(get_current_user)
):
    """새 면접 세션 생성 (인증 필요)"""
    # 사용자 인증 확인
    if not request or not request.user_email:
        raise HTTPException(
            status_code=401, detail="면접을 시작하려면 로그인이 필요합니다."
        )

    # 사용자 존재 여부 확인
    user = get_user_by_email(request.user_email)
    if not user:
        raise HTTPException(
            status_code=401, detail="유효하지 않은 사용자입니다. 다시 로그인해주세요."
        )

    session_id = state.create_session()

    # ── 채용 공고 기반 면접: 공고 정보를 세션에 저장 ──
    job_posting_context = None
    if request.job_posting_id:
        try:
            if DB_AVAILABLE:
                db = get_db()
                if db:
                    try:
                        jp = (
                            db.query(JobPosting)
                            .filter(JobPosting.id == request.job_posting_id)
                            .first()
                        )
                        if jp:
                            job_posting_context = {
                                "id": jp.id,
                                "title": jp.title,
                                "company": jp.company,
                                "location": jp.location,
                                "job_category": jp.job_category,
                                "experience_level": jp.experience_level,
                                "description": jp.description,
                                "salary_info": jp.salary_info,
                            }
                            print(f"📋 공고 기반 면접: [{jp.company}] {jp.title}")
                    finally:
                        db.close()
            # 메모리 폴백
            if not job_posting_context:
                for p in job_postings_memory:
                    if p["id"] == request.job_posting_id:
                        job_posting_context = {
                            k: p.get(k)
                            for k in [
                                "id",
                                "title",
                                "company",
                                "location",
                                "job_category",
                                "experience_level",
                                "description",
                                "salary_info",
                            ]
                        }
                        break
        except Exception as e:
            print(f"⚠️ 공고 조회 실패 (세션 생성 계속): {e}")

    greeting = interviewer.get_initial_greeting(job_posting_context)

    # 초기 인사 저장 (사용자 정보 + 공고 컨텍스트 포함)
    session_data = {
        "status": "active",
        "user_email": request.user_email,
        "user_id": request.user_id,
        "user_name": user.get("name", ""),
        "chat_history": [{"role": "assistant", "content": greeting}],
    }
    # 공고 정보가 있으면 세션에 저장 (LLM 질문 생성 시 활용)
    if job_posting_context:
        session_data["job_posting"] = job_posting_context
    state.update_session(session_id, session_data)

    # 같은 사용자가 이전에 업로드한 이력서(RAG retriever)가 있으면 새 세션으로 복사
    # 1차: 인메모리 세션에서 검색 (서버가 살아있는 동안 가장 빠름)
    resume_restored = False
    for sid, s in state.sessions.items():
        if (
            sid != session_id
            and s.get("user_email") == request.user_email
            and s.get("resume_uploaded")
        ):
            retriever = s.get("retriever")
            if retriever:
                state.update_session(
                    session_id,
                    {
                        "resume_uploaded": True,
                        "resume_path": s.get("resume_path"),
                        "resume_filename": s.get("resume_filename"),
                        "retriever": retriever,
                    },
                )
                print(f"📚 이전 세션({sid[:8]})의 이력서 RAG를 새 세션에 연결함")
                resume_restored = True
                break

    # 2차: DB에서 이력서 복원 (서버 재시작 후에도 이력서 유지)
    # 인메모리에 없는 경우, DB에 저장된 이력서 파일 경로를 확인하고
    # RAG retriever를 다시 생성하여 세션에 연결합니다.
    if not resume_restored and DB_AVAILABLE:
        try:
            db = SessionLocal()
            try:
                saved_resume = (
                    db.query(UserResume)
                    .filter(
                        UserResume.user_email == request.user_email,
                        UserResume.is_active == 1,
                    )
                    .order_by(UserResume.uploaded_at.desc())
                    .first()
                )

                if saved_resume and os.path.exists(saved_resume.file_path):
                    print(f"📚 DB에서 이력서 복원 시도: {saved_resume.filename}")

                    # RAG retriever 재생성
                    retriever = None
                    if RAG_AVAILABLE:
                        try:
                            connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
                            if connection_string:
                                session_rag = ResumeRAG(
                                    table_name=RESUME_TABLE,
                                    connection_string=connection_string,
                                )
                                retriever = session_rag.get_retriever()
                                print("✅ DB 이력서 RAG retriever 복원 완료")
                        except Exception as rag_err:
                            print(
                                f"⚠️ RAG retriever 복원 실패 (이력서 파일은 유지): {rag_err}"
                            )

                    state.update_session(
                        session_id,
                        {
                            "resume_uploaded": True,
                            "resume_path": saved_resume.file_path,
                            "resume_filename": saved_resume.filename,
                            "retriever": retriever,
                        },
                    )
                    resume_restored = True
                    print(f"✅ DB에서 이력서 복원 완료: {saved_resume.filename}")
            finally:
                db.close()
        except Exception as e:
            print(f"⚠️ DB 이력서 복원 실패: {e}")

    print(f"✅ 면접 세션 생성: {session_id} (사용자: {request.user_email})")

    # 📤 이벤트 발행: 세션 생성
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.SESSION_CREATED,
            session_id=session_id,
            user_email=request.user_email,
            data={"greeting": greeting[:100]},
            source="session_manager",
        )

    # 이력서 업로드 여부 확인 — 프론트엔드에 경고 메시지 전달 (UX 개선)
    session = state.get_session(session_id)
    resume_uploaded = session.get("resume_uploaded", False) if session else False

    return {
        "session_id": session_id,
        "greeting": greeting,
        "status": "active",
        "resume_uploaded": resume_uploaded,
        # 이력서가 없으면 경고 메시지 포함
        "resume_warning": None
        if resume_uploaded
        else (
            "이력서가 업로드되지 않았습니다. "
            "이력서를 업로드하면 맞춤형 면접 질문을 받을 수 있습니다."
        ),
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str, current_user: Dict = Depends(get_current_user)):
    """세션 정보 조회 (인증 필요)"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    return SessionInfo(
        session_id=session["id"],
        status=session["status"],
        created_at=session["created_at"],
        message_count=len(session.get("chat_history", [])),
    )


# ========== 실시간 개입 API (VAD + Turn-taking) ==========


class VADSignalRequest(BaseModel):
    session_id: str
    is_speech: bool
    audio_level: float = 0.0
    timestamp: Optional[str] = None


class InterventionCheckRequest(BaseModel):
    session_id: str
    current_answer: Optional[str] = None


class StartUserTurnRequest(BaseModel):
    session_id: str
    question: str


@app.post("/api/intervention/start-turn")
async def start_user_turn(
    request: StartUserTurnRequest, current_user: Dict = Depends(get_current_user)
):
    """사용자 발화 시작 - 질문 후 호출 (인증 필요)"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # 질문에서 키워드 추출
    keywords = intervention_manager.extract_question_keywords(request.question)

    # 사용자 턴 시작
    intervention_manager.start_user_turn(request.session_id, keywords)

    return {
        "success": True,
        "message": "사용자 발화 시작됨",
        "question_keywords": keywords,
        "max_time_seconds": intervention_manager.MAX_ANSWER_TIME_SECONDS,
        "warning_time_seconds": intervention_manager.SOFT_WARNING_TIME,
    }


@app.post("/api/intervention/vad-signal")
async def update_vad_signal(
    request: VADSignalRequest, current_user: Dict = Depends(get_current_user)
):
    """VAD 신호 업데이트 (실시간 스트리밍)"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # VAD 신호 업데이트
    turn_state = intervention_manager.update_vad_signal(
        request.session_id, request.is_speech, request.audio_level
    )

    # Turn-taking 신호 확인
    turn_signal = intervention_manager.get_turn_taking_signal(request.session_id)

    return {
        "turn_state": turn_state,
        "can_interrupt": turn_signal["can_interrupt"],
        "interrupt_reason": turn_signal.get("interrupt_reason", ""),
        "silence_duration_ms": turn_signal.get("silence_duration_ms", 0),
    }


@app.post("/api/intervention/check")
async def check_intervention(
    request: InterventionCheckRequest, current_user: Dict = Depends(get_current_user)
):
    """개입 필요 여부 확인"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # 개입 체크
    intervention = intervention_manager.check_intervention_needed(
        request.session_id, request.current_answer
    )

    # Turn-taking 신호
    turn_signal = intervention_manager.get_turn_taking_signal(request.session_id)

    if intervention:
        return {
            "needs_intervention": True,
            "intervention": intervention,
            "turn_signal": turn_signal,
        }

    return {
        "needs_intervention": False,
        "intervention": None,
        "turn_signal": turn_signal,
    }


@app.post("/api/intervention/end-turn")
async def end_user_turn(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """사용자 발화 종료"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    stats = intervention_manager.end_user_turn(session_id)

    return {"success": True, "stats": stats}


@app.get("/api/intervention/stats/{session_id}")
async def get_intervention_stats(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 개입 통계 조회"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    stats = intervention_manager.get_session_stats(session_id)

    return {
        "session_id": session_id,
        "total_interventions": stats["total_interventions"],
        "intervention_history": stats["intervention_history"],
        "current_state": {
            "turn_state": stats["state"].get("turn_state", "unknown"),
            "is_speaking": stats["state"].get("is_speaking", False),
            "intervention_count": stats["state"].get("intervention_count", 0),
        },
    }


class InterventionSettingsRequest(BaseModel):
    max_answer_time: Optional[int] = None
    max_answer_length: Optional[int] = None
    soft_warning_time: Optional[int] = None
    topic_relevance_threshold: Optional[float] = None


@app.post("/api/intervention/settings")
async def update_intervention_settings(
    request: InterventionSettingsRequest, current_user: Dict = Depends(get_current_user)
):
    """개입 설정 업데이트"""
    if request.max_answer_time:
        intervention_manager.MAX_ANSWER_TIME_SECONDS = request.max_answer_time
    if request.max_answer_length:
        intervention_manager.MAX_ANSWER_LENGTH = request.max_answer_length
    if request.soft_warning_time:
        intervention_manager.SOFT_WARNING_TIME = request.soft_warning_time
    if request.topic_relevance_threshold:
        intervention_manager.TOPIC_RELEVANCE_THRESHOLD = (
            request.topic_relevance_threshold
        )

    return {
        "success": True,
        "current_settings": {
            "max_answer_time_seconds": intervention_manager.MAX_ANSWER_TIME_SECONDS,
            "max_answer_length": intervention_manager.MAX_ANSWER_LENGTH,
            "soft_warning_time_seconds": intervention_manager.SOFT_WARNING_TIME,
            "topic_relevance_threshold": intervention_manager.TOPIC_RELEVANCE_THRESHOLD,
        },
    }


@app.get("/api/intervention/settings")
async def get_intervention_settings(current_user: Dict = Depends(get_current_user)):
    """현재 개입 설정 조회"""
    return {
        "max_answer_time_seconds": intervention_manager.MAX_ANSWER_TIME_SECONDS,
        "max_answer_length": intervention_manager.MAX_ANSWER_LENGTH,
        "soft_warning_time_seconds": intervention_manager.SOFT_WARNING_TIME,
        "soft_warning_length": intervention_manager.SOFT_WARNING_LENGTH,
        "silence_threshold_ms": intervention_manager.SILENCE_THRESHOLD_MS,
        "topic_relevance_threshold": intervention_manager.TOPIC_RELEVANCE_THRESHOLD,
    }


# ========== Chat API ==========


class ChatRequestWithIntervention(BaseModel):
    session_id: str
    message: str
    use_rag: bool = True
    was_interrupted: bool = False  # 개입으로 인한 강제 종료 여부
    intervention_type: Optional[str] = None  # 개입 유형


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, req: Request, current_user: Dict = Depends(get_current_user)
):
    """채팅 메시지 전송 및 AI 응답 받기"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # 사용자 입력 텍스트 정제 (STT 중복 누적 완화)
    sanitized_message = sanitize_user_input(request.message)

    # ── 지연 시간 측정용 request_id (미들웨어에서 부여) ──
    rid = getattr(req.state, "request_id", None)

    # 사용자 턴 종료 처리 (개입 시스템)
    turn_stats = intervention_manager.end_user_turn(request.session_id)

    # 발화 분석 턴 종료
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_service.end_turn(request.session_id, sanitized_message)
        except Exception as e:
            print(f"[SpeechAnalysis] 턴 종료 오류: {e}")

    # 시선 추적 턴 종료
    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_service.end_turn(request.session_id)
        except Exception as e:
            print(f"[GazeTracking] 턴 종료 오류: {e}")

    # AI 응답 생성 — LLM 추론 단계 측정 (REQ-N-001)
    if rid:
        latency_monitor.start_phase(rid, "llm_inference")
    response = await interviewer.generate_response(
        request.session_id, sanitized_message, request.use_rag
    )
    if rid:
        latency_monitor.end_phase(rid, "llm_inference")

    # 다음 질문을 위한 사용자 턴 시작 (개입 시스템)
    if not response.startswith("면접이 종료"):
        keywords = intervention_manager.extract_question_keywords(response)
        intervention_manager.start_user_turn(request.session_id, keywords)

        # 발화 분석 턴 시작
        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
            try:
                turn_idx = session.get("current_question_idx", 0)
                speech_service.start_turn(request.session_id, turn_idx)
            except Exception as e:
                print(f"[SpeechAnalysis] 턴 시작 오류: {e}")

        # 시선 추적 턴 시작
        if GAZE_TRACKING_AVAILABLE and gaze_service:
            try:
                turn_idx = session.get("current_question_idx", 0)
                gaze_service.start_turn(request.session_id, turn_idx)
            except Exception as e:
                print(f"[GazeTracking] 턴 시작 오류: {e}")

    # TTS 생성 (선택적) — TTS 합성 단계 측정 (REQ-N-001)
    audio_url = None
    if TTS_AVAILABLE and interviewer.tts_service:
        try:
            if rid:
                latency_monitor.start_phase(rid, "tts_synthesis")
            audio_file = await interviewer.generate_speech(response)
            if rid:
                latency_monitor.end_phase(rid, "tts_synthesis")
            if audio_file:
                audio_url = f"/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            if rid:
                latency_monitor.end_phase(rid, "tts_synthesis")
            print(f"TTS 생성 오류: {e}")

    # 📤 이벤트 발행: 질문 생성 + 답변 제출
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.ANSWER_SUBMITTED,
            session_id=request.session_id,
            data={"answer": sanitized_message[:200], "question": response[:200]},
            source="chat_api",
        )
        await event_bus.publish(
            AppEventType.QUESTION_GENERATED,
            session_id=request.session_id,
            data={"question": response[:200], "has_audio": audio_url is not None},
            source="ai_interviewer",
        )

    # 세션에서 현재 질문 번호 가져오기 (프론트엔드와 동기화)
    current_session = state.get_session(request.session_id)
    current_q_num = current_session.get("question_count", 1) if current_session else 1

    return ChatResponse(
        session_id=request.session_id,
        response=response,
        audio_url=audio_url,
        question_number=current_q_num,
    )


@app.post("/api/chat/with-intervention")
async def chat_with_intervention(
    request: ChatRequestWithIntervention,
    req: Request,
    current_user: Dict = Depends(get_current_user),
):
    """개입 정보를 포함한 채팅 메시지 전송"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # ── 지연 시간 측정용 request_id ──
    rid = getattr(req.state, "request_id", None)

    # 사용자 턴 종료 처리
    turn_stats = intervention_manager.end_user_turn(request.session_id)

    # 발화 분석 / 시선 추적 턴 종료
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_service.end_turn(request.session_id, request.message)
        except Exception:
            pass
    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_service.end_turn(request.session_id)
        except Exception:
            pass

    # 개입으로 인한 강제 종료인 경우 로깅
    if request.was_interrupted:
        print(
            f"⚡ [Chat] 세션 {request.session_id[:8]}... 개입으로 인한 답변 종료 ({request.intervention_type})"
        )

    # AI 응답 생성 — LLM 추론 단계 측정 (REQ-N-001)
    if rid:
        latency_monitor.start_phase(rid, "llm_inference")
    response = await interviewer.generate_response(
        request.session_id, request.message, request.use_rag
    )
    if rid:
        latency_monitor.end_phase(rid, "llm_inference")

    # 다음 질문을 위한 사용자 턴 시작
    question_keywords = []
    if not response.startswith("면접이 종료"):
        question_keywords = intervention_manager.extract_question_keywords(response)
        intervention_manager.start_user_turn(request.session_id, question_keywords)

        # 발화 분석 / 시선 추적 턴 시작
        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
            try:
                turn_idx = session.get("current_question_idx", 0)
                speech_service.start_turn(request.session_id, turn_idx)
            except Exception:
                pass
        if GAZE_TRACKING_AVAILABLE and gaze_service:
            try:
                turn_idx = session.get("current_question_idx", 0)
                gaze_service.start_turn(request.session_id, turn_idx)
            except Exception:
                pass

    # TTS 생성 — TTS 합성 단계 측정 (REQ-N-001)
    audio_url = None
    if TTS_AVAILABLE and interviewer.tts_service:
        try:
            if rid:
                latency_monitor.start_phase(rid, "tts_synthesis")
            audio_file = await interviewer.generate_speech(response)
            if rid:
                latency_monitor.end_phase(rid, "tts_synthesis")
            if audio_file:
                audio_url = f"/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            if rid:
                latency_monitor.end_phase(rid, "tts_synthesis")
            print(f"TTS 생성 오류: {e}")

    return {
        "session_id": request.session_id,
        "response": response,
        "audio_url": audio_url,
        "turn_stats": turn_stats,
        "was_interrupted": request.was_interrupted,
        "next_question_keywords": question_keywords,
    }


# ========== 평가 통계 헬퍼 ==========

EVAL_SCORE_KEYS = ["problem_solving", "logic", "technical", "star", "communication"]

# 비언어 등급 → 점수 변환 (5점 만점)
_GRADE_TO_SCORE = {"S": 5.0, "A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}


def _compute_nonverbal_scores(report: Dict) -> Dict:
    """
    비언어 평가 데이터(발화·시선·감정·Prosody)를 점수화하여 반환.
    각 항목 5점 만점으로 통일. 데이터가 없으면 해당 키를 포함하지 않는다.
    """
    nonverbal: Dict[str, float] = {}

    # ── 1. 발화 분석 (발화속도 등급 + 발음 등급 평균) ──
    speech = report.get("speech_analysis")
    if speech:
        scores = []
        sr_grade = speech.get("speech_rate_grade", "")
        if sr_grade in _GRADE_TO_SCORE:
            scores.append(_GRADE_TO_SCORE[sr_grade])
        pn_grade = speech.get("pronunciation_grade", "")
        if pn_grade in _GRADE_TO_SCORE:
            scores.append(_GRADE_TO_SCORE[pn_grade])
        if scores:
            nonverbal["speech"] = round(sum(scores) / len(scores), 1)

    # ── 2. 시선 추적 (아이컨택 등급) ──
    gaze = report.get("gaze_analysis")
    if gaze:
        ec_grade = gaze.get("eye_contact_grade", "")
        if ec_grade in _GRADE_TO_SCORE:
            nonverbal["gaze"] = _GRADE_TO_SCORE[ec_grade]

    # ── 3. 감정 분석 (neutral 비율 → 안정성 점수) ──
    emotion = report.get("emotion_stats")
    if emotion:
        probs = emotion.get("probabilities") or emotion.get("emotion") or {}
        if probs:
            neutral_ratio = probs.get("neutral", 0)
            happy_ratio = probs.get("happy", 0)
            positive = neutral_ratio + happy_ratio
            # positive 비율이 높을수록 안정적
            if positive >= 0.7:
                nonverbal["emotion"] = 5.0
            elif positive >= 0.5:
                nonverbal["emotion"] = 4.0
            elif positive >= 0.35:
                nonverbal["emotion"] = 3.0
            elif positive >= 0.2:
                nonverbal["emotion"] = 2.0
            else:
                nonverbal["emotion"] = 1.0

    # ── 4. Prosody 음성 감정 (긍정 지표-부정 지표 종합) ──
    prosody = report.get("prosody_analysis")
    if prosody:
        indicators = (
            prosody.get("session_avg_indicators")
            or prosody.get("indicator_averages")
            or {}
        )
        if indicators:
            positive_keys = ["confidence", "focus", "positivity", "calmness"]
            negative_keys = ["anxiety", "confusion", "negativity", "fatigue"]
            pos_avg = sum(indicators.get(k, 0) for k in positive_keys) / len(
                positive_keys
            )
            neg_avg = sum(indicators.get(k, 0) for k in negative_keys) / len(
                negative_keys
            )
            # 점수 = 긍정 비중 - 부정 비중, 0~1 범위로 정규화 후 5점 변환
            prosody_ratio = max(0, min(1, (pos_avg - neg_avg + 0.3) / 0.6))
            nonverbal["prosody"] = round(prosody_ratio * 4 + 1, 1)  # 1~5 범위

    return nonverbal


def _compute_evaluation_summary(evaluations: List[Dict], report: Dict = None) -> Dict:
    """
    평가 목록에서 평균 점수, 비언어 점수, 통합 점수, 합불 추천을 계산하는 공통 헬퍼.
    report가 전달되면 비언어 데이터(speech, gaze, emotion, prosody)를 반영한다.
    """
    if not evaluations:
        return {}

    # ── LLM 답변 평가 점수 (5축) ──
    avg_scores = {k: 0.0 for k in EVAL_SCORE_KEYS}
    for ev in evaluations:
        for key in avg_scores:
            avg_scores[key] += ev.get("scores", {}).get(key, 0)
    for key in avg_scores:
        avg_scores[key] = round(avg_scores[key] / len(evaluations), 1)

    verbal_avg = round(sum(avg_scores.values()) / len(EVAL_SCORE_KEYS), 1)

    # ── 비언어 평가 점수 ──
    nonverbal_scores: Dict[str, float] = {}
    nonverbal_avg = 0.0
    if report:
        nonverbal_scores = _compute_nonverbal_scores(report)
    if nonverbal_scores:
        nonverbal_avg = round(sum(nonverbal_scores.values()) / len(nonverbal_scores), 1)

    # ── 통합 최종 점수 (언어 60% + 비언어 40%) ──
    if nonverbal_scores:
        final_score = round(verbal_avg * 0.6 + nonverbal_avg * 0.4, 1)
    else:
        # 비언어 데이터 없으면 언어 평가만 사용
        final_score = verbal_avg

    # ── 합격 추천 결정 (통합 점수 기반) ──
    low_count = sum(1 for v in avg_scores.values() if v < 2.5)
    total_25 = sum(avg_scores.values())  # 25점 만점 합계

    if final_score >= 4.0 and total_25 >= 20 and low_count == 0:
        final_recommendation = "합격"
    else:
        final_recommendation = "불합격"

    # 추천 사유 생성
    parts = [f"통합 {final_score}/5.0 (언어 {verbal_avg}"]
    if nonverbal_scores:
        parts[0] += f" + 비언어 {nonverbal_avg}"
    parts[0] += ")"
    last_reason = evaluations[-1].get("recommendation_reason", "")
    if last_reason:
        parts.append(last_reason)
    recommendation_reason = " | ".join(parts)

    result = {
        "answer_count": len(evaluations),
        "average_scores": avg_scores,
        "verbal_average": verbal_avg,
        "nonverbal_scores": nonverbal_scores,
        "nonverbal_average": nonverbal_avg if nonverbal_scores else None,
        "final_score": final_score,
        "total_average": final_score,  # 하위 호환
        "recommendation": final_recommendation,
        "recommendation_reason": recommendation_reason,
        "all_evaluations": evaluations,
    }
    return result


# ========== Report API ==========


@app.get("/api/report/{session_id}")
async def get_report(session_id: str, current_user: Dict = Depends(get_current_user)):
    """면접 리포트 생성"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    generator = InterviewReportGenerator()

    # 감정 통계 조회 (있는 경우)
    emotion_stats = None
    if state.last_emotion:
        emotion_stats = state.last_emotion

    report = generator.generate_report(session_id, emotion_stats)

    # REQ-F-006: 비언어 평가 데이터 먼저 수집 (통합 점수 계산에 필요)
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_stats = speech_service.get_session_stats(session_id)
            if speech_stats:
                report["speech_analysis"] = speech_stats.to_dict()
        except Exception as e:
            print(f"[Report] 발화 분석 데이터 조회 오류: {e}")

    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_stats = gaze_service.get_session_stats(session_id)
            if gaze_stats:
                report["gaze_analysis"] = gaze_stats.to_dict()
        except Exception as e:
            print(f"[Report] 시선 추적 데이터 조회 오류: {e}")

    if PROSODY_AVAILABLE and prosody_service:
        try:
            prosody_stats = prosody_service.get_session_stats_dict(session_id)
            if prosody_stats and prosody_stats.get("total_samples", 0) > 0:
                report["prosody_analysis"] = prosody_stats
        except Exception as e:
            print(f"[Report] Prosody 분석 데이터 조회 오류: {e}")

    # LLM 평가 + 비언어 평가 통합 점수 계산
    evaluations = session.get("evaluations", [])
    if evaluations:
        report["llm_evaluation"] = _compute_evaluation_summary(evaluations, report)

    return report


# ========== PDF Report Download API ==========


@app.get("/api/report/{session_id}/pdf")
async def get_report_pdf(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """면접 리포트 PDF 다운로드"""
    if not PDF_REPORT_AVAILABLE or not generate_pdf_report:
        raise HTTPException(
            status_code=501, detail="PDF 리포트 서비스가 비활성화되어 있습니다."
        )

    # 기존 리포트 생성 로직 재사용
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    generator = InterviewReportGenerator()
    emotion_stats = None
    if state.last_emotion:
        emotion_stats = state.last_emotion

    report = generator.generate_report(session_id, emotion_stats)

    # 비언어 평가 데이터 먼저 수집
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_stats = speech_service.get_session_stats(session_id)
            if speech_stats:
                report["speech_analysis"] = speech_stats.to_dict()
        except Exception:
            pass

    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_stats = gaze_service.get_session_stats(session_id)
            if gaze_stats:
                report["gaze_analysis"] = gaze_stats.to_dict()
        except Exception:
            pass

    # LLM 평가 + 비언어 통합 점수 계산
    evaluations = session.get("evaluations", [])
    if evaluations:
        report["llm_evaluation"] = _compute_evaluation_summary(evaluations, report)

    try:
        pdf_bytes = generate_pdf_report(report)

        from fastapi.responses import Response

        filename = (
            f"interview_report_{session_id[:8]}_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 생성 오류: {str(e)}")


# ========== Evaluate API (LLM 기반 답변 평가) ==========


class EvaluateRequest(BaseModel):
    session_id: str
    question: str
    answer: str


class EvaluateResponse(BaseModel):
    session_id: str
    scores: Dict[str, int]
    total_score: int
    recommendation: str = "불합격"
    recommendation_reason: str = ""
    strengths: List[str]
    improvements: List[str]
    brief_feedback: str


@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate_answer(
    request: EvaluateRequest, current_user: Dict = Depends(get_current_user)
):
    """
    LLM을 사용하여 답변 평가

    - 질문과 답변을 받아 5가지 기준으로 평가
    - 세션에 평가 결과 저장
    """
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # LLM 평가 수행
    evaluation = await interviewer.evaluate_answer(
        request.session_id, request.question, request.answer
    )

    # 세션에 평가 저장
    evaluations = session.get("evaluations", [])
    evaluations.append(
        {"question": request.question, "answer": request.answer, **evaluation}
    )
    state.update_session(request.session_id, {"evaluations": evaluations})

    return EvaluateResponse(
        session_id=request.session_id,
        scores=evaluation.get("scores", {}),
        total_score=evaluation.get("total_score", 0),
        recommendation=evaluation.get("recommendation", "불합격"),
        recommendation_reason=evaluation.get("recommendation_reason", ""),
        strengths=evaluation.get("strengths", []),
        improvements=evaluation.get("improvements", []),
        brief_feedback=evaluation.get("brief_feedback", ""),
    )


@app.get("/api/evaluations/{session_id}")
async def get_evaluations(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 모든 평가 결과 조회 (인증 필요)"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    evaluations = session.get("evaluations", [])

    # 통계 계산
    if evaluations:
        summary = _compute_evaluation_summary(evaluations)
        return {
            "session_id": session_id,
            "total_answers": summary["answer_count"],
            "average_scores": summary["average_scores"],
            "total_average": summary["total_average"],
            "recommendation": summary["recommendation"],
            "recommendation_reason": summary["recommendation_reason"],
            "evaluations": evaluations,
        }

    return {
        "session_id": session_id,
        "total_answers": 0,
        "average_scores": {},
        "evaluations": [],
    }


# ========== WebRTC/Video API ==========


@app.post("/offer")
async def webrtc_offer(offer: Offer):
    """WebRTC offer 처리"""
    import traceback

    try:
        pc = RTCPeerConnection()
        state.pcs.add(pc)
        session_id = state.create_session()
        state.pc_sessions[pc] = session_id

        @pc.on("iceconnectionstatechange")
        async def on_ice_state_change():
            if pc.iceConnectionState in ("failed", "closed", "disconnected"):
                await pc.close()
                state.pcs.discard(pc)

        @pc.on("track")
        async def on_track(track):
            if track.kind == "video":
                pc.addTrack(track)
                # 녹화 서비스 시작 (GStreamer/FFmpeg 파이프라인)
                if RECORDING_AVAILABLE and recording_service:
                    try:
                        recording_service.start_recording(
                            session_id, width=640, height=480, fps=15
                        )
                    except Exception as e:
                        print(f"⚠️ [Recording] 녹화 시작 실패: {e}")
                # 감정 분석 + 녹화 통합 루프
                asyncio.create_task(_video_pipeline(track, session_id))
            else:
                # 오디오 트랙 STT 라우팅: Deepgram(우선) → Whisper(폴백) → 소비만
                # + 녹화 오디오 파이프
                asyncio.create_task(_audio_pipeline(track, session_id))

        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer.sdp, type=offer.type)
        )
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "session_id": session_id,
        }
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[/offer ERROR] {error_detail}")
        return JSONResponse(status_code=500, content={"error": str(e)})


async def _consume_audio(track, sink: MediaBlackhole):
    """오디오 트랙 소비 (Deepgram 비활성화 시 폴백)"""
    try:
        while True:
            frame = await track.recv()
            sink.write(frame)
    except Exception:
        pass


async def _video_pipeline(track, session_id: str):
    """
    비디오 트랙 통합 파이프라인:
    1. 모든 프레임을 GStreamer/FFmpeg 녹화 파이프에 전송
    2. 감정 분석 주기(1초)마다 DeepFace 처리
    """
    sample_period = 1.0
    batch_sample_period = 10.0
    last_ts = 0.0
    last_batch_ts = 0.0
    recording_active = (
        RECORDING_AVAILABLE
        and recording_service
        and recording_service.get_recording(session_id) is not None
    )

    try:
        while True:
            frame = await track.recv()
            now = time.monotonic()

            try:
                img = frame.to_ndarray(format="bgr24")
            except Exception:
                continue

            # ── 녹화: 모든 프레임을 파이프에 쓰기 ──
            if recording_active:
                try:
                    await recording_service.write_video_frame(session_id, img.tobytes())
                except Exception:
                    pass

            # ── 감정 분석: sample_period 마다 ──
            if not EMOTION_AVAILABLE or now - last_ts < sample_period:
                continue
            last_ts = now

            try:
                res = await run_deepface_async(img, actions=["emotion"])
                item = res[0] if isinstance(res, list) else res
                scores = item.get("emotion", {})

                # 시선 추적
                if GAZE_TRACKING_AVAILABLE and gaze_service:
                    try:
                        face_region = item.get("region")
                        if face_region:
                            frame_h, frame_w = img.shape[:2]
                            gaze_service.add_face_detection(
                                session_id, face_region, frame_w, frame_h
                            )
                    except Exception as e:
                        print(f"[GazeTracking] 데이터 전달 오류: {e}")

                keys_map = {
                    "happy": "happy",
                    "sad": "sad",
                    "angry": "angry",
                    "surprise": "surprise",
                    "fear": "fear",
                    "disgust": "disgust",
                    "neutral": "neutral",
                }
                raw = {k: float(scores.get(src, 0.0)) for k, src in keys_map.items()}
                total = sum(raw.values()) or 1.0
                probabilities = {k: (v / total) for k, v in raw.items()}

                data = {
                    "dominant_emotion": item.get("dominant_emotion"),
                    "probabilities": probabilities,
                    "raw_scores": raw,
                }

                async with state.emotion_lock:
                    state.last_emotion = data

                ts_ms = int(time.time() * 1000)
                for emo, prob in probabilities.items():
                    key = f"emotion:{session_id}:{emo}"
                    push_timeseries(key, ts_ms, prob, {"session_id": session_id})

                if now - last_batch_ts >= batch_sample_period:
                    last_batch_ts = now

                # WebSocket 브로드캐스트
                if session_id in state.websocket_connections:
                    msg = {"type": "emotion_update", **data, "timestamp": time.time()}
                    for ws in list(state.websocket_connections[session_id]):
                        try:
                            await ws.send_json(msg)
                        except Exception:
                            pass

            except Exception:
                pass

    except Exception:
        pass


# ========== Hume Prosody 오디오 버퍼 & 분석 함수 ==========
_prosody_audio_buffers: Dict[str, bytearray] = {}


async def _analyze_prosody_from_audio(session_id: str, raw_pcm: bytes, transcript: str):
    """
    축적된 PCM 오디오를 WAV로 변환 → Hume Prosody Streaming API로 분석.
    결과를 prosody_service 세션에 저장하고, WebSocket으로 클라이언트에 전송.
    """
    import io
    import struct

    try:
        # --- PCM (16kHz, 16bit, mono) → WAV 변환 ---
        wav_buf = io.BytesIO()
        num_samples = len(raw_pcm) // 2
        sample_rate = 16000
        # WAV header
        wav_buf.write(b"RIFF")
        data_size = num_samples * 2
        wav_buf.write(struct.pack("<I", 36 + data_size))
        wav_buf.write(b"WAVE")
        wav_buf.write(b"fmt ")
        wav_buf.write(
            struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        )
        wav_buf.write(b"data")
        wav_buf.write(struct.pack("<I", data_size))
        wav_buf.write(raw_pcm)
        wav_bytes = wav_buf.getvalue()

        # --- Prosody 분석 (Streaming REST API) ---
        result = await asyncio.get_event_loop().run_in_executor(
            LLM_EXECUTOR,
            lambda: prosody_service.analyze_audio_stream(
                session_id, wav_bytes, transcript
            ),
        )

        if result and result.get("interview_indicators"):
            # InterviewState에 최신 prosody 저장
            state.last_prosody = result

            # WebSocket으로 클라이언트에 전송
            await broadcast_stt_result(
                session_id,
                {
                    "type": "prosody_result",
                    "indicators": result["interview_indicators"],
                    "dominant_indicator": result.get("dominant_indicator", ""),
                    "adaptive_mode": result.get("adaptive_mode", "normal"),
                    "timestamp": time.time(),
                },
            )

            print(
                f"[Prosody] 세션 {session_id[:8]}... "
                f"주요감정: {result.get('dominant_indicator', '?')} "
                f"모드: {result.get('adaptive_mode', '?')}"
            )

    except Exception as e:
        print(f"[Prosody] 분석 오류 (세션 {session_id[:8]}): {e}")


async def _audio_pipeline(track, session_id: str):
    """
    오디오 트랙 통합 파이프라인:
    1. STT 처리 (Deepgram/Whisper)
    2. GStreamer/FFmpeg 녹화 파이프에 오디오 프레임 전송
    """
    import numpy as np

    recording_active = (
        RECORDING_AVAILABLE
        and recording_service
        and recording_service.get_recording(session_id) is not None
    )

    # ── STT 없이 녹화만 필요한 경우 ──
    if not DEEPGRAM_AVAILABLE and not (WHISPER_AVAILABLE and whisper_service):
        try:
            while True:
                frame = await track.recv()
                if recording_active:
                    try:
                        audio_data = frame.to_ndarray()
                        pcm = audio_data.astype(np.int16).tobytes()
                        await recording_service.write_audio_frame(session_id, pcm)
                    except Exception:
                        pass
        except Exception:
            pass
        return

    # ── Deepgram STT + 녹화 ──
    if DEEPGRAM_AVAILABLE:
        # _process_audio_with_stt 에 녹화 쓰기를 위임하지 않고
        # 별도로 호출 → 프레임은 공유 불가이므로 실제로는
        # _process_audio_with_stt_and_recording 을 사용
        await _process_audio_with_stt_and_recording(track, session_id, recording_active)
    elif WHISPER_AVAILABLE and whisper_service:
        print(f"🔄 [STT] 세션 {session_id[:8]}... Whisper 오프라인 폴백 사용")
        await process_audio_with_whisper(
            track,
            session_id,
            whisper_service,
            broadcast_stt_result,
            speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
        )


async def _process_audio_with_stt_and_recording(
    track, session_id: str, recording_active: bool
):
    """Deepgram STT + GStreamer/FFmpeg 녹화 통합 오디오 처리"""
    if not DEEPGRAM_AVAILABLE or not deepgram_client:
        return

    import numpy as np

    try:
        with deepgram_client.listen.v1.connect(
            model="nova-3",
            language="ko",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            punctuate=True,
            interim_results=True,
            vad_events=True,
            endpointing=300,
        ) as dg_connection:

            def on_message(message) -> None:
                try:
                    transcript = None
                    is_final = False
                    words_list = None
                    confidence = None

                    if hasattr(message, "results") and getattr(
                        message.results, "channels", None
                    ):
                        is_final = getattr(message.results, "is_final", False)
                        alts = message.results.channels[0].alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], "confidence", None)
                            raw_words = getattr(alts[0], "words", None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(
                                            w, "word", getattr(w, "punctuated_word", "")
                                        ),
                                        "start": getattr(w, "start", 0.0),
                                        "end": getattr(w, "end", 0.0),
                                        "confidence": getattr(w, "confidence", 0.0),
                                    }
                                    for w in raw_words
                                ]
                    elif hasattr(message, "channel") and getattr(
                        message.channel, "alternatives", None
                    ):
                        is_final = getattr(message, "is_final", True)
                        alts = message.channel.alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], "confidence", None)
                            raw_words = getattr(alts[0], "words", None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(
                                            w, "word", getattr(w, "punctuated_word", "")
                                        ),
                                        "start": getattr(w, "start", 0.0),
                                        "end": getattr(w, "end", 0.0),
                                        "confidence": getattr(w, "confidence", 0.0),
                                    }
                                    for w in raw_words
                                ]

                    if transcript:
                        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
                            try:
                                speech_service.add_stt_result(
                                    session_id,
                                    transcript,
                                    is_final,
                                    confidence=confidence,
                                    words=words_list,
                                )
                            except Exception as e:
                                print(f"[SpeechAnalysis] 데이터 전달 오류: {e}")

                        if (
                            is_final
                            and SPACING_CORRECTION_AVAILABLE
                            and _spacing_corrector
                        ):
                            corrected = _spacing_corrector.correct(transcript)
                            if corrected and corrected.strip():
                                transcript = corrected

                        asyncio.create_task(
                            broadcast_stt_result(
                                session_id,
                                {
                                    "type": "stt_result",
                                    "transcript": transcript,
                                    "is_final": is_final,
                                    "timestamp": time.time(),
                                },
                            )
                        )

                        # ── Hume Prosody 음성 감정 분석 (최종 발화 시) ──
                        if is_final and PROSODY_AVAILABLE and prosody_service:
                            buffered = bytes(
                                _prosody_audio_buffers.get(session_id, b"")
                            )
                            _prosody_audio_buffers[session_id] = bytearray()
                            if len(buffered) > 3200:  # 최소 0.1초 (16kHz, 16bit)
                                asyncio.create_task(
                                    _analyze_prosody_from_audio(
                                        session_id, buffered, transcript
                                    )
                                )

                except Exception as e:
                    print(f"[STT] 메시지 처리 오류: {e}")

            def on_error(error) -> None:
                print(f"[STT] Deepgram 오류: {error}")

            dg_connection.on(
                EventType.OPEN,
                lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결됨"),
            )
            dg_connection.on(EventType.MESSAGE, on_message)
            dg_connection.on(
                EventType.CLOSE,
                lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결 종료"),
            )
            dg_connection.on(EventType.ERROR, on_error)

            state.stt_connections[session_id] = dg_connection
            print(f"[STT] 세션 {session_id} 오디오 처리 시작")

            # Prosody용 오디오 버퍼 초기화
            if PROSODY_AVAILABLE and prosody_service:
                _prosody_audio_buffers[session_id] = bytearray()

            try:
                while True:
                    frame = await track.recv()
                    try:
                        audio_data = frame.to_ndarray()
                        if (
                            audio_data.dtype == np.float32
                            or audio_data.dtype == np.float64
                        ):
                            audio_bytes = (
                                (audio_data * 32767).astype(np.int16).tobytes()
                            )
                        else:
                            audio_bytes = audio_data.astype(np.int16).tobytes()

                        # → Deepgram STT 전송
                        from deepgram.extensions.types.sockets import (
                            ListenV1MediaMessage,
                        )

                        dg_connection.send_media(ListenV1MediaMessage(audio_bytes))

                        # → Prosody 오디오 버퍼 축적
                        if (
                            PROSODY_AVAILABLE
                            and prosody_service
                            and session_id in _prosody_audio_buffers
                        ):
                            _prosody_audio_buffers[session_id].extend(audio_bytes)

                        # → 녹화 파이프 전송
                        if recording_active:
                            try:
                                await recording_service.write_audio_frame(
                                    session_id, audio_bytes
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception as e:
                print(f"[STT] 오디오 처리 종료: {e}")
            finally:
                state.stt_connections.pop(session_id, None)
                _prosody_audio_buffers.pop(session_id, None)

    except Exception as e:
        print(f"[STT] Deepgram 연결 실패: {e}")
        if WHISPER_AVAILABLE and whisper_service:
            print(
                f"🔄 [STT] 세션 {session_id[:8]}... Deepgram 실패 → Whisper 폴백 전환"
            )
            await process_audio_with_whisper(
                track,
                session_id,
                whisper_service,
                broadcast_stt_result,
                speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
            )
        else:
            print(
                f"⚠️ [STT] 세션 {session_id[:8]}... Whisper 폴백도 불가 — STT 비활성화"
            )


async def _process_audio_with_stt(track, session_id: str):
    """오디오 트랙을 Deepgram STT로 처리하여 실시간 텍스트 변환"""
    if not DEEPGRAM_AVAILABLE or not deepgram_client:
        return

    try:
        import numpy as np

        # Deepgram WebSocket 연결 (SDK v5.3.2 스타일)
        with deepgram_client.listen.v1.connect(
            model="nova-3",
            language="ko",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            punctuate=True,
            interim_results=True,
            vad_events=True,
            endpointing=300,
        ) as dg_connection:
            # 이벤트 핸들러 정의
            def on_message(message) -> None:
                """STT 결과 처리 및 WebSocket으로 클라이언트에 전송"""
                try:
                    transcript = None
                    is_final = False
                    words_list = None
                    confidence = None

                    if hasattr(message, "results") and getattr(
                        message.results, "channels", None
                    ):
                        is_final = getattr(message.results, "is_final", False)
                        alts = message.results.channels[0].alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], "confidence", None)
                            # word-level 타이밍/confidence 추출
                            raw_words = getattr(alts[0], "words", None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(
                                            w, "word", getattr(w, "punctuated_word", "")
                                        ),
                                        "start": getattr(w, "start", 0.0),
                                        "end": getattr(w, "end", 0.0),
                                        "confidence": getattr(w, "confidence", 0.0),
                                    }
                                    for w in raw_words
                                ]
                    elif hasattr(message, "channel") and getattr(
                        message.channel, "alternatives", None
                    ):
                        is_final = getattr(message, "is_final", True)
                        alts = message.channel.alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], "confidence", None)
                            raw_words = getattr(alts[0], "words", None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(
                                            w, "word", getattr(w, "punctuated_word", "")
                                        ),
                                        "start": getattr(w, "start", 0.0),
                                        "end": getattr(w, "end", 0.0),
                                        "confidence": getattr(w, "confidence", 0.0),
                                    }
                                    for w in raw_words
                                ]

                    if transcript:
                        # 발화 분석 서비스에 STT 결과 전달
                        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
                            try:
                                speech_service.add_stt_result(
                                    session_id,
                                    transcript,
                                    is_final,
                                    confidence=confidence,
                                    words=words_list,
                                )
                            except Exception as e:
                                print(f"[SpeechAnalysis] 데이터 전달 오류: {e}")

                        # 최종 결과에 한국어 띄어쓰기 보정 적용
                        if (
                            is_final
                            and SPACING_CORRECTION_AVAILABLE
                            and _spacing_corrector
                        ):
                            corrected = _spacing_corrector.correct(transcript)
                            if corrected and corrected.strip():
                                transcript = corrected

                        # 비동기 브로드캐스트를 위해 이벤트 루프에 태스크 추가
                        asyncio.create_task(
                            broadcast_stt_result(
                                session_id,
                                {
                                    "type": "stt_result",
                                    "transcript": transcript,
                                    "is_final": is_final,
                                    "timestamp": time.time(),
                                },
                            )
                        )

                except Exception as e:
                    print(f"[STT] 메시지 처리 오류: {e}")

            def on_error(error) -> None:
                print(f"[STT] Deepgram 오류: {error}")

            dg_connection.on(
                EventType.OPEN,
                lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결됨"),
            )
            dg_connection.on(EventType.MESSAGE, on_message)
            dg_connection.on(
                EventType.CLOSE,
                lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결 종료"),
            )
            dg_connection.on(EventType.ERROR, on_error)

            state.stt_connections[session_id] = dg_connection
            print(f"[STT] 세션 {session_id} 오디오 처리 시작")

            try:
                while True:
                    frame = await track.recv()
                    # aiortc 오디오 프레임을 raw PCM으로 변환
                    try:
                        audio_data = frame.to_ndarray()
                        # 16bit PCM으로 변환
                        if (
                            audio_data.dtype == np.float32
                            or audio_data.dtype == np.float64
                        ):
                            audio_bytes = (
                                (audio_data * 32767).astype(np.int16).tobytes()
                            )
                        else:
                            audio_bytes = audio_data.astype(np.int16).tobytes()

                        # Deepgram에 오디오 전송
                        from deepgram.extensions.types.sockets import (
                            ListenV1MediaMessage,
                        )

                        dg_connection.send_media(ListenV1MediaMessage(audio_bytes))
                    except Exception:
                        pass
            except Exception as e:
                print(f"[STT] 오디오 처리 종료: {e}")
            finally:
                state.stt_connections.pop(session_id, None)

    except Exception as e:
        print(f"[STT] Deepgram 연결 실패: {e}")
        # Deepgram 런타임 실패 시 Whisper 폴백 시도
        if WHISPER_AVAILABLE and whisper_service:
            print(
                f"🔄 [STT] 세션 {session_id[:8]}... Deepgram 실패 → Whisper 폴백 전환"
            )
            await process_audio_with_whisper(
                track,
                session_id,
                whisper_service,
                broadcast_stt_result,
                speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
            )
        else:
            print(
                f"⚠️ [STT] 세션 {session_id[:8]}... Whisper 폴백도 불가 — STT 비활성화"
            )


async def broadcast_stt_result(session_id: str, data: dict):
    """세션의 모든 WebSocket 클라이언트에 STT 결과 브로드캐스트"""
    if session_id not in state.websocket_connections:
        return

    dead_connections = []
    for ws in state.websocket_connections[session_id]:
        try:
            await ws.send_json(data)
        except Exception:
            dead_connections.append(ws)

    # 끊어진 연결 제거
    for ws in dead_connections:
        state.websocket_connections[session_id].remove(ws)


# ========== 녹화 / 트랜스코딩 API ==========


@app.post("/api/recording/{session_id}/start")
async def start_recording(session_id: str, current_user=Depends(get_current_user)):
    """면접 녹화 시작"""
    if not RECORDING_AVAILABLE or not recording_service:
        raise HTTPException(
            status_code=503, detail="녹화 서비스 비활성화 (GStreamer/FFmpeg 미설치)"
        )
    try:
        meta = recording_service.start_recording(session_id)
        return {
            "status": "recording",
            "recording_id": meta.recording_id,
            "session_id": session_id,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recording/{session_id}/stop")
async def stop_recording(session_id: str, current_user=Depends(get_current_user)):
    """
    면접 녹화 중지 + 비동기 트랜스코딩 태스크 시작.
    GStreamer/FFmpeg 파이프를 닫고 Celery를 통해 먹싱+트랜스코딩합니다.
    """
    if not RECORDING_AVAILABLE or not recording_service:
        raise HTTPException(status_code=503, detail="녹화 서비스 비활성화")

    try:
        meta = await recording_service.stop_recording(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Celery 트랜스코딩 태스크 비동기 실행
    task_result = None
    if CELERY_AVAILABLE and meta.raw_video_path:
        try:
            from celery_tasks import transcode_recording_task

            task = transcode_recording_task.delay(
                session_id=session_id,
                video_path=meta.raw_video_path,
                audio_path=meta.raw_audio_path or "",
            )
            task_result = {"task_id": task.id, "status": "queued"}
            print(f"📤 [Recording] 트랜스코딩 태스크 전송: {task.id}")
        except Exception as e:
            print(f"⚠️ [Recording] Celery 태스크 전송 실패: {e}")
            task_result = {"error": str(e)}

    return {
        **meta.to_dict(),
        "transcode_task": task_result,
    }


@app.get("/api/recording/{session_id}")
async def get_recording_info(session_id: str, current_user=Depends(get_current_user)):
    """녹화 상태 및 메타데이터 조회"""
    if not RECORDING_AVAILABLE or not recording_service:
        raise HTTPException(status_code=503, detail="녹화 서비스 비활성화")

    meta = recording_service.get_recording(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="녹화 정보 없음")
    return meta.to_dict()


@app.get("/api/recording/{session_id}/download")
async def download_recording(session_id: str, current_user=Depends(get_current_user)):
    """트랜스코딩 완료된 녹화 파일 다운로드"""
    if not RECORDING_AVAILABLE or not recording_service:
        raise HTTPException(status_code=503, detail="녹화 서비스 비활성화")

    meta = recording_service.get_recording(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="녹화 정보 없음")

    # 트랜스코딩 완료 파일 확인
    file_path = meta.transcoded_path or meta.raw_video_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, detail="녹화 파일 없음 (트랜스코딩 미완료)"
        )

    # AES-256 암호화된 파일인 경우 복호화하여 전송
    # is_encrypted_file()로 매직 바이트(AESF)를 확인하여 암호화 여부를 판단
    if AES_ENCRYPTION_AVAILABLE and is_encrypted_file(file_path):
        try:
            decrypted_path = file_path + ".decrypted.tmp"
            decrypt_file(file_path, decrypted_path)

            # 임시 복호화 파일을 전송 후 자동 삭제하도록 BackgroundTask 사용
            from starlette.background import BackgroundTask

            def cleanup_temp_file(path: str):
                """전송 완료 후 임시 복호화 파일 삭제"""
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass

            filename = f"interview_{session_id[:8]}.mp4"
            return FileResponse(
                path=decrypted_path,
                filename=filename,
                media_type="video/mp4",
                background=BackgroundTask(cleanup_temp_file, decrypted_path),
            )
        except Exception as e:
            # 복호화 실패 시 원본 파일 그대로 전송 (Graceful Degradation)
            print(f"⚠️ [Recording] AES 복호화 실패, 원본 전송: {e}")

    filename = f"interview_{session_id[:8]}.mp4"
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="video/mp4",
    )


@app.delete("/api/recording/{session_id}")
async def delete_recording(session_id: str, current_user=Depends(get_current_user)):
    """녹화 파일 삭제"""
    if not RECORDING_AVAILABLE or not recording_service:
        raise HTTPException(status_code=503, detail="녹화 서비스 비활성화")

    deleted = recording_service.delete_recording(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="녹화 정보 없음")
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/recording/status")
async def get_recording_service_status(current_user: Dict = Depends(get_current_user)):
    """녹화 서비스 상태 확인 (인증 필요)"""
    return {
        "available": RECORDING_AVAILABLE,
        "media_tool": MEDIA_TOOL if RECORDING_AVAILABLE else None,
        "gstreamer": _GST if RECORDING_AVAILABLE else False,
        "ffmpeg": _FFM if RECORDING_AVAILABLE else False,
        "active_recordings": len(
            [
                m
                for m in (
                    recording_service.get_all_recordings()
                    if RECORDING_AVAILABLE and recording_service
                    else []
                )
                if m.get("status") == "recording"
            ]
        ),
    }


# ========== WebSocket API (실시간 STT/이벤트) ==========


@app.websocket("/ws/interview/{session_id}")
async def websocket_interview(
    websocket: WebSocket, session_id: str, token: Optional[str] = None
):
    """실시간 면접 WebSocket - STT 결과 및 이벤트 수신 (JWT 인증 필수)"""

    # --- JWT 토큰 검증 ---
    # 1순위: 쿼리 파라미터 ?token=xxx  2순위: Sec-WebSocket-Protocol 헤더
    ws_token = token
    if not ws_token:
        # 헤더에서 토큰 추출 시도 (subprotocol)
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        for proto in protocols.split(","):
            proto = proto.strip()
            if proto.startswith("access_token."):
                ws_token = proto[len("access_token.") :]
                break

    if not ws_token:
        await websocket.close(code=4001, reason="인증 토큰이 필요합니다.")
        print(f"[WS] 세션 {session_id} 인증 실패: 토큰 없음")
        return

    payload = decode_access_token(ws_token)
    if payload is None:
        await websocket.close(
            code=4001, reason="인증 토큰이 만료되었거나 유효하지 않습니다."
        )
        print(f"[WS] 세션 {session_id} 인증 실패: 유효하지 않은 토큰")
        return

    ws_user_email = payload.get("sub", "unknown")
    print(f"[WS] 세션 {session_id} 인증 성공: {ws_user_email}")
    # --- JWT 검증 완료 ---

    await websocket.accept()

    # 세션에 WebSocket 연결 추가
    if session_id not in state.websocket_connections:
        state.websocket_connections[session_id] = []
    state.websocket_connections[session_id].append(websocket)

    print(f"[WS] 세션 {session_id} WebSocket 연결됨 (사용자: {ws_user_email})")

    # 📤 EventBus에 WebSocket 등록 (이벤트 기반 WS 브로드캐스트 지원)
    if EVENT_BUS_AVAILABLE and event_bus:
        event_bus.register_ws(session_id, websocket)

    try:
        # 연결 성공 메시지
        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session_id,
                "user": ws_user_email,
                "stt_available": DEEPGRAM_AVAILABLE,
            }
        )

        while True:
            # 클라이언트로부터 메시지 수신 (ping/pong 등)
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "vad_signal":
                # VAD 신호 처리 (기존 intervention 시스템과 연동)
                pass

    except WebSocketDisconnect:
        print(f"[WS] 세션 {session_id} WebSocket 연결 해제")
    except Exception as e:
        print(f"[WS] 세션 {session_id} 오류: {e}")
    finally:
        # 연결 제거
        if session_id in state.websocket_connections:
            if websocket in state.websocket_connections[session_id]:
                state.websocket_connections[session_id].remove(websocket)
        # EventBus에서 WebSocket 해제
        if EVENT_BUS_AVAILABLE and event_bus:
            event_bus.unregister_ws(session_id, websocket)


# ========== Emotion API ==========


@app.get("/emotion", response_class=HTMLResponse)
async def emotion_page(request: Request):
    """감정 분석 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "emotion")


@app.get("/api/emotion/current")
async def get_emotion_current(current_user: Dict = Depends(get_current_user)):
    """현재 감정 상태 조회 (인증 필요)"""
    async with state.emotion_lock:
        if state.last_emotion is None:
            return {"status": "no_data"}
        return state.last_emotion


@app.get("/emotion/sessions")
async def get_emotion_sessions(current_user: Dict = Depends(get_current_user)):
    """모든 세션 목록 조회 (인증 필요)"""
    r = get_redis()
    sessions = set()
    if r:
        try:
            keys = r.keys("emotion:*")
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                parts = key_str.split(":")
                if len(parts) >= 2:
                    sessions.add(parts[1])
        except Exception:
            pass
    return {"sessions": list(sessions)}


@app.get("/emotion/timeseries")
async def get_emotion_timeseries(
    session_id: str,
    emotion: str,
    limit: int = 100,
    current_user: Dict = Depends(get_current_user),
):
    """감정 시계열 데이터 조회 (인증 필요)"""
    r = get_redis()
    data = []
    if r:
        key = f"emotion:{session_id}:{emotion}"
        try:
            if _ts_available:
                res = r.execute_command("TS.RANGE", key, 0, int(time.time() * 1000))
                if isinstance(res, list):
                    data = res[-limit:]
            else:
                res = r.zrevrange(key, 0, limit - 1, withscores=True)
                data = [
                    [int(m.decode() if isinstance(m, bytes) else m), s] for m, s in res
                ]
        except Exception:
            pass
    return {"session_id": session_id, "emotion": emotion, "points": data}


@app.get("/emotion/stats")
async def get_emotion_stats(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """감정 통계 조회 (인증 필요)"""
    r = get_redis()
    emotions = ["happy", "sad", "angry", "surprise", "fear", "disgust", "neutral"]
    stats = {}

    for emotion in emotions:
        stats[emotion] = {"count": 0, "avg": 0, "min": 0, "max": 0}
        if not r:
            continue

        key = f"emotion:{session_id}:{emotion}"
        try:
            res = r.zrange(key, 0, -1, withscores=True)
            if res:
                values = [float(score) for _, score in res]
                stats[emotion] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
        except Exception:
            pass

    return {"session_id": session_id, "stats": stats}


# ========== Service Status ==========


@app.get("/api/status")
async def get_status(current_user: Optional[Dict] = Depends(get_current_user_optional)):
    """서비스 상태 확인 (선택적 인증)"""
    return {
        "status": "running",
        "services": {
            "llm": LLM_AVAILABLE,
            "tts": TTS_AVAILABLE,
            "stt": DEEPGRAM_AVAILABLE,
            "stt_whisper_fallback": WHISPER_AVAILABLE,
            "stt_spacing_correction": SPACING_CORRECTION_AVAILABLE,
            "rag": RAG_AVAILABLE,
            "emotion": EMOTION_AVAILABLE,
            "redis": REDIS_AVAILABLE,
            "celery": CELERY_AVAILABLE,
            "event_bus": EVENT_BUS_AVAILABLE,
        },
        "active_sessions": len(state.sessions),
        "active_connections": len(state.pcs),
        "celery_status": check_celery_status()
        if CELERY_AVAILABLE
        else {"status": "disabled"},
        "event_bus_stats": event_bus.get_stats()
        if EVENT_BUS_AVAILABLE and event_bus
        else {"status": "disabled"},
    }


@app.get("/api/stt/status")
async def get_stt_status(
    current_user: Optional[Dict] = Depends(get_current_user_optional),
):
    """STT 서비스 상태 상세 조회 (선택적 인증)"""
    status = {
        "primary": {
            "engine": "Deepgram (Nova-3)",
            "available": DEEPGRAM_AVAILABLE,
            "type": "cloud",
            "language": "ko",
        },
        "fallback": {
            "engine": "Whisper (offline)",
            "available": WHISPER_AVAILABLE,
            "type": "local",
        },
        "active_engine": "deepgram"
        if DEEPGRAM_AVAILABLE
        else ("whisper" if WHISPER_AVAILABLE else "none"),
        "spacing_correction": SPACING_CORRECTION_AVAILABLE,
    }
    if WHISPER_AVAILABLE and whisper_service:
        status["fallback"].update(whisper_service.get_status())
    return status


# ========== 이벤트 버스 모니터링 API ==========


@app.get("/api/events/stats")
async def get_event_stats(current_user: Dict = Depends(get_current_user)):
    """이벤트 버스 통계 조회 (인증 필요)"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled"}
    return event_bus.get_stats()


@app.get("/api/events/history")
async def get_event_history(
    limit: int = 50,
    event_type: Optional[str] = None,
    current_user: Dict = Depends(get_current_user),
):
    """이벤트 히스토리 조회 (인증 필요)"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled", "events": []}
    return {
        "events": event_bus.get_history(limit=limit, event_type=event_type),
        "total": len(event_bus.get_history(limit=9999)),
    }


@app.get("/api/events/registered")
async def get_registered_events(current_user: Dict = Depends(get_current_user)):
    """등록된 이벤트 타입 및 핸들러 목록 (인증 필요)"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled"}
    return {
        "event_types": event_bus.get_registered_events(),
        "handler_count": {k: len(v) for k, v in event_bus._handlers.items() if v},
    }


# ========== LangGraph 워크플로우 시각화/감사 API ==========


@app.get("/api/workflow/status")
async def get_workflow_status(current_user: Dict = Depends(get_current_user)):
    """LangGraph 워크플로우 서비스 상태 (인증 필요)"""
    return {
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "workflow_initialized": interview_workflow is not None,
        "features": {
            "conditional_branching": True,
            "loop_control": True,
            "checkpointing": True,
            "parallel_processing": True,
            "visualization": True,
            "audit_trace": True,
        }
        if interview_workflow
        else {},
    }


@app.get("/api/workflow/graph")
async def get_workflow_graph(current_user: Dict = Depends(get_current_user)):
    """LangGraph 워크플로우 그래프 다이어그램 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return {
        "mermaid": interview_workflow.get_graph_mermaid(),
        "format": "mermaid",
    }


@app.get("/api/workflow/graph-definition")
async def get_workflow_graph_definition(current_user: Dict = Depends(get_current_user)):
    """LangGraph 워크플로우 정적 그래프 구조 정보 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return interview_workflow.get_graph_definition()


@app.get("/api/workflow/{session_id}/trace")
async def get_workflow_trace(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 LangGraph 실행 추적 이력 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    traces = interview_workflow.get_execution_trace(session_id)
    return {
        "session_id": session_id,
        "total_turns": len(traces),
        "traces": traces,
    }


@app.get("/api/workflow/{session_id}/state")
async def get_workflow_state(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 현재 워크플로우 상태 요약 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return interview_workflow.get_current_state_summary(session_id)


@app.get("/api/workflow/{session_id}/checkpoint")
async def get_workflow_checkpoint(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """세션의 마지막 체크포인트 정보 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    checkpoint = interview_workflow.get_checkpoint(session_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="체크포인트를 찾을 수 없습니다.")
    return checkpoint


@app.get("/api/workflow/{session_id}/checkpoints")
async def list_workflow_checkpoints(
    session_id: str, limit: int = 10, current_user: Dict = Depends(get_current_user)
):
    """세션의 체크포인트 이력 목록 (인증 필요)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    checkpoints = interview_workflow.list_checkpoints(session_id, limit=limit)
    return {
        "session_id": session_id,
        "total": len(checkpoints),
        "checkpoints": checkpoints,
    }


# ========== Celery 비동기 작업 API ==========


class AsyncTaskRequest(BaseModel):
    """비동기 태스크 요청"""

    session_id: str
    question: Optional[str] = None
    answer: Optional[str] = None
    use_rag: bool = True


class AsyncTaskResponse(BaseModel):
    """비동기 태스크 응답"""

    task_id: str
    status: str
    message: str


@app.post("/api/async/evaluate", response_model=AsyncTaskResponse)
async def async_evaluate_answer(
    request: AsyncTaskRequest, current_user: Dict = Depends(get_current_user)
):
    """
    비동기 답변 평가 (Celery)

    - 답변 평가 작업을 Celery Worker에 전달
    - task_id를 반환하여 나중에 결과 조회 가능
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # RAG 컨텍스트 가져오기 (옵션)
    resume_context = ""
    if request.use_rag and RAG_AVAILABLE:
        try:
            result = retrieve_resume_context_task.delay(request.answer)
            context_result = result.get(timeout=30)
            resume_context = context_result.get("context", "")
        except Exception:
            pass

    # 비동기 태스크 실행
    task = evaluate_answer_task.delay(
        request.session_id, request.question, request.answer, resume_context
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="평가 작업이 대기열에 추가되었습니다.",
    )


@app.post("/api/async/batch-evaluate", response_model=AsyncTaskResponse)
async def async_batch_evaluate(
    request: Request, current_user: Dict = Depends(get_current_user)
):
    """
    비동기 배치 평가 (Celery)

    여러 답변을 한 번에 평가합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    data = await request.json()
    session_id = data.get("session_id")
    qa_pairs = data.get("qa_pairs", [])

    if not qa_pairs:
        raise HTTPException(status_code=400, detail="평가할 QA 쌍이 없습니다.")

    task = batch_evaluate_task.delay(session_id, qa_pairs)

    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message=f"{len(qa_pairs)}개 답변의 배치 평가가 시작되었습니다.",
    )


@app.post("/api/async/emotion-analysis", response_model=AsyncTaskResponse)
async def async_emotion_analysis(
    request: Request, current_user: Dict = Depends(get_current_user)
):
    """
    비동기 감정 분석 (Celery)

    이미지 데이터(Base64)를 받아 감정 분석 수행
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    data = await request.json()
    session_id = data.get("session_id")
    image_data = data.get("image_data")  # Base64 인코딩된 이미지

    if not image_data:
        raise HTTPException(status_code=400, detail="이미지 데이터가 없습니다.")

    task = analyze_emotion_task.delay(session_id, image_data)

    return AsyncTaskResponse(
        task_id=task.id, status="PENDING", message="감정 분석 작업이 시작되었습니다."
    )


@app.post("/api/async/batch-emotion", response_model=AsyncTaskResponse)
async def async_batch_emotion_analysis(request: Request):
    """
    비동기 배치 감정 분석 (Celery)

    여러 이미지를 한 번에 분석합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    data = await request.json()
    session_id = data.get("session_id")
    image_data_list = data.get("images", [])

    if not image_data_list:
        raise HTTPException(status_code=400, detail="분석할 이미지가 없습니다.")

    task = batch_emotion_analysis_task.delay(session_id, image_data_list)

    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message=f"{len(image_data_list)}개 이미지의 감정 분석이 시작되었습니다.",
    )


@app.post("/api/async/generate-report", response_model=AsyncTaskResponse)
async def async_generate_report(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """
    비동기 리포트 생성 (Celery)

    면접 종료 후 종합 리포트를 생성합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    chat_history = session.get("chat_history", [])
    evaluations = session.get("evaluations", [])
    emotion_stats = session.get("emotion_stats", None)

    task = generate_report_task.delay(
        session_id, chat_history, evaluations, emotion_stats
    )

    return AsyncTaskResponse(
        task_id=task.id, status="PENDING", message="리포트 생성 작업이 시작되었습니다."
    )


@app.post("/api/async/complete-interview", response_model=AsyncTaskResponse)
async def async_complete_interview(
    request: Request, current_user: Dict = Depends(get_current_user)
):
    """
    비동기 면접 완료 워크플로우 (Celery)

    평가 + 감정 분석 + 리포트 생성을 한 번에 처리합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    data = await request.json()
    session_id = data.get("session_id")

    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    chat_history = session.get("chat_history", [])
    emotion_images = data.get("emotion_images", [])

    task = complete_interview_workflow_task.delay(
        session_id, chat_history, emotion_images
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="면접 완료 워크플로우가 시작되었습니다.",
    )


@app.get("/api/async/task/{task_id}")
async def get_task_status(task_id: str):
    """
    태스크 상태 조회

    - PENDING: 대기 중
    - STARTED: 실행 중
    - SUCCESS: 완료
    - FAILURE: 실패
    - RETRY: 재시도 중
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    result = AsyncResult(task_id, app=celery_app)

    response = {"task_id": task_id, "status": result.status, "ready": result.ready()}

    if result.ready():
        if result.successful():
            response["result"] = result.get()
        else:
            response["error"] = str(result.result)

    return response


@app.get("/api/async/task/{task_id}/result")
async def get_task_result(task_id: str, timeout: int = 60):
    """
    태스크 결과 조회 (대기)

    태스크가 완료될 때까지 대기 후 결과 반환
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    result = AsyncResult(task_id, app=celery_app)

    try:
        task_result = result.get(timeout=timeout)
        return {"task_id": task_id, "status": "SUCCESS", "result": task_result}
    except Exception as e:
        return {"task_id": task_id, "status": "FAILURE", "error": str(e)}


@app.delete("/api/async/task/{task_id}")
async def cancel_task(task_id: str):
    """
    태스크 취소

    실행 대기 중인 태스크를 취소합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Celery 서비스가 비활성화되어 있습니다."
        )

    celery_app.control.revoke(task_id, terminate=True)

    return {
        "task_id": task_id,
        "status": "REVOKED",
        "message": "태스크가 취소되었습니다.",
    }


@app.get("/api/celery/status")
async def get_celery_status():
    """
    Celery 상태 조회

    Worker 연결 상태, 큐 정보 등을 반환합니다.
    """
    if not CELERY_AVAILABLE:
        return {
            "status": "disabled",
            "message": "Celery 서비스가 비활성화되어 있습니다.",
        }

    try:
        # Worker 상태 확인
        inspect = celery_app.control.inspect()

        active_workers = inspect.active() or {}
        reserved_tasks = inspect.reserved() or {}
        stats = inspect.stats() or {}

        return {
            "status": "connected" if active_workers else "no_workers",
            "workers": list(active_workers.keys()),
            "active_tasks": sum(len(tasks) for tasks in active_workers.values()),
            "reserved_tasks": sum(len(tasks) for tasks in reserved_tasks.values()),
            "worker_stats": stats,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/celery/queues")
async def get_celery_queues():
    """
    Celery 큐 정보 조회
    """
    if not CELERY_AVAILABLE:
        return {"status": "disabled"}

    try:
        import redis as redis_lib

        r = redis_lib.from_url(REDIS_URL)

        queues = [
            "default",
            "llm_evaluation",
            "emotion_analysis",
            "report_generation",
            "tts_generation",
            "rag_processing",
        ]

        queue_info = {}
        for queue in queues:
            queue_info[queue] = r.llen(queue)

        return {"queues": queue_info, "total_pending": sum(queue_info.values())}
    except Exception as e:
        return {"error": str(e)}


# ========== 면접 완료 워크플로우 API ==========


@app.get("/api/interview/{session_id}/workflow-status")
async def get_interview_workflow_status(session_id: str):
    """
    면접 완료 워크플로우 상태 조회

    - 백그라운드에서 실행 중인 리포트 생성 상태 확인
    - 완료 시 최종 리포트 반환
    """
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    workflow_task_id = session.get("completion_workflow_task_id")

    if not workflow_task_id:
        return {
            "session_id": session_id,
            "workflow_status": "not_started",
            "message": "면접 완료 워크플로우가 시작되지 않았습니다.",
        }

    if not CELERY_AVAILABLE:
        return {
            "session_id": session_id,
            "workflow_status": "celery_unavailable",
            "message": "Celery 서비스를 사용할 수 없습니다.",
        }

    try:
        from celery.result import AsyncResult

        result = AsyncResult(workflow_task_id, app=celery_app)

        response = {
            "session_id": session_id,
            "workflow_task_id": workflow_task_id,
            "workflow_status": result.status,
            "started_at": session.get("completion_started_at"),
        }

        if result.ready():
            if result.successful():
                workflow_result = result.get(timeout=5)
                response["report"] = workflow_result.get("report")
                response["evaluations"] = workflow_result.get("evaluations")
                response["emotion_stats"] = workflow_result.get("emotion_stats")
            else:
                response["error"] = str(result.result)

        return response

    except Exception as e:
        return {"session_id": session_id, "workflow_status": "error", "error": str(e)}


@app.post("/api/interview/{session_id}/collect-evaluations")
async def collect_pending_evaluations(session_id: str):
    """
    대기 중인 Celery 평가 결과 수집

    - 백그라운드에서 완료된 평가들을 세션에 저장
    - 수집된 평가 개수 반환
    """
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    before_count = len(session.get("evaluations", []))
    evaluations = await interviewer.collect_celery_evaluations(session_id)
    after_count = len(evaluations)

    return {
        "session_id": session_id,
        "collected_count": after_count - before_count,
        "total_evaluations": after_count,
        "pending_tasks": len(
            state.get_session(session_id).get("pending_eval_tasks", [])
        ),
    }


@app.post("/api/interview/{session_id}/start-workflow")
async def start_interview_workflow(session_id: str):
    """
    면접 완료 워크플로우 수동 시작

    - 면접이 정상 종료되지 않은 경우 수동으로 워크플로우 시작
    """
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if session.get("completion_workflow_task_id"):
        return {
            "session_id": session_id,
            "status": "already_started",
            "task_id": session.get("completion_workflow_task_id"),
        }

    task_id = await interviewer.start_interview_completion_workflow(session_id)

    if task_id:
        return {"session_id": session_id, "status": "started", "task_id": task_id}
    else:
        return {
            "session_id": session_id,
            "status": "failed",
            "message": "워크플로우 시작에 실패했습니다.",
        }


# ========== 서버 종료 처리 ==========


@app.on_event("startup")
async def on_startup():
    """서버 시작 시 초기화 — 이벤트 버스 + 핸들러 등록"""
    if EVENT_BUS_AVAILABLE and event_bus:
        redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        await event_bus.initialize(redis_url)
        register_all_handlers(event_bus)
        print("✅ [Startup] 이벤트 버스 초기화 및 핸들러 등록 완료")

        # 시스템 시작 이벤트 발행
        await event_bus.publish(
            AppEventType.SERVICE_STATUS_CHANGED,
            data={"service": "api_server", "status": "started"},
            source="system",
            broadcast_ws=False,
        )

    # ── 코딩 문제 풀(Pool) 사전 생성 ──
    # Celery worker가 실행 중이면 난이도별로 문제를 미리 생성하여
    # 사용자가 코딩 테스트 페이지를 열었을 때 즉시 제공할 수 있도록 합니다.
    if CODING_TEST_AVAILABLE:
        try:
            from code_execution_service import (
                POOL_TARGET_SIZE,
                problem_pool,
                trigger_pool_refill,
            )

            for diff in ("easy", "medium", "hard"):
                current = problem_pool.count(diff)
                if current < POOL_TARGET_SIZE:
                    trigger_pool_refill(diff)
                    print(
                        f"  📦 [Pool] {diff} 풀 보충 요청 (현재 {current}/{POOL_TARGET_SIZE})"
                    )
                else:
                    print(f"  ✅ [Pool] {diff} 풀 충분 ({current}/{POOL_TARGET_SIZE})")
            print("✅ [Startup] 코딩 문제 풀 사전 생성 태스크 발행 완료")
        except Exception as e:
            print(f"⚠️ [Startup] 코딩 문제 풀 초기화 실패 (Celery 미실행?): {e}")


@app.on_event("shutdown")
async def on_shutdown():
    """서버 종료 시 정리"""
    # 이벤트 버스 종료
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.SERVICE_STATUS_CHANGED,
            data={"service": "api_server", "status": "shutting_down"},
            source="system",
            broadcast_ws=False,
            propagate_redis=False,
        )
        await event_bus.shutdown()
        print("✅ [Shutdown] 이벤트 버스 종료 완료")

    # WebRTC 연결 정리
    coros = [pc.close() for pc in state.pcs]
    await asyncio.gather(*coros, return_exceptions=True)
    state.pcs.clear()

    # 녹화 프로세스 정리
    if RECORDING_AVAILABLE and recording_service:
        await recording_service.cleanup()
        print("✅ [Shutdown] 녹화 프로세스 정리 완료")

    # ThreadPoolExecutor 정리
    print("🔄 [Shutdown] ThreadPoolExecutor 종료 중...")
    LLM_EXECUTOR.shutdown(wait=False)
    RAG_EXECUTOR.shutdown(wait=False)
    VISION_EXECUTOR.shutdown(wait=False)
    print("✅ [Shutdown] 모든 Executor 종료 완료")


# ========== Next.js 캐치올 프록시 (반드시 모든 라우트 뒤에 위치) ==========


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def nextjs_catchall(request: Request, path: str):
    """
    등록되지 않은 모든 경로를 Next.js로 프록시합니다.
    FastAPI API 라우트보다 후순위로 매칭됩니다.
    """
    # /api/ 경로는 Next.js로 보내지 않음 (FastAPI에서 404 반환)
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    return await _proxy_to_nextjs(request, path)


# ========== 메인 실행 ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("🎯 AI 모의면접 통합 시스템 (비동기 + Celery 백그라운드 처리)")
    print("=" * 70)
    print(f"  • LLM 모델: {DEFAULT_LLM_MODEL}")
    print("  • 비동기 처리 (ThreadPoolExecutor):")
    print("    - LLM Executor: 4 workers (질문 생성, 평가)")
    print("    - RAG Executor: 2 workers (이력서 검색)")
    print("    - Vision Executor: 2 workers (감정 분석)")
    print("  • Celery 백그라운드 작업:")
    print("    - llm_evaluation: 답변 평가 (배치)")
    print("    - emotion_analysis: 감정 분석 (배치)")
    print("    - report_generation: 리포트 생성")
    print("    - tts_generation: TTS 프리페칭")
    print("    - rag_processing: 이력서 인덱싱")
    print("  • 서비스 상태:")
    print(f"    - LLM: {'✅ 활성화' if LLM_AVAILABLE else '❌ 비활성화'}")
    print(f"    - TTS: {'✅ 활성화' if TTS_AVAILABLE else '❌ 비활성화'}")
    print(f"    - RAG: {'✅ 활성화' if RAG_AVAILABLE else '❌ 비활성화'}")
    print(f"    - 감정분석: {'✅ 활성화' if EMOTION_AVAILABLE else '❌ 비활성화'}")
    print(f"    - Redis: {'✅ 활성화' if REDIS_AVAILABLE else '❌ 비활성화'}")
    print(f"    - Celery: {'✅ 활성화' if CELERY_AVAILABLE else '❌ 비활성화'}")
    _rec_tool = MEDIA_TOOL.upper() if RECORDING_AVAILABLE else "미설치"
    print(
        f"    - 녹화: {'✅ ' + _rec_tool if RECORDING_AVAILABLE else '❌ 비활성화 (GStreamer/FFmpeg 필요)'}"
    )
    print("=" * 70)
    print("  📋 Celery Worker 시작 명령어 (별도 터미널에서 실행):")
    print("     # 모든 큐 처리")
    print("     celery -A celery_app worker --pool=solo --loglevel=info")
    print("")
    print("     # 특정 큐만 처리 (권장: 여러 터미널에서 분산)")
    print("     celery -A celery_app worker -Q llm_evaluation --pool=solo")
    print("     celery -A celery_app worker -Q report_generation --pool=solo")
    print("=" * 70)

    # TLS 설정 확인
    ssl_context = get_ssl_context()
    if ssl_context:
        protocol = "https"
        ssl_kwargs = {
            "ssl_certfile": os.getenv("TLS_CERTFILE", ""),
            "ssl_keyfile": os.getenv("TLS_KEYFILE", ""),
        }
        print("  🔒 TLS 활성화 (HTTPS)")
    else:
        protocol = "http"
        ssl_kwargs = {}
        print(
            "  ⚠️ TLS 비활성화 (HTTP) — 프로덕션에서는 TLS_CERTFILE/TLS_KEYFILE 설정 권장"
        )

    # Next.js 개발 서버 자동 시작
    import atexit

    frontend_dir = os.path.join(current_dir, "frontend")
    if os.path.exists(os.path.join(frontend_dir, "package.json")):
        print("  🚀 Next.js 프론트엔드 개발 서버 시작 중...")
        try:
            _nextjs_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=frontend_dir,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print(
                f"  ✅ Next.js 서버 시작됨 (PID: {_nextjs_process.pid}, {NEXTJS_URL})"
            )
        except Exception as e:
            print(f"  ⚠️ Next.js 서버 자동 시작 실패: {e}")
            print("     수동 시작: cd CSH/frontend && npm run dev")
            _nextjs_process = None
    else:
        print("  ⚠️ Next.js 프론트엔드 미설치 (CSH/frontend/package.json 없음)")
        _nextjs_process = None

    def cleanup_nextjs():
        """Next.js 프로세스 정리"""
        global _nextjs_process
        if _nextjs_process and _nextjs_process.poll() is None:
            print("\n🔄 Next.js 서버 종료 중...")
            _nextjs_process.terminate()
            try:
                _nextjs_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _nextjs_process.kill()
            print("✅ Next.js 서버 종료 완료")

    atexit.register(cleanup_nextjs)

    print(f"  🌐 {protocol}://localhost:8000 에서 접속하세요")
    print(f"  🎨 Next.js: {NEXTJS_URL} (프록시 경유: :8000)")
    print("=" * 70 + "\n")

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, **ssl_kwargs)
    finally:
        cleanup_nextjs()
