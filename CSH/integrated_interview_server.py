"""
AI 모의면접 통합 시스템
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

import os
import sys
import asyncio
import time
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, List, Set, Any
from collections import Counter
import re
from concurrent.futures import ThreadPoolExecutor
import functools

# FastAPI 및 웹 프레임워크
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import subprocess
import httpx

# WebRTC
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole

# 환경 설정
from dotenv import load_dotenv

# PostgreSQL 데이터베이스
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
sys.path.append(current_dir)

load_dotenv()

# JSON Resilience 유틸리티
from json_utils import resilient_json_parse, parse_evaluation_json

# 보안 유틸리티 (bcrypt 비밀번호 해싱, JWT 토큰 인증, TLS)
from security import (
    hash_password, verify_password, needs_rehash,
    create_access_token, decode_access_token, get_current_user, get_current_user_optional,
    get_ssl_context
)

# ========== 설정 ==========
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
DEFAULT_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
DEFAULT_LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "16384"))
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
LLM_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm_worker")
RAG_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag_worker")
VISION_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vision_worker")


async def run_in_executor(executor: ThreadPoolExecutor, func, *args, **kwargs):
    """동기 함수를 ThreadPoolExecutor에서 비동기로 실행"""
    loop = asyncio.get_event_loop()
    if kwargs:
        func_with_kwargs = functools.partial(func, **kwargs)
        return await loop.run_in_executor(executor, func_with_kwargs, *args)
    return await loop.run_in_executor(executor, func, *args)


async def run_llm_async(llm, messages):
    """LLM invoke를 비동기로 실행 (이벤트 루프 블로킹 방지)"""
    return await run_in_executor(LLM_EXECUTOR, llm.invoke, messages)


async def run_rag_async(retriever, query):
    """RAG retriever invoke를 비동기로 실행 (nomic-embed-text 최적화: search_query 접두사 적용)"""
    prefixed_query = f"search_query: {query}"
    docs = await run_in_executor(RAG_EXECUTOR, retriever.invoke, prefixed_query)
    # search_document: 접두사 제거
    for doc in docs:
        if doc.page_content.startswith("search_document: "):
            doc.page_content = doc.page_content[len("search_document: "):]
    return docs


async def run_deepface_async(img, actions=None):
    """DeepFace analyze를 비동기로 실행 (CPU 바운드 작업)"""
    if actions is None:
        actions = ["emotion"]
    return await run_in_executor(
        VISION_EXECUTOR, 
        DeepFace.analyze, 
        img, 
        actions=actions, 
        enforce_detection=False
    )


# ========== PostgreSQL 데이터베이스 설정 ==========
# POSTGRES_CONNECTION_STRING 환경변수가 있으면 우선 사용
DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING")

# 없으면 개별 환경변수로 조합
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "interview_db")
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"🔗 DB 연결 시도: {DATABASE_URL.replace(DATABASE_URL.split(':')[2].split('@')[0], '****')}")

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
        role = Column(String(20), nullable=False, default="candidate")  # candidate, recruiter
        password_hash = Column(String(255), nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow)
        name = Column(String(50), nullable=True)
        birth_date = Column(String(10), nullable=True)  # DATE 타입이지만 문자열로 처리
        gender = Column(String(10), nullable=True)
        address = Column(String(500), nullable=True)
        phone = Column(String(20), nullable=True)  # 전화번호 (예: 010-1234-5678)
    
    # 연결 테스트
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    DB_AVAILABLE = True
    print("✅ PostgreSQL 데이터베이스 연결됨")
except Exception as e:
    DB_AVAILABLE = False
    print(f"⚠️ PostgreSQL 데이터베이스 연결 실패: {e}")
    print("   → 메모리 저장소를 사용합니다.")

# ========== FastAPI 앱 초기화 ==========
app = FastAPI(
    title="AI 모의면접 통합 시스템",
    description="TTS, STT, LLM, 화상 면접, 감정 분석을 통합한 AI 면접 시스템",
    version="1.0.0"
)

# CORS 설정 (운영 환경에서는 ALLOWED_ORIGINS 환경변수로 허용 도메인 지정)
# 예: ALLOWED_ORIGINS=https://example.com,https://app.example.com
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").strip()
if ALLOWED_ORIGINS:
    cors_origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]
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
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in skip_headers}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # GET/POST 모두 지원
            method = request.method
            body = await request.body() if method in ("POST", "PUT", "PATCH") else None
            resp = await client.request(method, target_url, headers=fwd_headers, content=body)
            # Next.js 응답 헤더 원본 보존 (RSC, Vary, Set-Cookie 등)
            proxy_headers = {}
            for key in ("content-type", "vary", "x-nextjs-cache", "set-cookie", "cache-control",
                         "x-action-redirect", "x-action-revalidate", "location",
                         "rsc", "next-router-state-tree", "x-nextjs-matched-path"):
                val = resp.headers.get(key)
                if val:
                    proxy_headers[key] = val
            if not proxy_headers.get("content-type"):
                proxy_headers["content-type"] = "text/html; charset=utf-8"
            from fastapi.responses import Response
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=proxy_headers
            )
    except httpx.ConnectError:
        # Next.js 서버가 아직 시작되지 않았을 때 안내 페이지
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head><meta charset="utf-8"><title>Next.js 서버 대기 중</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center;
                   align-items: center; min-height: 100vh; background: #0a0a0a; color: #ededed; margin: 0; }}
            .card {{ background: #1a1a2e; padding: 3rem; border-radius: 16px; text-align: center;
                     box-shadow: 0 8px 32px rgba(0,0,0,0.3); max-width: 500px; }}
            h2 {{ color: #60a5fa; margin-bottom: 1rem; }}
            p {{ color: #9ca3af; line-height: 1.6; }}
            code {{ background: #374151; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
            .spinner {{ width: 40px; height: 40px; border: 4px solid #374151; border-top-color: #60a5fa;
                       border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1.5rem; }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
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
        """, status_code=503)
    except Exception as e:
        return HTMLResponse(content=f"<h1>프록시 오류</h1><p>{e}</p>", status_code=502)

# ========== 외부 서비스 임포트 ==========
# TTS 서비스
try:
    from hume_tts_service import HumeTTSService, HumeInterviewerVoice, create_tts_router
    tts_router = create_tts_router()
    app.include_router(tts_router)
    TTS_AVAILABLE = True
    print("✅ Hume TTS 서비스 활성화됨")
except ImportError as e:
    TTS_AVAILABLE = False
    print(f"⚠️ Hume TTS 서비스 비활성화: {e}")

# RAG 서비스
try:
    from resume_rag import ResumeRAG, RESUME_TABLE, QA_TABLE
    RAG_AVAILABLE = True
    print("✅ Resume RAG 서비스 활성화됨")
except ImportError as e:
    RAG_AVAILABLE = False
    print(f"⚠️ Resume RAG 서비스 비활성화: {e}")

# LLM 서비스
try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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
    from deepface import DeepFace
    import numpy as np
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
    from celery_app import celery_app, check_celery_status
    from celery_tasks import (
        evaluate_answer_task,
        batch_evaluate_task,
        analyze_emotion_task,
        batch_emotion_analysis_task,
        generate_report_task,
        generate_tts_task,
        process_resume_task,
        retrieve_resume_context_task,
        complete_interview_workflow_task,
        prefetch_tts_task,
        generate_question_task,
        save_session_to_redis_task
    )
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
    print("✅ Celery 비동기 작업 서비스 활성화됨")
except ImportError as e:
    CELERY_AVAILABLE = False
    print(f"⚠️ Celery 서비스 비활성화: {e}")

# D-ID AI 아바타 서비스
try:
    from did_avatar_service import create_did_router, is_did_available
    did_router = create_did_router()
    app.include_router(did_router)
    DID_AVAILABLE = is_did_available()
    if DID_AVAILABLE:
        print("✅ D-ID AI 아바타 서비스 활성화됨")
    else:
        print("⚠️ D-ID API 키가 설정되지 않음 (정적 이미지 사용)")
