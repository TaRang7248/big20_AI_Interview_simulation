"""
AI 모의면접 통합 시스템
========================
기능 통합:
1. LLM 기반 면접 질문 생성 (Ollama/Llama3)
2. TTS 서비스 (Hume AI)
3. STT 서비스 (Deepgram)
4. 화상 면접 + 감정 분석 (DeepFace + WebRTC)
5. 이력서 RAG (PostgreSQL + PGVector)
6. STAR 기법 기반 리포트 생성

실행 방법:
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

# FastAPI 및 웹 프레임워크
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# WebRTC
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole

# 환경 설정
from dotenv import load_dotenv

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)
sys.path.append(current_dir)

load_dotenv()

# ========== 설정 ==========
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
DEFAULT_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ========== FastAPI 앱 초기화 ==========
app = FastAPI(
    title="AI 모의면접 통합 시스템",
    description="TTS, STT, LLM, 화상 면접, 감정 분석을 통합한 AI 면접 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 마운트
static_dir = os.path.join(current_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
    from resume_rag import ResumeRAG
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


# ========== 전역 상태 관리 ==========
class InterviewState:
    """면접 세션 상태 관리"""
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.pcs: Set[RTCPeerConnection] = set()
        self.pc_sessions: Dict[RTCPeerConnection, str] = {}
        self.last_emotion: Optional[Dict] = None
        self.emotion_lock = asyncio.Lock()
        
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
            "interview_mode": "text"  # text, voice, video
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, data: Dict):
        if session_id in self.sessions:
            self.sessions[session_id].update(data)

state = InterviewState()


# ========== LLM 면접관 서비스 ==========
class AIInterviewer:
    """AI 면접관 - LLM 기반 질문 생성 및 대화 관리"""
    
    SYSTEM_PROMPT = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 이력서 내용과 답변을 바탕으로 기술 스택과 경험에 대해 심도 있는 질문을 던지세요.
제공된 '참고용 이력서 내용'을 적극 활용하여 구체적인 질문을 하세요.

[중요 규칙]
1. 답변이 부실하면 구체적인 예시를 요구하거나 꼬리 질문을 하세요.
2. 꼬리 질문은 주제당 최대 2번까지만 허용합니다. 
3. 동일한 기술적 주제에 대해 2번의 답변을 들었다면, "알겠습니다. 다음은..."이라며 주제를 전환하세요.
4. 질문은 한 번에 하나만 하세요.
5. 응답은 100자 내외로 간결하게 작성하세요.

질문을 할 때 너무 공격적이지 않게, 정중하지만 날카로운 태도를 유지하세요."""

    DEFAULT_QUESTIONS = [
        "안녕하세요. 오늘 면접을 진행하게 된 면접관입니다. 먼저 간단한 자기소개를 부탁드립니다.",
        "지원하신 포지션에 관심을 갖게 된 계기가 무엇인가요?",
        "본인의 가장 큰 기술적 강점은 무엇이라고 생각하시나요?",
        "가장 도전적이었던 프로젝트 경험에 대해 말씀해주세요.",
        "팀 프로젝트에서 갈등이 발생했을 때 어떻게 해결하셨나요?",
        "앞으로의 커리어 목표는 무엇인가요?",
        "마지막으로 저희 회사에 궁금한 점이 있으신가요?"
    ]

    def __init__(self):
        self.llm = None
        self.rag = None
        self.retriever = None
        self.tts_service = None
        
        self._init_services()
    
    def _init_services(self):
        """서비스 초기화"""
        # LLM 초기화
        if LLM_AVAILABLE:
            try:
                self.llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL, 
                    temperature=DEFAULT_LLM_TEMPERATURE
                )
                print(f"✅ LLM 초기화 완료: {DEFAULT_LLM_MODEL}")
            except Exception as e:
                print(f"❌ LLM 초기화 실패: {e}")
        
        # RAG 초기화
        if RAG_AVAILABLE:
            try:
                connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
                if connection_string:
                    self.rag = ResumeRAG(connection_string=connection_string)
                    self.retriever = self.rag.get_retriever()
                    print("✅ RAG 초기화 완료")
            except Exception as e:
                print(f"⚠️ RAG 초기화 실패: {e}")
        
        # TTS 초기화
        if TTS_AVAILABLE:
            try:
                self.tts_service = HumeInterviewerVoice()
                print("✅ TTS 초기화 완료")
            except Exception as e:
                print(f"⚠️ TTS 초기화 실패: {e}")
    
    def get_initial_greeting(self) -> str:
        """초기 인사말 반환"""
        return self.DEFAULT_QUESTIONS[0]
    
    async def generate_response(
        self, 
        session_id: str, 
        user_input: str,
        use_rag: bool = True
    ) -> str:
        """사용자 입력에 대한 AI 응답 생성"""
        session = state.get_session(session_id)
        if not session:
            return "세션을 찾을 수 없습니다."
        
        # LLM이 없으면 기본 질문 순환
        if not self.llm:
            idx = session.get("current_question_idx", 0)
            next_idx = (idx + 1) % len(self.DEFAULT_QUESTIONS)
            state.update_session(session_id, {"current_question_idx": next_idx})
            return self.DEFAULT_QUESTIONS[next_idx]
        
        try:
            # 대화 기록 구성
            chat_history = session.get("chat_history", [])
            messages = [SystemMessage(content=self.SYSTEM_PROMPT)]
            
            # 이전 대화 추가
            for msg in chat_history[-10:]:  # 최근 10개 메시지만
                if msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
                else:
                    messages.append(HumanMessage(content=msg["content"]))
            
            # 현재 사용자 입력 추가
            messages.append(HumanMessage(content=user_input))
            
            # RAG 컨텍스트 추가
            if use_rag and self.retriever:
                try:
                    retrieved_docs = self.retriever.invoke(user_input)
                    if retrieved_docs:
                        context_text = "\n".join([doc.page_content for doc in retrieved_docs])
                        context_msg = SystemMessage(
                            content=f"--- [RAG] 참고용 이력서 내용 ---\n{context_text}\n---"
                        )
                        messages.append(context_msg)
                except Exception as e:
                    print(f"RAG 검색 오류: {e}")
            
            # LLM 응답 생성
            response = self.llm.invoke(messages)
            ai_response = response.content
            
            # 대화 기록 업데이트
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": ai_response})
            state.update_session(session_id, {"chat_history": chat_history})
            
            return ai_response
            
        except Exception as e:
            print(f"LLM 응답 생성 오류: {e}")
            return "죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요."
    
    async def generate_speech(self, text: str) -> Optional[str]:
        """텍스트를 음성으로 변환"""
        if self.tts_service:
            try:
                return await self.tts_service.speak(text)
            except Exception as e:
                print(f"TTS 오류: {e}")
        return None