except ImportError as e:
    DID_AVAILABLE = False
    print(f"⚠️ D-ID 서비스 비활성화: {e}")

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
    from events import EventType as AppEventType, EventFactory
    from event_handlers import register_all_handlers

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
        HumeProsodyService, get_prosody_service, is_prosody_available,
        extract_interview_indicators, determine_emotion_adaptive_mode,
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
        WhisperSTTService, is_whisper_available, process_audio_with_whisper
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
        MediaRecordingService, recording_service,
        RecordingStatus, RecordingMetadata,
        GSTREAMER_AVAILABLE as _GST, FFMPEG_AVAILABLE as _FFM, MEDIA_TOOL,
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
        InterviewWorkflow, WorkflowState, InterviewPhase,
        init_workflow, get_workflow_instance
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
                        "created_at": user.created_at.isoformat() if user.created_at else None
                    }
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
                    role=user_data.get("role", "candidate")  # 기본값: candidate
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)  # id 가져오기
                print(f"✅ DB에 사용자 저장됨: {user_data['email']} (ID: {new_user.id})")
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
            "follow_up_mode": False  # 꼬리질문 모드 여부
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
            "알겠습니다. 간단히 정리해서 마무리해 주세요."
        ],
        "hard_time_limit": [
            "네, 충분히 이해했습니다. 다음 질문으로 넘어가겠습니다.",
            "좋습니다. 시간 관계상 다음 질문을 드리겠습니다.",
            "감사합니다. 이제 다음 주제로 넘어가 볼까요?"
        ],
        "off_topic": [
            "좋은 말씀이시네요. 다만 질문과 조금 다른 방향인 것 같은데, 원래 질문으로 돌아가 볼까요?",
            "흥미로운 내용이지만, 질문에 좀 더 집중해서 답변해 주시겠어요?",
            "네, 이해합니다. 원래 질문의 핵심에 대해 답변 부탁드립니다."
        ],
        "encourage_more": [
            "조금 더 구체적으로 설명해 주시겠어요?",
            "예시를 들어 설명해 주시면 좋겠습니다.",
            "그 부분에 대해 좀 더 자세히 말씀해 주세요."
        ],
        "silence_detected": [
            "생각 정리가 필요하시면 잠시 시간을 드릴게요.",
            "천천히 생각하셔도 됩니다.",
            "준비가 되시면 말씀해 주세요."
        ]
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
            "turn_state": "ai_speaking"  # ai_speaking, user_speaking, silence
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
    
    def update_vad_signal(self, session_id: str, is_speech: bool, audio_level: float = 0.0):
        """VAD 신호 업데이트 (실시간)"""
        if session_id not in self.session_states:
            return None
        
        state = self.session_states[session_id]
        current_time = datetime.now()
        
        # VAD 버퍼에 신호 추가
        state["vad_buffer"].append({
            "timestamp": current_time,
            "is_speech": is_speech,
            "audio_level": audio_level
        })
        
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
                silence_ms = (current_time - state["last_speech_time"]).total_seconds() * 1000
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
    
    def check_intervention_needed(self, session_id: str, answer_text: str = None) -> Optional[Dict]:
        """개입이 필요한지 확인"""
        if session_id not in self.session_states:
            return None
        
        state = self.session_states[session_id]
        
        if answer_text:
            state["current_answer_text"] = answer_text
        
        answer_length = len(state["current_answer_text"])
        elapsed_seconds = 0
        
        if state["answer_start_time"]:
            elapsed_seconds = (datetime.now() - state["answer_start_time"]).total_seconds()
        
        intervention = None
        
        # 1. 강제 시간 제한 초과
        if elapsed_seconds >= self.MAX_ANSWER_TIME_SECONDS:
            intervention = {
                "type": "hard_time_limit",
                "reason": f"시간 초과 ({elapsed_seconds:.0f}초)",
                "message": self._get_random_message("hard_time_limit"),
                "action": "force_next_question",
                "priority": "high"
            }
        
        # 2. 소프트 시간 경고
        elif elapsed_seconds >= self.SOFT_WARNING_TIME and not state["soft_warning_given"]:
            intervention = {
                "type": "soft_time_warning",
                "reason": f"시간 경고 ({elapsed_seconds:.0f}초)",
                "message": self._get_random_message("soft_time_warning"),
                "action": "warn",
                "priority": "medium"
            }
            state["soft_warning_given"] = True
        
        # 3. 답변 길이 초과
        elif answer_length >= self.MAX_ANSWER_LENGTH:
            intervention = {
                "type": "hard_time_limit",
                "reason": f"답변 길이 초과 ({answer_length}자)",
                "message": self._get_random_message("hard_time_limit"),
                "action": "force_next_question",
                "priority": "high"
            }
        
        # 4. 소프트 길이 경고
        elif answer_length >= self.SOFT_WARNING_LENGTH and not state["soft_warning_given"]:
            intervention = {
                "type": "soft_time_warning",
                "reason": f"답변 길이 경고 ({answer_length}자)",
                "message": self._get_random_message("soft_time_warning"),
                "action": "warn",
                "priority": "medium"
            }
            state["soft_warning_given"] = True
        
        # 5. 주제 이탈 감지
        if intervention is None and answer_length > 100:
            relevance = self._check_topic_relevance(
                state["current_answer_text"],
                state["current_question_keywords"]
            )
            if relevance < self.TOPIC_RELEVANCE_THRESHOLD:
                intervention = {
                    "type": "off_topic",
                    "reason": f"주제 관련성 낮음 ({relevance:.2f})",
                    "message": self._get_random_message("off_topic"),
                    "action": "redirect",
                    "priority": "medium"
                }
        
        # 6. 장시간 침묵 감지
        if intervention is None and state["silence_duration_ms"] > 5000:  # 5초 이상 침묵
            intervention = {
                "type": "silence_detected",
                "reason": f"침묵 감지 ({state['silence_duration_ms']/1000:.1f}초)",
                "message": self._get_random_message("silence_detected"),
                "action": "encourage",
                "priority": "low"
            }
        
        if intervention:
            state["intervention_count"] += 1
            self.intervention_history[session_id].append({
                **intervention,
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": elapsed_seconds,
                "answer_length": answer_length
            })
            print(f"⚠️ [Intervention] 세션 {session_id[:8]}... {intervention['type']}: {intervention['reason']}")
        
        return intervention
    
    def _check_topic_relevance(self, answer: str, question_keywords: List[str]) -> float:
        """주제 관련성 점수 계산 (0.0 ~ 1.0)"""
        if not question_keywords:
            return 1.0  # 키워드가 없으면 관련성 체크 스킵
        
        answer_lower = answer.lower()
        matches = sum(1 for kw in question_keywords if kw.lower() in answer_lower)
        
        # 기본 관련성 점수
        keyword_score = matches / len(question_keywords) if question_keywords else 0
        
        # 일반적인 면접 관련 키워드 체크 (보너스)
        general_keywords = ["경험", "프로젝트", "개발", "팀", "기술", "결과", "성과", "학습"]
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
        stopwords = ["무엇", "어떻게", "왜", "있", "하", "되", "을", "를", "이", "가", "은", "는",
                     "에", "서", "로", "으로", "의", "와", "과", "도", "만", "까지", "부터",
                     "말씀", "해주", "주세요", "싶", "있나요", "인가요", "대해", "관해"]
        
        # 한글 단어 추출
        import re
        words = re.findall(r'[가-힣]{2,}', question)
        
        # 불용어 제거
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]
        
        # 기술 키워드 우선
        tech_keywords = ["python", "java", "react", "api", "서버", "데이터", "알고리즘",
                         "프로젝트", "개발", "설계", "배포", "테스트", "협업"]
        
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
            speech_ratio = sum(1 for v in recent_vad if v["is_speech"]) / len(recent_vad)
            # 발화가 줄어들고 있으면 (문장 끝) 개입 가능
            if speech_ratio < 0.3 and state["silence_duration_ms"] > 1000:
                can_interrupt = True
                interrupt_reason = "speech_ending"
        
        return {
            "can_interrupt": can_interrupt,
            "interrupt_reason": interrupt_reason,
            "turn_state": state["turn_state"],
            "silence_duration_ms": state["silence_duration_ms"],
            "is_speaking": state["is_speaking"]
        }
    
    def end_user_turn(self, session_id: str) -> Dict:
        """사용자 발화 종료"""
        if session_id not in self.session_states:
            return {}
        
        state = self.session_states[session_id]
        
        # 발화 통계 계산
        elapsed_seconds = 0
        if state["answer_start_time"]:
            elapsed_seconds = (datetime.now() - state["answer_start_time"]).total_seconds()
        
        stats = {
            "total_time_seconds": elapsed_seconds,
            "answer_length": len(state["current_answer_text"]),
            "intervention_count": state["intervention_count"],
            "soft_warning_given": state["soft_warning_given"]
        }
        
        # 상태 리셋
        state["turn_state"] = "ai_speaking"
        state["is_speaking"] = False
        
        print(f"🎙️ [VAD] 세션 {session_id[:8]}... 사용자 발화 종료 ({elapsed_seconds:.1f}초, {stats['answer_length']}자)")
        
        return stats
    
    def get_session_stats(self, session_id: str) -> Dict:
        """세션 개입 통계 반환"""
        return {
            "intervention_history": self.intervention_history.get(session_id, []),
            "total_interventions": len(self.intervention_history.get(session_id, [])),
            "state": self.session_states.get(session_id, {})
        }


# 개입 관리자 인스턴스
intervention_manager = InterviewInterventionManager()


# ========== LLM 면접관 서비스 ==========
class AIInterviewer:
    """AI 면접관 - LangChain LLM 기반 동적 질문 생성 + 답변 분석/평가"""
    
    # 면접관 시스템 프롬프트 (동적 질문 생성용)
    INTERVIEWER_PROMPT = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 이력서 내용과 답변을 바탕으로 기술 스택과 경험에 대해 심도 있는 질문을 던지세요.
제공된 '참고용 이력서 내용'을 적극 활용하여 구체적인 질문을 하세요.

[중요 규칙]
1. 답변이 부실하면 구체적인 예시를 요구하거나 꼬리 질문을 하세요.
2. 꼬리 질문은 주제당 최대 2번까지만 허용합니다. 
3. 동일한 기술적 주제에 대해 2번의 답변을 들었다면, "알겠습니다. 다음은..."이라며 주제를 전환하세요.
4. 질문은 한 번에 하나만 하세요.
5. 면접은 총 5개의 질문으로 진행됩니다.
6. 현재 질문 번호를 인지하고, 5번째 질문에서는 마무리 질문을 하세요.