# AI 면접관 인스턴스
interviewer = AIInterviewer()


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
    """영상 프레임 감정 분석"""
    if not EMOTION_AVAILABLE:
        return
    
    sample_period = 1.0
    last_ts = 0.0
    
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
                res = DeepFace.analyze(img, actions=["emotion"], enforce_detection=False)
                item = res[0] if isinstance(res, list) else res
                scores = item.get("emotion", {})
                
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


# ========== API 엔드포인트 ==========

@app.get("/", response_class=HTMLResponse)
async def index():
    """메인 페이지"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <title>AI 모의면접 시스템</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                min-height: 100vh;
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                text-align: center;
                padding: 40px;
            }
            h1 {
                font-size: 48px;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 20px;
            }
            p { color: #8892b0; margin-bottom: 40px; font-size: 18px; }
            .links {
                display: flex;
                gap: 20px;
                justify-content: center;
                flex-wrap: wrap;
            }
            .link-card {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 16px;
                padding: 30px;
                width: 250px;
                text-decoration: none;
                color: #fff;
                transition: all 0.3s;
            }
            .link-card:hover {
                transform: translateY(-5px);
                border-color: #00d9ff;
                box-shadow: 0 10px 40px rgba(0,217,255,0.2);
            }
            .link-card h3 { margin-bottom: 10px; }
            .link-card p { font-size: 14px; color: #8892b0; margin: 0; }
            .status { margin-top: 40px; font-size: 14px; color: #666; }
            .status span { color: #00ff88; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 AI 모의면접 시스템</h1>
            <p>TTS, STT, LLM, 화상 면접, 감정 분석을 통합한 AI 면접 시스템</p>
            
            <div class="links">
                <a href="/static/video.html" class="link-card">
                    <h3>🎥 화상 면접</h3>
                    <p>WebRTC 기반 실시간 화상 면접 및 감정 분석</p>
                </a>
                <a href="/static/dashboard.html" class="link-card">
                    <h3>📊 감정 대시보드</h3>
                    <p>실시간 감정 분석 결과 시각화</p>
                </a>
                <a href="/docs" class="link-card">
                    <h3>📚 API 문서</h3>
                    <p>FastAPI Swagger 문서</p>
                </a>
                <a href="/interview" class="link-card">
                    <h3>💬 웹 채팅 면접</h3>
                    <p>텍스트 기반 AI 면접</p>
                </a>
            </div>
            
            <div class="status">
                서비스 상태: 
                <span>LLM """ + ("✅" if LLM_AVAILABLE else "❌") + """</span> | 
                <span>TTS """ + ("✅" if TTS_AVAILABLE else "❌") + """</span> | 
                <span>RAG """ + ("✅" if RAG_AVAILABLE else "❌") + """</span> | 
                <span>감정분석 """ + ("✅" if EMOTION_AVAILABLE else "❌") + """</span>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/interview", response_class=HTMLResponse)
async def interview_page():
    """웹 기반 텍스트 채팅 면접 페이지"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <title>AI 모의면접 - 채팅</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                min-height: 100vh;
                color: #fff;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            header {
                text-align: center;
                padding: 20px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            header h1 {
                font-size: 24px;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 20px 0;
            }
            .message {
                display: flex;
                margin-bottom: 16px;
                gap: 12px;
            }
            .message.user { flex-direction: row-reverse; }
            .avatar {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                flex-shrink: 0;
            }
            .message.ai .avatar { background: linear-gradient(135deg, #00d9ff, #00ff88); }
            .message.user .avatar { background: rgba(255,255,255,0.1); }
            .bubble {
                max-width: 70%;
                padding: 12px 16px;
                border-radius: 16px;
                line-height: 1.5;
            }
            .message.ai .bubble {
                background: rgba(0,217,255,0.1);
                border: 1px solid rgba(0,217,255,0.2);
            }
            .message.user .bubble {
                background: rgba(255,255,255,0.1);
            }
            .input-area {
                display: flex;
                gap: 12px;
                padding: 20px 0;
                border-top: 1px solid rgba(255,255,255,0.1);
            }
            #messageInput {
                flex: 1;
                padding: 14px 20px;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 25px;
                background: rgba(255,255,255,0.05);
                color: #fff;
                font-size: 16px;
            }
            #messageInput:focus {
                outline: none;
                border-color: #00d9ff;
            }
            #sendBtn {
                padding: 14px 30px;
                background: linear-gradient(135deg, #00d9ff, #00ff88);
                border: none;
                border-radius: 25px;
                color: #1a1a2e;
                font-weight: 600;
                cursor: pointer;
            }
            #sendBtn:hover { transform: scale(1.05); }
            #sendBtn:disabled { opacity: 0.5; cursor: not-allowed; }
            .typing { color: #888; font-style: italic; }
            .controls {
                display: flex;
                gap: 10px;
                margin-top: 10px;
                justify-content: center;
            }
            .controls button {
                padding: 8px 16px;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 8px;
                background: transparent;
                color: #fff;
                cursor: pointer;
            }
            .controls button:hover { background: rgba(255,255,255,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>💬 AI 모의면접 채팅</h1>
            </header>
            
            <div class="chat-container" id="chatContainer"></div>
            
            <div class="input-area">
                <input type="text" id="messageInput" placeholder="답변을 입력하세요..." />
                <button id="sendBtn">전송</button>
            </div>
            
            <div class="controls">
                <button onclick="startNewSession()">새 면접 시작</button>
                <button onclick="generateReport()">리포트 생성</button>
                <button onclick="location.href='/'">홈으로</button>
            </div>
        </div>
        
        <script>
            let sessionId = null;
            const chatContainer = document.getElementById('chatContainer');
            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            
            function addMessage(content, isUser = false) {
                const div = document.createElement('div');
                div.className = 'message ' + (isUser ? 'user' : 'ai');
                div.innerHTML = `
                    <div class="avatar">${isUser ? '👤' : '👔'}</div>
                    <div class="bubble">${content}</div>
                `;
                chatContainer.appendChild(div);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            async function startNewSession() {
                const resp = await fetch('/api/session', { method: 'POST' });
                const data = await resp.json();
                sessionId = data.session_id;
                chatContainer.innerHTML = '';
                addMessage(data.greeting);
            }
            
            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message || !sessionId) return;
                
                addMessage(message, true);
                messageInput.value = '';
                sendBtn.disabled = true;
                
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message ai typing';
                typingDiv.innerHTML = '<div class="avatar">👔</div><div class="bubble">생각 중...</div>';
                chatContainer.appendChild(typingDiv);
                
                try {
                    const resp = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: sessionId, message })
                    });
                    const data = await resp.json();
                    typingDiv.remove();
                    addMessage(data.response);
                } catch (e) {
                    typingDiv.remove();
                    addMessage('오류가 발생했습니다. 다시 시도해주세요.');
                }
                
                sendBtn.disabled = false;
            }
            
            async function generateReport() {
                if (!sessionId) { alert('면접을 먼저 시작해주세요.'); return; }
                
                const resp = await fetch(`/api/report/${sessionId}`);
                const report = await resp.json();
                
                let reportHtml = '<h3>📊 면접 리포트</h3>';
                reportHtml += `<p>총 답변: ${report.metrics.total}회</p>`;
                reportHtml += `<p>평균 길이: ${report.metrics.avg_length}자</p>`;
                reportHtml += '<h4>피드백:</h4><ul>';
                report.feedback.forEach(f => { reportHtml += `<li>${f}</li>`; });
                reportHtml += '</ul>';
                
                addMessage(reportHtml);
            }
            
            sendBtn.onclick = sendMessage;
            messageInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
            
            // 페이지 로드 시 세션 시작
            startNewSession();
        </script>
    </body>
    </html>
    """


# ========== Session API ==========

@app.post("/api/session")
async def create_session():
    """새 면접 세션 생성"""
    session_id = state.create_session()
    greeting = interviewer.get_initial_greeting()
    
    # 초기 인사 저장
    state.update_session(session_id, {
        "status": "active",
        "chat_history": [{"role": "assistant", "content": greeting}]
    })
    
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


# ========== Chat API ==========

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 메시지 전송 및 AI 응답 받기"""
    session = state.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # AI 응답 생성
    response = await interviewer.generate_response(
        request.session_id,
        request.message,
        request.use_rag
    )
    
    # TTS 생성 (선택적)
    audio_url = None
    if TTS_AVAILABLE and interviewer.tts_service:
        try:
            audio_file = await interviewer.generate_speech(response)
            if audio_file:
                audio_url = f"/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            print(f"TTS 생성 오류: {e}")
    
    return ChatResponse(
        session_id=request.session_id,
        response=response,
        audio_url=audio_url
    )


# ========== Report API ==========

@app.get("/api/report/{session_id}")
async def get_report(session_id: str):
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
    return report


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
                asyncio.create_task(analyze_emotions(track, session_id))
            else:
                bh = MediaBlackhole()
                asyncio.create_task(_consume_audio(track, bh))
        
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
    """오디오 트랙 소비"""
    try:
        while True:
            frame = await track.recv()
            sink.write(frame)
    except Exception:
        pass


# ========== Emotion API ==========

@app.get("/emotion")
async def get_emotion():
    """현재 감정 상태 조회"""
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
            "rag": RAG_AVAILABLE,
            "emotion": EMOTION_AVAILABLE,
            "redis": REDIS_AVAILABLE
        },
        "active_sessions": len(state.sessions),
        "active_connections": len(state.pcs)
    }


# ========== 서버 종료 처리 ==========

@app.on_event("shutdown")
async def on_shutdown():
    """서버 종료 시 정리"""
    coros = [pc.close() for pc in state.pcs]
    await asyncio.gather(*coros, return_exceptions=True)
    state.pcs.clear()


# ========== 메인 실행 ==========

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("🎯 AI 모의면접 통합 시스템")
    print("=" * 60)
    print(f"  • LLM 모델: {DEFAULT_LLM_MODEL}")
    print(f"  • 서비스 상태:")
    print(f"    - LLM: {'✅ 활성화' if LLM_AVAILABLE else '❌ 비활성화'}")
    print(f"    - TTS: {'✅ 활성화' if TTS_AVAILABLE else '❌ 비활성화'}")
    print(f"    - RAG: {'✅ 활성화' if RAG_AVAILABLE else '❌ 비활성화'}")
    print(f"    - 감정분석: {'✅ 활성화' if EMOTION_AVAILABLE else '❌ 비활성화'}")
    print(f"    - Redis: {'✅ 활성화' if REDIS_AVAILABLE else '❌ 비활성화'}")
    print("=" * 60)
    print("  🌐 http://localhost:8000 에서 접속하세요")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