질문을 할 때 너무 공격적이지 않게, 정중하지만 날카로운 태도를 유지하세요.
면접은 자기소개로 시작합니다."""

    # LLM 분석용 프롬프트 (답변 평가용)
    EVALUATION_PROMPT = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 답변을 분석하고 평가해주세요. 답변을 분석하고 평가할 때는 반드시 아래 평가 기준을 엄격히 준수하세요.

[평가 기준]
1. 문제 해결력 및 논리성 (1-5점): 지원자가 문제를 어떻게 접근하고 해결하는지, 그리고 답변의 논리적 흐름이 일관성 있는지를 평가합니다. 
2. 의사소통능력 (1-5점): 지원자가 자신의 생각을 명확하게 전달하는지, 그리고 면접관의 질문에 적절히 반응하는지를 평가합니다. 
3. 직무 역량 및 기술 이해도 (1-5점): 기술적 개념이나 원리에 대한 이해가 정확한가? 설명이나 예시가 충분하고 적절한가?
4. STAR 기법 (1-5점): 상황-과제-행동-결과 구조로 답변했는가?

[출력 형식 - 반드시 JSON으로 응답]
{{
    "scores": {{
        "problem_solving_and_logic": 숫자,
        "communication": 숫자,
        "technical": 숫자,
        "star": 숫자
    }},
    "total_score": 숫자,
    "strengths": ["강점1", "강점2"],
    "improvements": ["개선점1", "개선점2"],
    "brief_feedback": "한 줄 피드백"
}}"""

    # 최대 질문 개수
    MAX_QUESTIONS = 5

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
                # 평가용 LLM (낮은 temperature)
                self.llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL, 
                    temperature=0.3,
                    num_ctx=DEFAULT_LLM_NUM_CTX
                )
                # 질문 생성용 LLM (높은 temperature)
                self.question_llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL, 
                    temperature=DEFAULT_LLM_TEMPERATURE,
                    num_ctx=DEFAULT_LLM_NUM_CTX
                )
                print(f"✅ LLM 초기화 완료 (질문 생성 + 평가): {DEFAULT_LLM_MODEL}")
            except Exception as e:
                print(f"❌ LLM 초기화 실패: {e}")
        
        # RAG 초기화
        if RAG_AVAILABLE:
            try:
                connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
                if connection_string:
                    self.rag = ResumeRAG(connection_string=connection_string, table_name=RESUME_TABLE)
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
                "summary": ""    # 요약 (나중에 사용)
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
            "technical": ["기술", "스택", "언어", "프레임워크", "도구", "python", "java", "react"],
            "experience": ["경험", "경력", "회사", "팀", "업무"],
            "problem_solving": ["문제", "해결", "버그", "오류", "이슈", "장애"],
            "teamwork": ["팀", "협업", "동료", "커뮤니케이션", "갈등"],
            "motivation": ["지원", "이유", "동기", "관심", "목표"],
            "growth": ["성장", "발전", "학습", "공부", "목표", "계획"]
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
        
        # 답변 품질 분석 (간단한 휴리스틱)
        answer_length = len(answer)
        has_specifics = any(word in answer for word in ["예를 들어", "구체적으로", "실제로", "결과적으로", "%", "개월", "명"])
        
        # 꼬리질문 필요 여부 결정
        needs_follow_up = False
        follow_up_reason = ""
        
        # 1. 답변이 너무 짧은 경우
        if answer_length < 50:
            needs_follow_up = True
            follow_up_reason = "답변이 짧음 - 구체적인 예시 요청"
        # 2. 구체적인 내용이 없는 경우 (길이는 되지만 추상적)
        elif answer_length < 150 and not has_specifics:
            needs_follow_up = True
            follow_up_reason = "구체성 부족 - 상세 설명 요청"
        
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
            state.update_session(session_id, {
                "topic_question_count": topic_count + 1,
                "follow_up_mode": True
            })
        else:
            # 새 질문: 주제 전환
            if current_topic:
                topic_history.append({
                    "topic": current_topic,
                    "count": topic_count
                })
            
            state.update_session(session_id, {
                "current_topic": detected_topic,
                "topic_question_count": 1,
                "topic_history": topic_history,
                "follow_up_mode": False
            })
    
    def get_initial_greeting(self) -> str:
        """초기 인사말 반환"""
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
                "마지막으로 저희 회사에 궁금한 점이 있으신가요?"
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
            needs_follow_up, follow_up_reason = self.should_follow_up(session_id, user_answer)
            current_topic = session.get("current_topic", "general")
            topic_count = session.get("topic_question_count", 0)
            
            # 꼬리질문 상태 로깅
            print(f"📊 [Session {session_id[:8]}] 주제: {current_topic}, 주제내 질문수: {topic_count}, 꼬리질문 필요: {needs_follow_up} ({follow_up_reason})")
            
            # ========== 3. RAG 컨텍스트 가져오기 (세션별 retriever 우선) - 비동기 ==========
            resume_context = ""
            session_retriever = session.get("retriever") or self.retriever
            if session_retriever and user_answer:
                try:
                    # ThreadPoolExecutor로 블로킹 RAG 검색을 비동기로 실행
                    docs = await run_rag_async(session_retriever, user_answer)
                    if docs:
                        resume_context = "\n".join([d.page_content for d in docs[:3]])
                        print(f"📚 [RAG] {len(docs)}개 문서에서 컨텍스트 추출 (비동기)")
                except Exception as e:
                    print(f"⚠️ RAG 검색 오류: {e}")
            
            # ========== 3-1. 면접 Q&A 참조 데이터 검색 (모범 답변 참고용) ==========
            qa_reference_context = ""
            if RAG_AVAILABLE and user_answer and getattr(self, 'qa_rag', None):
                try:
                    qa_docs = await run_in_executor(RAG_EXECUTOR, self.qa_rag.similarity_search, user_answer, 2)
                    if qa_docs:
                        qa_reference_context = "\n".join([d.page_content for d in qa_docs[:2]])
                        print(f"📖 [Q&A RAG] {len(qa_docs)}개 참조 문서에서 모범 답변 추출")
                except Exception as e:
                    print(f"⚠️ Q&A 참조 데이터 검색 오류 (무시): {e}")
            
            # ========== 4. 대화 기록을 LangChain 메시지로 변환 ==========
            chat_history = session.get("chat_history", [])
            messages = [SystemMessage(content=self.INTERVIEWER_PROMPT)]
            
            # Memory에서 대화 기록 가져오기 (있으면)
            memory_messages = self.get_memory_messages(session_id)
            if memory_messages:
                messages.extend(memory_messages)
            else:
                # Memory가 없으면 수동 chat_history 사용
                for msg in chat_history:
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
            
            question_prompt = f"""[현재 상황]
- 진행된 질문 수: {question_count}/{self.MAX_QUESTIONS}
- 남은 질문 수: {self.MAX_QUESTIONS - question_count}
- 현재 주제: {current_topic}
- 주제 내 질문 횟수: {topic_count}/2
{follow_up_instruction}

지원자의 답변을 바탕으로 다음 질문을 생성해주세요.
{f'마지막 질문이니 마무리 질문을 해주세요.' if question_count == self.MAX_QUESTIONS - 1 else ''}
질문만 작성하세요. 부가 설명은 필요 없습니다."""
            
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
                "마지막으로 하고 싶은 말씀이 있으신가요?"
            ]
            return fallback[min(question_count, len(fallback) - 1)]
    
    async def evaluate_answer(
        self, 
        session_id: str, 
        question: str,
        answer: str
    ) -> Dict:
        """LLM을 사용하여 답변 평가"""
        if not self.llm:
            # LLM 없으면 기본 평가 반환
            return {
                "scores": {
                    "specificity": 3,
                    "logic": 3,
                    "technical": 3,
                    "star": 3,
                    "communication": 3
                },
                "total_score": 15,
                "strengths": ["답변을 완료했습니다."],
                "improvements": ["더 구체적인 예시를 들어보세요."],
                "brief_feedback": "괜찮은 답변입니다."
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
                            resume_context = "\n".join([d.page_content for d in docs[:2]])
                    except Exception:
                        pass
            
            # 평가 요청
            messages = [
                SystemMessage(content=self.EVALUATION_PROMPT),
                HumanMessage(content=f"""
[질문]
{question}

[지원자 답변]
{answer}

{f'[참고: 이력서 내용]{chr(10)}{resume_context}' if resume_context else ''}

위 답변을 평가해주세요. 반드시 JSON 형식으로 응답해주세요.
""")
            ]
            
            # ThreadPoolExecutor로 블로킹 LLM 호출을 비동기로 실행
            response = await run_llm_async(self.llm, messages)
            response_text = response.content
            
            # JSON Resilience 파싱
            evaluation = parse_evaluation_json(response_text, context="AIInterviewer.evaluate_answer")
            return evaluation
                
        except Exception as e:
            print(f"평가 오류: {e}")
            return {
                "scores": {
                    "specificity": 3,
                    "logic": 3,
                    "technical": 3,
                    "star": 3,
                    "communication": 3
                },
                "total_score": 15,
                "strengths": ["답변을 완료했습니다."],
                "improvements": ["더 구체적인 예시를 들어보세요."],
                "brief_feedback": "답변을 분석 중입니다."
            }
    
    async def generate_response(
        self, 
        session_id: str, 
        user_input: str,
        use_rag: bool = True
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
            state.update_session(session_id, {
                "chat_history": chat_history,
                "question_count": 1  # 첫 번째 질문
            })
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
                    ""  # RAG 컨텍스트는 Worker에서 가져옴
                )
                # 태스크 ID 저장 (나중에 결과 조회용)
                pending_tasks = session.get("pending_eval_tasks", [])
                pending_tasks.append({
                    "task_id": task.id,
                    "question": previous_question,
                    "answer": user_input,
                    "submitted_at": time.time()
                })
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
                        evaluations.append({
                            "question": task_info["question"],
                            "answer": task_info["answer"],
                            **eval_result
                        })
                        print(f"✅ [Celery] 평가 완료 수집: {task_info['task_id'][:8]}...")
                    else:
                        print(f"❌ [Celery] 평가 실패: {task_info['task_id'][:8]}...")
                else:
                    # 5분 이상 지난 태스크는 제거
                    if time.time() - task_info.get("submitted_at", 0) < 300:
                        still_pending.append(task_info)
            except Exception as e:
                print(f"⚠️ [Celery] 결과 수집 오류: {e}")
        
        # 세션 업데이트
        state.update_session(session_id, {
            "evaluations": evaluations,
            "pending_eval_tasks": still_pending
        })
        
        return evaluations
    
    async def start_interview_completion_workflow(self, session_id: str) -> Optional[str]:
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
                session_id,
                chat_history,
                session.get("emotion_images", [])
            )
            
            # 워크플로우 태스크 ID 저장
            state.update_session(session_id, {
                "completion_workflow_task_id": task.id,
                "completion_started_at": time.time()
            })
            
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
        'situation': ['상황', '배경', '당시', '그때', '환경', '상태', '문제', '이슈', '과제'],
        'task': ['목표', '과제', '임무', '역할', '담당', '책임', '해야 할', '목적', '미션'],
        'action': ['행동', '수행', '실행', '처리', '해결', '개발', '구현', '적용', '진행', '시도', '노력'],
        'result': ['결과', '성과', '달성', '완료', '개선', '향상', '증가', '감소', '효과', '성공']
    }
    
    TECH_KEYWORDS = [
        'python', 'java', 'javascript', 'react', 'vue', 'django', 'flask', 'spring',
        'aws', 'azure', 'docker', 'kubernetes', 'sql', 'mongodb', 'postgresql',
        'git', 'ci/cd', 'api', 'rest', 'machine learning', 'deep learning',
        'tensorflow', 'pytorch', 'pandas', 'LLM', 'RAG', 'LangChain', 'FastAPI'
    ]
    
    def __init__(self, llm=None):
        self.llm = llm or interviewer.llm
    
    def analyze_star_structure(self, answers: List[str]) -> Dict:
        """STAR 기법 분석"""
        star_analysis = {key: {'count': 0, 'examples': []} for key in self.STAR_KEYWORDS}
        
        for answer in answers:
            answer_lower = answer.lower()
            for element, keywords in self.STAR_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in answer_lower:
                        star_analysis[element]['count'] += 1
                        break
        
        return star_analysis
    
    def extract_keywords(self, answers: List[str]) -> Dict:
        """키워드 추출"""
        all_text = ' '.join(answers).lower()
        
        found_tech = []
        for kw in self.TECH_KEYWORDS:
            if kw.lower() in all_text:
                count = all_text.count(kw.lower())
                found_tech.append((kw, count))
        
        found_tech.sort(key=lambda x: x[1], reverse=True)
        
        korean_words = re.findall(r'[가-힣]{2,}', all_text)
        word_freq = Counter(korean_words)
        
        stopwords = ['그래서', '그리고', '하지만', '그런데', '있습니다', '했습니다', '합니다']
        for sw in stopwords:
            word_freq.pop(sw, None)
        
        return {
            'tech_keywords': found_tech[:10],
            'general_keywords': word_freq.most_common(15)
        }
    
    def calculate_metrics(self, answers: List[str]) -> Dict:
        """답변 메트릭 계산"""
        if not answers:
            return {'total': 0, 'avg_length': 0}
        
        return {
            'total': len(answers),
            'avg_length': round(sum(len(a) for a in answers) / len(answers), 1),
            'total_chars': sum(len(a) for a in answers)
        }
    
    def generate_report(
        self, 
        session_id: str, 
        emotion_stats: Optional[Dict] = None
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
                key: {"count": val["count"]} 
                for key, val in star_analysis.items()
            },
            "keywords": keywords,
            "emotion_stats": emotion_stats,
            "feedback": self._generate_feedback(star_analysis, metrics, keywords)
        }
        
        return report
    
    def _generate_feedback(self, star_analysis: Dict, metrics: Dict, keywords: Dict) -> List[str]:
        """피드백 생성"""
        feedback = []
        
        # STAR 분석 피드백
        weak_elements = [k for k, v in star_analysis.items() if v['count'] < 2]
        if weak_elements:
            element_names = {
                'situation': '상황(S)', 'task': '과제(T)',
                'action': '행동(A)', 'result': '결과(R)'
            }
            weak_names = [element_names[e] for e in weak_elements]
            feedback.append(f"📝 STAR 기법에서 {', '.join(weak_names)} 요소를 더 보완하면 좋겠습니다.")
        
        # 답변 길이 피드백
        if metrics.get('avg_length', 0) < 50:
            feedback.append("💡 답변을 더 구체적이고 상세하게 작성해보세요.")
        
        # 기술 키워드 피드백
        if not keywords.get('tech_keywords'):
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
                    "happy": "happy", "sad": "sad", "angry": "angry",
                    "surprise": "surprise", "fear": "fear", 
                    "disgust": "disgust", "neutral": "neutral"
                }
                raw = {k: float(scores.get(src, 0.0)) for k, src in keys_map.items()}
                total = sum(raw.values()) or 1.0
                probabilities = {k: (v / total) for k, v in raw.items()}
                
                data = {
                    "dominant_emotion": item.get("dominant_emotion"),
                    "probabilities": probabilities,
                    "raw_scores": raw
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
                        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        img_base64 = base64.b64encode(buffer).decode('utf-8')
                        
                        # 세션에 이미지 저장 (최대 30개)
                        session = state.get_session(session_id)
                        if session:
                            emotion_images = session.get("emotion_images", [])
                            if len(emotion_images) < 30:
                                emotion_images.append(img_base64)
                                state.update_session(session_id, {"emotion_images": emotion_images})
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
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in skip_headers}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(target_url, headers=fwd_headers)
            content_type = resp.headers.get("content-type", "application/octet-stream")
            from fastapi.responses import Response
            return Response(content=resp.content, status_code=resp.status_code,
                          headers={"content-type": content_type, "cache-control": resp.headers.get("cache-control", "")})
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
    """프로필 페이지 → Next.js 프록시"""
    return await _proxy_to_nextjs(request, "profile")


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
                content={"error": "카카오 로그인이 설정되지 않았습니다."}
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
                status_code=400,
                content={"error": "구글 로그인이 설정되지 않았습니다."}
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
                content={"error": "네이버 로그인이 설정되지 않았습니다."}
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
            status_code=400,
            content={"error": f"지원하지 않는 소셜 로그인: {provider}"}
        )
    
    return RedirectResponse(url=auth_url)


@app.get("/api/auth/social/{provider}/callback")
async def social_login_callback(provider: str, code: str = None, state: str = None, error: str = None):
    """소셜 로그인 콜백"""
    from fastapi.responses import RedirectResponse
    import httpx
    
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
                        "code": code
                    }
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # 사용자 정보 조회
                user_response = await client.get(
                    "https://kapi.kakao.com/v2/user/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                user_data = user_response.json()
                
                email = user_data.get("kakao_account", {}).get("email", f"kakao_{user_data['id']}@kakao.local")
                name = user_data.get("properties", {}).get("nickname", "카카오사용자")
                
            elif provider == "google":
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code": code
                    }
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # 사용자 정보 조회
                user_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
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
                        "state": state
                    }
                )
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # 사용자 정보 조회
                user_response = await client.get(
                    "https://openapi.naver.com/v1/nid/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                user_data = user_response.json()
                response_data = user_data.get("response", {})
                
                email = response_data.get("email", f"naver_{response_data.get('id')}@naver.local")
                name = response_data.get("name") or response_data.get("nickname", "네이버사용자")
            
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
                    "role": "candidate"
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
                "created_at": datetime.now().isoformat()
            }
            
            return RedirectResponse(url=f"/?token={temp_token}")
            
    except Exception as e:
        print(f"❌ 소셜 로그인 오류: {e}")
        return RedirectResponse(url=f"/?error=login_failed")


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
            "gender": user.get("gender")
        }
    }


@app.get("/api/auth/social/status")
async def social_login_status():
    """소셜 로그인 설정 상태 확인"""
    return {
        "kakao": bool(KAKAO_CLIENT_ID),
        "google": bool(GOOGLE_CLIENT_ID),
        "naver": bool(NAVER_CLIENT_ID)
    }


# ========== 회원가입/로그인 API ==========

@app.get("/api/auth/check-email")
async def check_email_duplicate(email: str):
    """이메일 중복 확인 API"""
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
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
        return UserRegisterResponse(
            success=False,
            message="이미 등록된 이메일입니다."
        )
    
    # 이메일 형식 검증
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, request.email):
        return UserRegisterResponse(
            success=False,
            message="올바른 이메일 형식이 아닙니다."
        )
    
    # 생년월일 검증
    try:
        birth = datetime.strptime(request.birth_date, "%Y-%m-%d")
        if birth > datetime.now():
            return UserRegisterResponse(
                success=False,
                message="생년월일이 올바르지 않습니다."
            )
    except ValueError:
        return UserRegisterResponse(
            success=False,
            message="생년월일 형식이 올바르지 않습니다. (YYYY-MM-DD)"
        )
    
    # 성별 검증
    if request.gender not in ["male", "female"]:
        return UserRegisterResponse(
            success=False,
            message="성별을 선택해주세요."
        )
    
    # 역할 검증
    if request.role not in ["candidate", "recruiter"]:
        return UserRegisterResponse(
            success=False,
            message="회원 유형을 선택해주세요. (지원자 또는 면접관)"
        )
    
    # 비밀번호 검증
    if len(request.password) < 8:
        return UserRegisterResponse(
            success=False,
            message="비밀번호는 8자 이상이어야 합니다."
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
        "role": request.role  # 사용자가 선택한 역할
    }
    
    # DB에 저장
    create_user(user_data)
    
    # 저장된 사용자 조회하여 ID 가져오기
    saved_user = get_user_by_email(request.email)
    user_id = saved_user["user_id"] if saved_user else None
    
    role_text = "지원자" if request.role == "candidate" else "면접관"
    print(f"✅ 새 회원 가입: {request.name} ({request.email}) - {role_text}")
    
    return UserRegisterResponse(
        success=True,
        message="회원가입이 완료되었습니다.",
        user_id=user_id
    )


@app.post("/api/auth/login", response_model=UserLoginResponse)
async def login_user(request: UserLoginRequest):
    """로그인 API (이메일 + 비밀번호)"""
    # DB에서 사용자 조회
    user = get_user_by_email(request.email)
    
    if not user:
        return UserLoginResponse(
            success=False,
            message="등록되지 않은 이메일입니다. 회원가입을 먼저 해주세요."
        )
    
    # 비밀번호 검증 (bcrypt + SHA-256 하위 호환)
    if not verify_password(request.password, user.get("password_hash", "")):
        return UserLoginResponse(
            success=False,
            message="비밀번호가 올바르지 않습니다."
        )
    
    # SHA-256 → bcrypt 자동 마이그레이션
    if needs_rehash(user.get("password_hash", "")):
        new_hash = hash_password(request.password)
        update_user(request.email, {"password_hash": new_hash})
        print(f"🔄 비밀번호 해시 마이그레이션 완료: {request.email} (SHA-256 → bcrypt)")
    
    # 민감 정보 제외하고 반환
    user_info = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "gender": user["gender"]
    }
    
    # JWT 액세스 토큰 발급
    access_token = create_access_token(data={
        "sub": user["email"],
        "user_id": str(user["user_id"]),
        "name": user["name"],
        "role": user.get("role", "candidate")
    })
    
    print(f"✅ 로그인: {user['name']} ({user['email']})")
    
    return UserLoginResponse(
        success=True,
        message="로그인 성공",
        user=user_info,
        access_token=access_token
    )


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
        "created_at": user["created_at"]
    }


# ========== 프론트엔드 호환 래퍼 API (GET/PUT /api/user) ==========

@app.get("/api/user")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """현재 로그인 유저 정보 조회 (토큰 기반)"""
    user = get_user_by_email(current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {
        "user_id": user["user_id"], "email": user["email"],
        "name": user["name"], "birth_date": user.get("birth_date"),
        "address": user.get("address"), "gender": user.get("gender"),
        "role": user.get("role"), "created_at": user.get("created_at")
    }


@app.put("/api/user")
async def update_current_user_info(data: dict, current_user: Dict = Depends(get_current_user)):
    """현재 로그인 유저 정보 수정 (토큰 기반)"""
    from pydantic import BaseModel as BM
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
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserUpdateResponse(BaseModel):
    success: bool
    message: str


@app.put("/api/auth/user/update")
async def update_user_info(request: UserUpdateRequest, current_user: Dict = Depends(get_current_user)):
    """회원 정보 수정 API (인증 필요)"""
    
    # 사용자 존재 확인
    user = get_user_by_email(request.email)
    if not user:
        return UserUpdateResponse(
            success=False,
            message="사용자를 찾을 수 없습니다."
        )
    
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
                success=False,
                message="올바른 성별을 선택해주세요."
            )
        update_data["gender"] = request.gender
    
    # 전화번호 수정
    if request.phone is not None:
        update_data["phone"] = request.phone
    
    # 비밀번호 변경
    if request.new_password:
        if not request.current_password:
            return UserUpdateResponse(
                success=False,
                message="현재 비밀번호를 입력해주세요."
            )
        
        # 현재 비밀번호 확인 (bcrypt + SHA-256 하위 호환)
        if not verify_password(request.current_password, user.get("password_hash", "")):
            return UserUpdateResponse(
                success=False,
                message="현재 비밀번호가 일치하지 않습니다."
            )
        
        if len(request.new_password) < 8:
            return UserUpdateResponse(
                success=False,
                message="새 비밀번호는 8자 이상이어야 합니다."
            )
        
        update_data["password_hash"] = hash_password(request.new_password)
    
    # 업데이트 실행
    if update_data:
        success = update_user(request.email, update_data)
        if success:
            print(f"✅ 회원 정보 수정: {request.email}")
            return UserUpdateResponse(
                success=True,
                message="회원정보가 수정되었습니다."
            )
        else:
            return UserUpdateResponse(
                success=False,
                message="회원정보 수정에 실패했습니다."
            )
    
    return UserUpdateResponse(
        success=True,
        message="변경된 정보가 없습니다."
    )


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
    current_user: Dict = Depends(get_current_user)
):
    """
    이력서 PDF 파일 업로드 및 RAG 인덱싱
    """
    # 파일 형식 검증
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    
    # 파일 크기 검증 (10MB 제한)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다.")
    
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
                    table_name=RESUME_TABLE,
                    connection_string=connection_string
                )
                
                # PDF 인덱싱
                print(f"📚 이력서 인덱싱 시작: {file_path}")
                num_chunks = session_rag.load_and_index_pdf(file_path)
                
                # 세션에 retriever 저장
                retriever = session_rag.get_retriever()
                state.update_session(session_id, {
                    "resume_uploaded": True,
                    "resume_path": file_path,
                    "resume_filename": file.filename,
                    "retriever": retriever
                })
                
                chunks_created = num_chunks if num_chunks else 1
                print(f"✅ RAG 인덱싱 완료: {RESUME_TABLE}")
            else:
                print("⚠️ POSTGRES_CONNECTION_STRING 미설정, RAG 비활성화")
                state.update_session(session_id, {
                    "resume_uploaded": True,
                    "resume_path": file_path,
                    "resume_filename": file.filename
                })
        except Exception as e:
            print(f"❌ RAG 인덱싱 오류: {e}")
            # RAG 실패해도 파일은 저장되었으므로 성공 반환
            state.update_session(session_id, {
                "resume_uploaded": True,
                "resume_path": file_path,
                "resume_filename": file.filename
            })
    else:
        # RAG 비활성화 상태에서도 파일 정보 저장
        state.update_session(session_id, {
            "resume_uploaded": True,
            "resume_path": file_path,
            "resume_filename": file.filename
        })

    # 📤 이벤트 발행: 이력서 업로드
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.RESUME_UPLOADED,
            session_id=session_id,
            user_email=user_email,
            data={"filename": file.filename, "chunks_created": chunks_created},
            source="resume_api",
        )

    return ResumeUploadResponse(
        success=True,
        message="이력서가 성공적으로 업로드되었습니다." + (
            " RAG 인덱싱이 완료되어 면접 질문에 반영됩니다." if RAG_AVAILABLE else ""
        ),
        session_id=session_id,
        filename=file.filename,
        chunks_created=chunks_created if chunks_created > 0 else None
    )


@app.get("/api/resume/status/{session_id}")
async def get_resume_status(session_id: str):
    """세션의 이력서 업로드 상태 확인"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return {
        "session_id": session_id,
        "resume_uploaded": session.get("resume_uploaded", False),
        "resume_filename": session.get("resume_filename"),
        "rag_enabled": session.get("retriever") is not None
    }


@app.delete("/api/resume/{session_id}")
async def delete_resume(session_id: str, current_user: Dict = Depends(get_current_user)):
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
    
    state.update_session(session_id, {
        "resume_uploaded": False,
        "resume_path": None,
        "resume_filename": None,
        "retriever": None
    })
    
    return {"success": True, "message": "이력서가 삭제되었습니다."}


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
        return {"success": False, "message": "이미 인덱싱이 진행 중입니다.", "status": _qa_index_status}
    
    # data.json 경로
    json_path = os.path.join(root_dir, "Data", "data.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail=f"데이터 파일을 찾을 수 없습니다: {json_path}")
    
    _qa_index_status = {"status": "indexing", "indexed": 0, "total": 0, "error": None}
    
    try:
        # 별도 컬렉션으로 인덱싱 (이력서 데이터와 분리)
        rag = ResumeRAG(table_name=QA_TABLE)
        
        # 비동기 실행 (대량 데이터이므로 ThreadPool 사용)
        indexed_count = await run_in_executor(
            RAG_EXECUTOR,
            rag.load_and_index_json,
            json_path,
            100
        )
        
        _qa_index_status = {"status": "completed", "indexed": indexed_count, "total": indexed_count, "error": None}
        print(f"✅ 면접 Q&A 데이터 인덱싱 완료: {indexed_count}개 청크")
        
        return {
            "success": True,
            "message": f"면접 Q&A 데이터 인덱싱 완료: {indexed_count}개 청크가 저장되었습니다.",
            "chunks_indexed": indexed_count
        }
    except Exception as e:
        _qa_index_status = {"status": "error", "indexed": 0, "total": 0, "error": str(e)}
        print(f"❌ Q&A 인덱싱 실패: {e}")
        raise HTTPException(status_code=500, detail=f"인덱싱 실패: {str(e)}")

@app.get("/api/qa-data/status")
async def qa_data_status():
    """Q&A 데이터 인덱싱 상태 조회"""
    return _qa_index_status

@app.get("/api/qa-data/search")
async def search_qa_data(q: str, k: int = 4):
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
            ]
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
async def get_interviews_list(email: str, current_user: Dict = Depends(get_current_user)):
    """면접 이력 목록 조회 (프론트엔드 호환)"""
    return await get_interview_history(email, current_user)


@app.get("/api/interview/history")
async def get_interview_history(email: str, current_user: Dict = Depends(get_current_user)):
    """사용자 이메일 기준 면접 이력 조회 (인증 필요)"""
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    history = []
    for sid, session in state.sessions.items():
        if session.get("user_email") == email and session.get("status") in ("completed", "active"):
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
            
            history.append({
                "session_id": sid,
                "date": session.get("created_at", ""),
                "summary": summary,
                "score": avg_score,
                "status": session.get("status"),
                "message_count": len(chat_history)
            })
    
    # 최신순 정렬
    history.sort(key=lambda x: x["date"], reverse=True)
    
    return history


# ========== 세션 생성 요청 모델 ==========
class SessionCreateRequest(BaseModel):
    user_email: Optional[str] = None
    user_id: Optional[str] = None


# ========== Session API ==========

@app.post("/api/session/create")
@app.post("/api/session")
async def create_session(request: SessionCreateRequest = None, current_user: Dict = Depends(get_current_user)):
    """새 면접 세션 생성 (인증 필요)"""
    # 사용자 인증 확인
    if not request or not request.user_email:
        raise HTTPException(
            status_code=401, 
            detail="면접을 시작하려면 로그인이 필요합니다."
        )
    
    # 사용자 존재 여부 확인
    user = get_user_by_email(request.user_email)
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="유효하지 않은 사용자입니다. 다시 로그인해주세요."
        )
    
    session_id = state.create_session()
    greeting = interviewer.get_initial_greeting()
    
    # 초기 인사 저장 (사용자 정보 포함)
    state.update_session(session_id, {
        "status": "active",
        "user_email": request.user_email,
        "user_id": request.user_id,
        "user_name": user.get("name", ""),
        "chat_history": [{"role": "assistant", "content": greeting}]
    })
    
    # 같은 사용자가 이전에 업로드한 이력서(RAG retriever)가 있으면 새 세션으로 복사
    for sid, s in state.sessions.items():
        if sid != session_id and s.get("user_email") == request.user_email and s.get("resume_uploaded"):
            retriever = s.get("retriever")
            if retriever:
                state.update_session(session_id, {
                    "resume_uploaded": True,
                    "resume_path": s.get("resume_path"),
                    "resume_filename": s.get("resume_filename"),
                    "retriever": retriever
                })
                print(f"📚 이전 세션({sid[:8]})의 이력서 RAG를 새 세션에 연결함")
                break
    
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

    return {
        "session_id": session_id,
        "greeting": greeting,
        "status": "active"
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """세션 정보 조회"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return SessionInfo(
        session_id=session["id"],
        status=session["status"],
        created_at=session["created_at"],
        message_count=len(session.get("chat_history", []))
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
async def start_user_turn(request: StartUserTurnRequest):
    """사용자 발화 시작 - 질문 후 호출"""
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
        "warning_time_seconds": intervention_manager.SOFT_WARNING_TIME
    }


@app.post("/api/intervention/vad-signal")
async def update_vad_signal(request: VADSignalRequest):
    """VAD 신호 업데이트 (실시간 스트리밍)"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # VAD 신호 업데이트
    turn_state = intervention_manager.update_vad_signal(
        request.session_id,
        request.is_speech,
        request.audio_level
    )
    
    # Turn-taking 신호 확인
    turn_signal = intervention_manager.get_turn_taking_signal(request.session_id)
    
    return {
        "turn_state": turn_state,
        "can_interrupt": turn_signal["can_interrupt"],
        "interrupt_reason": turn_signal.get("interrupt_reason", ""),
        "silence_duration_ms": turn_signal.get("silence_duration_ms", 0)
    }


@app.post("/api/intervention/check")
async def check_intervention(request: InterventionCheckRequest):
    """개입 필요 여부 확인"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # 개입 체크
    intervention = intervention_manager.check_intervention_needed(
        request.session_id,
        request.current_answer
    )
    
    # Turn-taking 신호
    turn_signal = intervention_manager.get_turn_taking_signal(request.session_id)
    
    if intervention:
        return {
            "needs_intervention": True,
            "intervention": intervention,
            "turn_signal": turn_signal
        }
    
    return {
        "needs_intervention": False,
        "intervention": None,
        "turn_signal": turn_signal
    }


@app.post("/api/intervention/end-turn")
async def end_user_turn(session_id: str):
    """사용자 발화 종료"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    stats = intervention_manager.end_user_turn(session_id)
    
    return {
        "success": True,
        "stats": stats
    }


@app.get("/api/intervention/stats/{session_id}")
async def get_intervention_stats(session_id: str):
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
            "intervention_count": stats["state"].get("intervention_count", 0)
        }
    }


class InterventionSettingsRequest(BaseModel):
    max_answer_time: Optional[int] = None
    max_answer_length: Optional[int] = None
    soft_warning_time: Optional[int] = None
    topic_relevance_threshold: Optional[float] = None

@app.post("/api/intervention/settings")
async def update_intervention_settings(request: InterventionSettingsRequest):
    """개입 설정 업데이트"""
    if request.max_answer_time:
        intervention_manager.MAX_ANSWER_TIME_SECONDS = request.max_answer_time
    if request.max_answer_length:
        intervention_manager.MAX_ANSWER_LENGTH = request.max_answer_length
    if request.soft_warning_time:
        intervention_manager.SOFT_WARNING_TIME = request.soft_warning_time
    if request.topic_relevance_threshold:
        intervention_manager.TOPIC_RELEVANCE_THRESHOLD = request.topic_relevance_threshold
    
    return {
        "success": True,
        "current_settings": {
            "max_answer_time_seconds": intervention_manager.MAX_ANSWER_TIME_SECONDS,
            "max_answer_length": intervention_manager.MAX_ANSWER_LENGTH,
            "soft_warning_time_seconds": intervention_manager.SOFT_WARNING_TIME,
            "topic_relevance_threshold": intervention_manager.TOPIC_RELEVANCE_THRESHOLD
        }
    }


@app.get("/api/intervention/settings")
async def get_intervention_settings():
    """현재 개입 설정 조회"""
    return {
        "max_answer_time_seconds": intervention_manager.MAX_ANSWER_TIME_SECONDS,
        "max_answer_length": intervention_manager.MAX_ANSWER_LENGTH,
        "soft_warning_time_seconds": intervention_manager.SOFT_WARNING_TIME,
        "soft_warning_length": intervention_manager.SOFT_WARNING_LENGTH,
        "silence_threshold_ms": intervention_manager.SILENCE_THRESHOLD_MS,
        "topic_relevance_threshold": intervention_manager.TOPIC_RELEVANCE_THRESHOLD
    }


# ========== Chat API ==========

class ChatRequestWithIntervention(BaseModel):
    session_id: str
    message: str
    use_rag: bool = True
    was_interrupted: bool = False  # 개입으로 인한 강제 종료 여부
    intervention_type: Optional[str] = None  # 개입 유형

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: Dict = Depends(get_current_user)):
    """채팅 메시지 전송 및 AI 응답 받기"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # 사용자 턴 종료 처리 (개입 시스템)
    turn_stats = intervention_manager.end_user_turn(request.session_id)
    
    # 발화 분석 턴 종료
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_service.end_turn(request.session_id, request.message)
        except Exception as e:
            print(f"[SpeechAnalysis] 턴 종료 오류: {e}")
    
    # 시선 추적 턴 종료
    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_service.end_turn(request.session_id)
        except Exception as e:
            print(f"[GazeTracking] 턴 종료 오류: {e}")
    
    # AI 응답 생성
    response = await interviewer.generate_response(
        request.session_id,
        request.message,
        request.use_rag
    )
    
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
    
    # TTS 생성 (선택적)
    audio_url = None
    if TTS_AVAILABLE and interviewer.tts_service:
        try:
            audio_file = await interviewer.generate_speech(response)
            if audio_file:
                audio_url = f"/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            print(f"TTS 생성 오류: {e}")

    # 📤 이벤트 발행: 질문 생성 + 답변 제출
    if EVENT_BUS_AVAILABLE and event_bus:
        await event_bus.publish(
            AppEventType.ANSWER_SUBMITTED,
            session_id=request.session_id,
            data={"answer": request.message[:200], "question": response[:200]},
            source="chat_api",
        )
        await event_bus.publish(
            AppEventType.QUESTION_GENERATED,
            session_id=request.session_id,
            data={"question": response[:200], "has_audio": audio_url is not None},
            source="ai_interviewer",
        )

    return ChatResponse(
        session_id=request.session_id,
        response=response,
        audio_url=audio_url
    )


@app.post("/api/chat/with-intervention")
async def chat_with_intervention(request: ChatRequestWithIntervention, current_user: Dict = Depends(get_current_user)):
    """개입 정보를 포함한 채팅 메시지 전송"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
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
        print(f"⚡ [Chat] 세션 {request.session_id[:8]}... 개입으로 인한 답변 종료 ({request.intervention_type})")
    
    # AI 응답 생성
    response = await interviewer.generate_response(
        request.session_id,
        request.message,
        request.use_rag
    )
    
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
    
    # TTS 생성
    audio_url = None
    if TTS_AVAILABLE and interviewer.tts_service:
        try:
            audio_file = await interviewer.generate_speech(response)
            if audio_file:
                audio_url = f"/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            print(f"TTS 생성 오류: {e}")
    
    return {
        "session_id": request.session_id,
        "response": response,
        "audio_url": audio_url,
        "turn_stats": turn_stats,
        "was_interrupted": request.was_interrupted,
        "next_question_keywords": question_keywords
    }


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
    
    # 세션의 평가 결과 포함
    evaluations = session.get("evaluations", [])
    if evaluations:
        # 평균 점수 계산
        avg_scores = {
            "specificity": 0, "logic": 0, "technical": 0, "star": 0, "communication": 0
        }
        for ev in evaluations:
            for key in avg_scores:
                avg_scores[key] += ev.get("scores", {}).get(key, 0)
        
        if len(evaluations) > 0:
            for key in avg_scores:
                avg_scores[key] = round(avg_scores[key] / len(evaluations), 1)
        
        report["llm_evaluation"] = {
            "answer_count": len(evaluations),
            "average_scores": avg_scores,
            "total_average": round(sum(avg_scores.values()) / 5, 1),
            "all_evaluations": evaluations
        }
    
    # REQ-F-006: 발화 분석 데이터 추가
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_stats = speech_service.get_session_stats(session_id)
            if speech_stats:
                report["speech_analysis"] = speech_stats.to_dict()
        except Exception as e:
            print(f"[Report] 발화 분석 데이터 조회 오류: {e}")
    
    # REQ-F-006: 시선 추적 데이터 추가
    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_stats = gaze_service.get_session_stats(session_id)
            if gaze_stats:
                report["gaze_analysis"] = gaze_stats.to_dict()
        except Exception as e:
            print(f"[Report] 시선 추적 데이터 조회 오류: {e}")
    
    # Hume Prosody 음성 감정 분석 데이터 추가
    if PROSODY_AVAILABLE and prosody_service:
        try:
            prosody_stats = prosody_service.get_session_stats_dict(session_id)
            if prosody_stats and prosody_stats.get("total_samples", 0) > 0:
                report["prosody_analysis"] = prosody_stats
        except Exception as e:
            print(f"[Report] Prosody 분석 데이터 조회 오류: {e}")
    
    return report


# ========== PDF Report Download API ==========

@app.get("/api/report/{session_id}/pdf")
async def get_report_pdf(session_id: str, current_user: Dict = Depends(get_current_user)):
    """면접 리포트 PDF 다운로드"""
    if not PDF_REPORT_AVAILABLE or not generate_pdf_report:
        raise HTTPException(status_code=501, detail="PDF 리포트 서비스가 비활성화되어 있습니다.")
    
    # 기존 리포트 생성 로직 재사용
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    generator = InterviewReportGenerator()
    emotion_stats = None
    if state.last_emotion:
        emotion_stats = state.last_emotion
    
    report = generator.generate_report(session_id, emotion_stats)
    
    # 평가 결과 포함
    evaluations = session.get("evaluations", [])
    if evaluations:
        avg_scores = {
            "specificity": 0, "logic": 0, "technical": 0, "star": 0, "communication": 0
        }
        for ev in evaluations:
            for key in avg_scores:
                avg_scores[key] += ev.get("scores", {}).get(key, 0)
        if len(evaluations) > 0:
            for key in avg_scores:
                avg_scores[key] = round(avg_scores[key] / len(evaluations), 1)
        report["llm_evaluation"] = {
            "answer_count": len(evaluations),
            "average_scores": avg_scores,
            "total_average": round(sum(avg_scores.values()) / 5, 1),
            "all_evaluations": evaluations
        }
    
    # 발화 분석 데이터 추가
    if SPEECH_ANALYSIS_AVAILABLE and speech_service:
        try:
            speech_stats = speech_service.get_session_stats(session_id)
            if speech_stats:
                report["speech_analysis"] = speech_stats.to_dict()
        except Exception:
            pass
    
    # 시선 추적 데이터 추가
    if GAZE_TRACKING_AVAILABLE and gaze_service:
        try:
            gaze_stats = gaze_service.get_session_stats(session_id)
            if gaze_stats:
                report["gaze_analysis"] = gaze_stats.to_dict()
        except Exception:
            pass
    
    try:
        pdf_bytes = generate_pdf_report(report)
        
        from fastapi.responses import Response
        filename = f"interview_report_{session_id[:8]}_{datetime.now().strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
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
    strengths: List[str]
    improvements: List[str]
    brief_feedback: str

@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate_answer(request: EvaluateRequest, current_user: Dict = Depends(get_current_user)):
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
        request.session_id,
        request.question,
        request.answer
    )
    
    # 세션에 평가 저장
    evaluations = session.get("evaluations", [])
    evaluations.append({
        "question": request.question,
        "answer": request.answer,
        **evaluation
    })
    state.update_session(request.session_id, {"evaluations": evaluations})
    
    return EvaluateResponse(
        session_id=request.session_id,
        scores=evaluation.get("scores", {}),
        total_score=evaluation.get("total_score", 0),
        strengths=evaluation.get("strengths", []),
        improvements=evaluation.get("improvements", []),
        brief_feedback=evaluation.get("brief_feedback", "")
    )


@app.get("/api/evaluations/{session_id}")
async def get_evaluations(session_id: str, current_user: Dict = Depends(get_current_user)):
    """세션의 모든 평가 결과 조회 (인증 필요)"""
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    evaluations = session.get("evaluations", [])
    
    # 통계 계산
    if evaluations:
        avg_scores = {"specificity": 0, "logic": 0, "technical": 0, "star": 0, "communication": 0}
        for ev in evaluations:
            for key in avg_scores:
                avg_scores[key] += ev.get("scores", {}).get(key, 0)
        for key in avg_scores:
            avg_scores[key] = round(avg_scores[key] / len(evaluations), 1)
        
        return {
            "session_id": session_id,
            "total_answers": len(evaluations),
            "average_scores": avg_scores,
            "total_average": round(sum(avg_scores.values()) / 5, 1),
            "evaluations": evaluations
        }
    
    return {
        "session_id": session_id,
        "total_answers": 0,
        "average_scores": {},
        "evaluations": []
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
                        recording_service.start_recording(session_id, width=640, height=480, fps=15)
                    except Exception as e:
                        print(f"⚠️ [Recording] 녹화 시작 실패: {e}")
                # 감정 분석 + 녹화 통합 루프
                asyncio.create_task(_video_pipeline(track, session_id))
            else:
                # 오디오 트랙 STT 라우팅: Deepgram(우선) → Whisper(폴백) → 소비만
                # + 녹화 오디오 파이프
                asyncio.create_task(_audio_pipeline(track, session_id))
        
        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer.sdp, type=offer.type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "session_id": session_id
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
    recording_active = RECORDING_AVAILABLE and recording_service and \
                        recording_service.get_recording(session_id) is not None

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
                    "happy": "happy", "sad": "sad", "angry": "angry",
                    "surprise": "surprise", "fear": "fear",
                    "disgust": "disgust", "neutral": "neutral"
                }
                raw = {k: float(scores.get(src, 0.0)) for k, src in keys_map.items()}
                total = sum(raw.values()) or 1.0
                probabilities = {k: (v / total) for k, v in raw.items()}

                data = {
                    "dominant_emotion": item.get("dominant_emotion"),
                    "probabilities": probabilities,
                    "raw_scores": raw
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
    import io, struct
    try:
        # --- PCM (16kHz, 16bit, mono) → WAV 변환 ---
        wav_buf = io.BytesIO()
        num_samples = len(raw_pcm) // 2
        sample_rate = 16000
        # WAV header
        wav_buf.write(b'RIFF')
        data_size = num_samples * 2
        wav_buf.write(struct.pack('<I', 36 + data_size))
        wav_buf.write(b'WAVE')
        wav_buf.write(b'fmt ')
        wav_buf.write(struct.pack('<IHHIIHH', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        wav_buf.write(b'data')
        wav_buf.write(struct.pack('<I', data_size))
        wav_buf.write(raw_pcm)
        wav_bytes = wav_buf.getvalue()

        # --- Prosody 분석 (Streaming REST API) ---
        result = await asyncio.get_event_loop().run_in_executor(
            LLM_EXECUTOR,
            lambda: prosody_service.analyze_audio_stream(session_id, wav_bytes, transcript)
        )

        if result and result.get("interview_indicators"):
            # InterviewState에 최신 prosody 저장
            state.last_prosody = result

            # WebSocket으로 클라이언트에 전송
            await broadcast_stt_result(session_id, {
                "type": "prosody_result",
                "indicators": result["interview_indicators"],
                "dominant_indicator": result.get("dominant_indicator", ""),
                "adaptive_mode": result.get("adaptive_mode", "normal"),
                "timestamp": time.time()
            })

            print(f"[Prosody] 세션 {session_id[:8]}... "
                  f"주요감정: {result.get('dominant_indicator', '?')} "
                  f"모드: {result.get('adaptive_mode', '?')}")

    except Exception as e:
        print(f"[Prosody] 분석 오류 (세션 {session_id[:8]}): {e}")


async def _audio_pipeline(track, session_id: str):
    """
    오디오 트랙 통합 파이프라인:
    1. STT 처리 (Deepgram/Whisper)
    2. GStreamer/FFmpeg 녹화 파이프에 오디오 프레임 전송
    """
    import numpy as np
    recording_active = RECORDING_AVAILABLE and recording_service and \
                        recording_service.get_recording(session_id) is not None

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
            track, session_id, whisper_service,
            broadcast_stt_result,
            speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
        )


async def _process_audio_with_stt_and_recording(track, session_id: str, recording_active: bool):
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

                    if hasattr(message, 'results') and getattr(message.results, 'channels', None):
                        is_final = getattr(message.results, 'is_final', False)
                        alts = message.results.channels[0].alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], 'confidence', None)
                            raw_words = getattr(alts[0], 'words', None)
                            if raw_words:
                                words_list = [
                                    {"word": getattr(w, 'word', getattr(w, 'punctuated_word', '')),
                                     "start": getattr(w, 'start', 0.0),
                                     "end": getattr(w, 'end', 0.0),
                                     "confidence": getattr(w, 'confidence', 0.0)}
                                    for w in raw_words
                                ]
                    elif hasattr(message, 'channel') and getattr(message.channel, 'alternatives', None):
                        is_final = getattr(message, 'is_final', True)
                        alts = message.channel.alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], 'confidence', None)
                            raw_words = getattr(alts[0], 'words', None)
                            if raw_words:
                                words_list = [
                                    {"word": getattr(w, 'word', getattr(w, 'punctuated_word', '')),
                                     "start": getattr(w, 'start', 0.0),
                                     "end": getattr(w, 'end', 0.0),
                                     "confidence": getattr(w, 'confidence', 0.0)}
                                    for w in raw_words
                                ]

                    if transcript:
                        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
                            try:
                                speech_service.add_stt_result(
                                    session_id, transcript, is_final,
                                    confidence=confidence, words=words_list
                                )
                            except Exception as e:
                                print(f"[SpeechAnalysis] 데이터 전달 오류: {e}")

                        if is_final and SPACING_CORRECTION_AVAILABLE and _spacing_corrector:
                            corrected = _spacing_corrector.correct(transcript)
                            if corrected and corrected.strip():
                                transcript = corrected

                        asyncio.create_task(broadcast_stt_result(session_id, {
                            "type": "stt_result",
                            "transcript": transcript,
                            "is_final": is_final,
                            "timestamp": time.time()
                        }))

                        # ── Hume Prosody 음성 감정 분석 (최종 발화 시) ──
                        if is_final and PROSODY_AVAILABLE and prosody_service:
                            buffered = bytes(_prosody_audio_buffers.get(session_id, b''))
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

            dg_connection.on(EventType.OPEN, lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결됨"))
            dg_connection.on(EventType.MESSAGE, on_message)
            dg_connection.on(EventType.CLOSE, lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결 종료"))
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
                        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                        else:
                            audio_bytes = audio_data.astype(np.int16).tobytes()

                        # → Deepgram STT 전송
                        from deepgram.extensions.types.sockets import ListenV1MediaMessage
                        dg_connection.send_media(ListenV1MediaMessage(audio_bytes))

                        # → Prosody 오디오 버퍼 축적
                        if PROSODY_AVAILABLE and prosody_service and session_id in _prosody_audio_buffers:
                            _prosody_audio_buffers[session_id].extend(audio_bytes)

                        # → 녹화 파이프 전송
                        if recording_active:
                            try:
                                await recording_service.write_audio_frame(session_id, audio_bytes)
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
            print(f"🔄 [STT] 세션 {session_id[:8]}... Deepgram 실패 → Whisper 폴백 전환")
            await process_audio_with_whisper(
                track, session_id, whisper_service,
                broadcast_stt_result,
                speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
            )
        else:
            print(f"⚠️ [STT] 세션 {session_id[:8]}... Whisper 폴백도 불가 — STT 비활성화")


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
                    
                    if hasattr(message, 'results') and getattr(message.results, 'channels', None):
                        is_final = getattr(message.results, 'is_final', False)
                        alts = message.results.channels[0].alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], 'confidence', None)
                            # word-level 타이밍/confidence 추출
                            raw_words = getattr(alts[0], 'words', None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(w, 'word', getattr(w, 'punctuated_word', '')),
                                        "start": getattr(w, 'start', 0.0),
                                        "end": getattr(w, 'end', 0.0),
                                        "confidence": getattr(w, 'confidence', 0.0),
                                    }
                                    for w in raw_words
                                ]
                    elif hasattr(message, 'channel') and getattr(message.channel, 'alternatives', None):
                        is_final = getattr(message, 'is_final', True)
                        alts = message.channel.alternatives
                        if alts:
                            transcript = alts[0].transcript
                            confidence = getattr(alts[0], 'confidence', None)
                            raw_words = getattr(alts[0], 'words', None)
                            if raw_words:
                                words_list = [
                                    {
                                        "word": getattr(w, 'word', getattr(w, 'punctuated_word', '')),
                                        "start": getattr(w, 'start', 0.0),
                                        "end": getattr(w, 'end', 0.0),
                                        "confidence": getattr(w, 'confidence', 0.0),
                                    }
                                    for w in raw_words
                                ]
                    
                    if transcript:
                        # 발화 분석 서비스에 STT 결과 전달
                        if SPEECH_ANALYSIS_AVAILABLE and speech_service:
                            try:
                                speech_service.add_stt_result(
                                    session_id, transcript, is_final,
                                    confidence=confidence, words=words_list
                                )
                            except Exception as e:
                                print(f"[SpeechAnalysis] 데이터 전달 오류: {e}")
                        
                        # 최종 결과에 한국어 띄어쓰기 보정 적용
                        if is_final and SPACING_CORRECTION_AVAILABLE and _spacing_corrector:
                            corrected = _spacing_corrector.correct(transcript)
                            if corrected and corrected.strip():
                                transcript = corrected
                        
                        # 비동기 브로드캐스트를 위해 이벤트 루프에 태스크 추가
                        asyncio.create_task(broadcast_stt_result(session_id, {
                            "type": "stt_result",
                            "transcript": transcript,
                            "is_final": is_final,
                            "timestamp": time.time()
                        }))
                        
                except Exception as e:
                    print(f"[STT] 메시지 처리 오류: {e}")
            
            def on_error(error) -> None:
                print(f"[STT] Deepgram 오류: {error}")
            
            dg_connection.on(EventType.OPEN, lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결됨"))
            dg_connection.on(EventType.MESSAGE, on_message)
            dg_connection.on(EventType.CLOSE, lambda _: print(f"[STT] 세션 {session_id} Deepgram 연결 종료"))
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
                        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                        else:
                            audio_bytes = audio_data.astype(np.int16).tobytes()
                        
                        # Deepgram에 오디오 전송
                        from deepgram.extensions.types.sockets import ListenV1MediaMessage
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
            print(f"🔄 [STT] 세션 {session_id[:8]}... Deepgram 실패 → Whisper 폴백 전환")
            await process_audio_with_whisper(
                track, session_id, whisper_service,
                broadcast_stt_result,
                speech_service=speech_service if SPEECH_ANALYSIS_AVAILABLE else None,
            )
        else:
            print(f"⚠️ [STT] 세션 {session_id[:8]}... Whisper 폴백도 불가 — STT 비활성화")


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
        raise HTTPException(status_code=503, detail="녹화 서비스 비활성화 (GStreamer/FFmpeg 미설치)")
    try:
        meta = recording_service.start_recording(session_id)
        return {"status": "recording", "recording_id": meta.recording_id, "session_id": session_id}
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
        raise HTTPException(status_code=404, detail="녹화 파일 없음 (트랜스코딩 미완료)")

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
async def get_recording_service_status():
    """녹화 서비스 상태 확인"""
    return {
        "available": RECORDING_AVAILABLE,
        "media_tool": MEDIA_TOOL if RECORDING_AVAILABLE else None,
        "gstreamer": _GST if RECORDING_AVAILABLE else False,
        "ffmpeg": _FFM if RECORDING_AVAILABLE else False,
        "active_recordings": len([
            m for m in (recording_service.get_all_recordings() if RECORDING_AVAILABLE and recording_service else [])
            if m.get("status") == "recording"
        ]),
    }


# ========== WebSocket API (실시간 STT/이벤트) ==========

@app.websocket("/ws/interview/{session_id}")
async def websocket_interview(websocket: WebSocket, session_id: str, token: Optional[str] = None):
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
                ws_token = proto[len("access_token."):]
                break
    
    if not ws_token:
        await websocket.close(code=4001, reason="인증 토큰이 필요합니다.")
        print(f"[WS] 세션 {session_id} 인증 실패: 토큰 없음")
        return
    
    payload = decode_access_token(ws_token)
    if payload is None:
        await websocket.close(code=4001, reason="인증 토큰이 만료되었거나 유효하지 않습니다.")
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
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "user": ws_user_email,
            "stt_available": DEEPGRAM_AVAILABLE
        })
        
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
async def get_emotion_current():
    """현재 감정 상태 조회 (API)"""
    async with state.emotion_lock:
        if state.last_emotion is None:
            return {"status": "no_data"}
        return state.last_emotion


@app.get("/emotion/sessions")
async def get_emotion_sessions():
    """모든 세션 목록 조회"""
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
async def get_emotion_timeseries(session_id: str, emotion: str, limit: int = 100):
    """감정 시계열 데이터 조회"""
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
                data = [[int(m.decode() if isinstance(m, bytes) else m), s] for m, s in res]
        except Exception:
            pass
    return {"session_id": session_id, "emotion": emotion, "points": data}


@app.get("/emotion/stats")
async def get_emotion_stats(session_id: str):
    """감정 통계 조회"""
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
                    "max": max(values)
                }
        except Exception:
            pass
    
    return {"session_id": session_id, "stats": stats}


# ========== Service Status ==========

@app.get("/api/status")
async def get_status():
    """서비스 상태 확인"""
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
        "celery_status": check_celery_status() if CELERY_AVAILABLE else {"status": "disabled"},
        "event_bus_stats": event_bus.get_stats() if EVENT_BUS_AVAILABLE and event_bus else {"status": "disabled"},
    }


@app.get("/api/stt/status")
async def get_stt_status():
    """STT 서비스 상태 상세 조회"""
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
        "active_engine": "deepgram" if DEEPGRAM_AVAILABLE else ("whisper" if WHISPER_AVAILABLE else "none"),
        "spacing_correction": SPACING_CORRECTION_AVAILABLE,
    }
    if WHISPER_AVAILABLE and whisper_service:
        status["fallback"].update(whisper_service.get_status())
    return status


# ========== 이벤트 버스 모니터링 API ==========

@app.get("/api/events/stats")
async def get_event_stats():
    """이벤트 버스 통계 조회"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled"}
    return event_bus.get_stats()


@app.get("/api/events/history")
async def get_event_history(limit: int = 50, event_type: Optional[str] = None):
    """이벤트 히스토리 조회"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled", "events": []}
    return {
        "events": event_bus.get_history(limit=limit, event_type=event_type),
        "total": len(event_bus.get_history(limit=9999)),
    }


@app.get("/api/events/registered")
async def get_registered_events():
    """등록된 이벤트 타입 및 핸들러 목록"""
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"status": "disabled"}
    return {
        "event_types": event_bus.get_registered_events(),
        "handler_count": {k: len(v) for k, v in event_bus._handlers.items() if v},
    }


# ========== LangGraph 워크플로우 시각화/감사 API ==========

@app.get("/api/workflow/status")
async def get_workflow_status():
    """LangGraph 워크플로우 서비스 상태"""
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
        } if interview_workflow else {},
    }


@app.get("/api/workflow/graph")
async def get_workflow_graph():
    """LangGraph 워크플로우 그래프 다이어그램 (Mermaid)"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return {
        "mermaid": interview_workflow.get_graph_mermaid(),
        "format": "mermaid",
    }


@app.get("/api/workflow/graph-definition")
async def get_workflow_graph_definition():
    """LangGraph 워크플로우 정적 그래프 구조 정보"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return interview_workflow.get_graph_definition()


@app.get("/api/workflow/{session_id}/trace")
async def get_workflow_trace(session_id: str):
    """세션의 LangGraph 실행 추적 이력"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    traces = interview_workflow.get_execution_trace(session_id)
    return {
        "session_id": session_id,
        "total_turns": len(traces),
        "traces": traces,
    }


@app.get("/api/workflow/{session_id}/state")
async def get_workflow_state(session_id: str):
    """세션의 현재 워크플로우 상태 요약"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    return interview_workflow.get_current_state_summary(session_id)


@app.get("/api/workflow/{session_id}/checkpoint")
async def get_workflow_checkpoint(session_id: str):
    """세션의 마지막 체크포인트 정보"""
    if not interview_workflow:
        raise HTTPException(status_code=503, detail="LangGraph 워크플로우가 비활성화됨")
    checkpoint = interview_workflow.get_checkpoint(session_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="체크포인트를 찾을 수 없습니다.")
    return checkpoint


@app.get("/api/workflow/{session_id}/checkpoints")
async def list_workflow_checkpoints(session_id: str, limit: int = 10):
    """세션의 체크포인트 이력 목록"""
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
async def async_evaluate_answer(request: AsyncTaskRequest, current_user: Dict = Depends(get_current_user)):
    """
    비동기 답변 평가 (Celery)
    
    - 답변 평가 작업을 Celery Worker에 전달
    - task_id를 반환하여 나중에 결과 조회 가능
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
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
        request.session_id,
        request.question,
        request.answer,
        resume_context
    )
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="평가 작업이 대기열에 추가되었습니다."
    )


@app.post("/api/async/batch-evaluate", response_model=AsyncTaskResponse)
async def async_batch_evaluate(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    비동기 배치 평가 (Celery)
    
    여러 답변을 한 번에 평가합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    data = await request.json()
    session_id = data.get("session_id")
    qa_pairs = data.get("qa_pairs", [])
    
    if not qa_pairs:
        raise HTTPException(status_code=400, detail="평가할 QA 쌍이 없습니다.")
    
    task = batch_evaluate_task.delay(session_id, qa_pairs)
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message=f"{len(qa_pairs)}개 답변의 배치 평가가 시작되었습니다."
    )


@app.post("/api/async/emotion-analysis", response_model=AsyncTaskResponse)
async def async_emotion_analysis(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    비동기 감정 분석 (Celery)
    
    이미지 데이터(Base64)를 받아 감정 분석 수행
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    data = await request.json()
    session_id = data.get("session_id")
    image_data = data.get("image_data")  # Base64 인코딩된 이미지
    
    if not image_data:
        raise HTTPException(status_code=400, detail="이미지 데이터가 없습니다.")
    
    task = analyze_emotion_task.delay(session_id, image_data)
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="감정 분석 작업이 시작되었습니다."
    )


@app.post("/api/async/batch-emotion", response_model=AsyncTaskResponse)
async def async_batch_emotion_analysis(request: Request):
    """
    비동기 배치 감정 분석 (Celery)
    
    여러 이미지를 한 번에 분석합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    data = await request.json()
    session_id = data.get("session_id")
    image_data_list = data.get("images", [])
    
    if not image_data_list:
        raise HTTPException(status_code=400, detail="분석할 이미지가 없습니다.")
    
    task = batch_emotion_analysis_task.delay(session_id, image_data_list)
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message=f"{len(image_data_list)}개 이미지의 감정 분석이 시작되었습니다."
    )


@app.post("/api/async/generate-report", response_model=AsyncTaskResponse)
async def async_generate_report(session_id: str, current_user: Dict = Depends(get_current_user)):
    """
    비동기 리포트 생성 (Celery)
    
    면접 종료 후 종합 리포트를 생성합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    chat_history = session.get("chat_history", [])
    evaluations = session.get("evaluations", [])
    emotion_stats = session.get("emotion_stats", None)
    
    task = generate_report_task.delay(
        session_id,
        chat_history,
        evaluations,
        emotion_stats
    )
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="리포트 생성 작업이 시작되었습니다."
    )


@app.post("/api/async/complete-interview", response_model=AsyncTaskResponse)
async def async_complete_interview(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    비동기 면접 완료 워크플로우 (Celery)
    
    평가 + 감정 분석 + 리포트 생성을 한 번에 처리합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    data = await request.json()
    session_id = data.get("session_id")
    
    session = state.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    chat_history = session.get("chat_history", [])
    emotion_images = data.get("emotion_images", [])
    
    task = complete_interview_workflow_task.delay(
        session_id,
        chat_history,
        emotion_images
    )
    
    return AsyncTaskResponse(
        task_id=task.id,
        status="PENDING",
        message="면접 완료 워크플로우가 시작되었습니다."
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
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready()
    }
    
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
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    result = AsyncResult(task_id, app=celery_app)
    
    try:
        task_result = result.get(timeout=timeout)
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "result": task_result
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "FAILURE",
            "error": str(e)
        }


@app.delete("/api/async/task/{task_id}")
async def cancel_task(task_id: str):
    """
    태스크 취소
    
    실행 대기 중인 태스크를 취소합니다.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery 서비스가 비활성화되어 있습니다.")
    
    celery_app.control.revoke(task_id, terminate=True)
    
    return {
        "task_id": task_id,
        "status": "REVOKED",
        "message": "태스크가 취소되었습니다."
    }


@app.get("/api/celery/status")
async def get_celery_status():
    """
    Celery 상태 조회
    
    Worker 연결 상태, 큐 정보 등을 반환합니다.
    """
    if not CELERY_AVAILABLE:
        return {"status": "disabled", "message": "Celery 서비스가 비활성화되어 있습니다."}
    
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
            "worker_stats": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


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
            "rag_processing"
        ]
        
        queue_info = {}
        for queue in queues:
            queue_info[queue] = r.llen(queue)
        
        return {
            "queues": queue_info,
            "total_pending": sum(queue_info.values())
        }
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
            "message": "면접 완료 워크플로우가 시작되지 않았습니다."
        }
    
    if not CELERY_AVAILABLE:
        return {
            "session_id": session_id,
            "workflow_status": "celery_unavailable",
            "message": "Celery 서비스를 사용할 수 없습니다."
        }
    
    try:
        from celery.result import AsyncResult
        result = AsyncResult(workflow_task_id, app=celery_app)
        
        response = {
            "session_id": session_id,
            "workflow_task_id": workflow_task_id,
            "workflow_status": result.status,
            "started_at": session.get("completion_started_at")
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
        return {
            "session_id": session_id,
            "workflow_status": "error",
            "error": str(e)
        }


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
        "pending_tasks": len(state.get_session(session_id).get("pending_eval_tasks", []))
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
            "task_id": session.get("completion_workflow_task_id")
        }
    
    task_id = await interviewer.start_interview_completion_workflow(session_id)
    
    if task_id:
        return {
            "session_id": session_id,
            "status": "started",
            "task_id": task_id
        }
    else:
        return {
            "session_id": session_id,
            "status": "failed",
            "message": "워크플로우 시작에 실패했습니다."
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
    print(f"  • 비동기 처리 (ThreadPoolExecutor):")
    print(f"    - LLM Executor: 4 workers (질문 생성, 평가)")
    print(f"    - RAG Executor: 2 workers (이력서 검색)")
    print(f"    - Vision Executor: 2 workers (감정 분석)")
    print(f"  • Celery 백그라운드 작업:")
    print(f"    - llm_evaluation: 답변 평가 (배치)")
    print(f"    - emotion_analysis: 감정 분석 (배치)")
    print(f"    - report_generation: 리포트 생성")
    print(f"    - tts_generation: TTS 프리페칭")
    print(f"    - rag_processing: 이력서 인덱싱")
    print(f"  • 서비스 상태:")
    print(f"    - LLM: {'✅ 활성화' if LLM_AVAILABLE else '❌ 비활성화'}")
    print(f"    - TTS: {'✅ 활성화' if TTS_AVAILABLE else '❌ 비활성화'}")
    print(f"    - RAG: {'✅ 활성화' if RAG_AVAILABLE else '❌ 비활성화'}")
    print(f"    - 감정분석: {'✅ 활성화' if EMOTION_AVAILABLE else '❌ 비활성화'}")
    print(f"    - Redis: {'✅ 활성화' if REDIS_AVAILABLE else '❌ 비활성화'}")
    print(f"    - Celery: {'✅ 활성화' if CELERY_AVAILABLE else '❌ 비활성화'}")
    _rec_tool = MEDIA_TOOL.upper() if RECORDING_AVAILABLE else "미설치"
    print(f"    - 녹화: {'✅ ' + _rec_tool if RECORDING_AVAILABLE else '❌ 비활성화 (GStreamer/FFmpeg 필요)'}")
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
            "ssl_keyfile": os.getenv("TLS_KEYFILE", "")
        }
        print("  🔒 TLS 활성화 (HTTPS)")
    else:
        protocol = "http"
        ssl_kwargs = {}
        print("  ⚠️ TLS 비활성화 (HTTP) — 프로덕션에서는 TLS_CERTFILE/TLS_KEYFILE 설정 권장")
    
    # Next.js 개발 서버 자동 시작
    import atexit, signal
    
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
            print(f"  ✅ Next.js 서버 시작됨 (PID: {_nextjs_process.pid}, {NEXTJS_URL})")
        except Exception as e:
            print(f"  ⚠️ Next.js 서버 자동 시작 실패: {e}")
            print(f"     수동 시작: cd CSH/frontend && npm run dev")
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
