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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil

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
        complete_interview_workflow_task
    )
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
    print("✅ Celery 비동기 작업 서비스 활성화됨")
except ImportError as e:
    CELERY_AVAILABLE = False
    print(f"⚠️ Celery 서비스 비활성화: {e}")


# ========== 전역 상태 관리 ==========

# 회원 정보 저장소 (실제 운영에서는 DB 사용)
users_db: Dict[str, Dict] = {}

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
            "interview_mode": "text",  # text, voice, video
            "resume_uploaded": False,
            "resume_path": None,
            "resume_filename": None,
            "retriever": None  # 세션별 RAG retriever
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
    """AI 면접관 - 질문 은행 기반 질문 + LLM 기반 답변 분석/평가"""
    
    # LLM 분석용 프롬프트 (질문 생성이 아닌 답변 평가용)
    EVALUATION_PROMPT = """당신은 IT 기업의 30년차 수석 개발자 면접관입니다.
지원자의 답변을 분석하고 평가해주세요.

[평가 기준]
1. 구체성 (1-5점): 답변이 구체적인 사례와 수치를 포함하는가?
2. 논리성 (1-5점): 답변의 논리적 흐름이 일관성 있는가?
3. 기술 이해도 (1-5점): 기술적 개념에 대한 이해가 정확한가?
4. STAR 기법 (1-5점): 상황-과제-행동-결과 구조로 답변했는가?
5. 전달력 (1-5점): 답변이 명확하고 이해하기 쉬운가?

[출력 형식 - 반드시 JSON으로 응답]
{{
    "scores": {{
        "specificity": 숫자,
        "logic": 숫자,
        "technical": 숫자,
        "star": 숫자,
        "communication": 숫자
    }},
    "total_score": 숫자(25점 만점),
    "strengths": ["강점1", "강점2"],
    "improvements": ["개선점1", "개선점2"],
    "brief_feedback": "한 줄 피드백"
}}"""

    # 질문 은행 - 카테고리별 질문 목록
    QUESTION_BANK = {
        "intro": [
            "안녕하세요. 오늘 면접을 진행하게 된 면접관입니다. 먼저 간단한 자기소개를 부탁드립니다.",
        ],
        "motivation": [
            "지원하신 포지션에 관심을 갖게 된 계기가 무엇인가요?",
            "우리 회사에 지원하게 된 이유를 말씀해주세요.",
        ],
        "strength": [
            "본인의 가장 큰 기술적 강점은 무엇이라고 생각하시나요?",
            "다른 지원자와 비교했을 때 본인만의 차별점은 무엇인가요?",
        ],
        "project": [
            "가장 도전적이었던 프로젝트 경험에 대해 말씀해주세요.",
            "최근에 진행한 프로젝트에서 맡았던 역할과 기여도를 설명해주세요.",
            "프로젝트 진행 중 가장 어려웠던 기술적 문제와 해결 과정을 설명해주세요.",
        ],
        "teamwork": [
            "팀 프로젝트에서 갈등이 발생했을 때 어떻게 해결하셨나요?",
            "팀원과의 협업 경험 중 가장 기억에 남는 것은 무엇인가요?",
        ],
        "technical": [
            "사용하시는 주요 기술 스택에 대해 설명해주세요.",
            "최근에 학습하고 있는 기술이 있다면 무엇인가요?",
            "코드 품질을 위해 어떤 노력을 하시나요?",
        ],
        "problem_solving": [
            "예상치 못한 버그나 장애가 발생했을 때 어떻게 대처하시나요?",
            "기술적으로 가장 어려웠던 문제와 해결 방법을 설명해주세요.",
        ],
        "growth": [
            "앞으로의 커리어 목표는 무엇인가요?",
            "5년 후 어떤 개발자가 되어있을 것 같나요?",
        ],
        "closing": [
            "마지막으로 저희 회사에 궁금한 점이 있으신가요?",
        ]
    }
    
    # 면접 진행 순서
    INTERVIEW_FLOW = ["intro", "motivation", "strength", "project", "teamwork", 
                       "technical", "problem_solving", "growth", "closing"]

    def __init__(self):
        self.llm = None
        self.rag = None
        self.retriever = None
        self.tts_service = None
        
        self._init_services()
    
    def _init_services(self):
        """서비스 초기화"""
        # LLM 초기화 (평가/분석용)
        if LLM_AVAILABLE:
            try:
                self.llm = ChatOllama(
                    model=DEFAULT_LLM_MODEL, 
                    temperature=0.3  # 평가는 낮은 temperature
                )
                print(f"✅ LLM 초기화 완료 (평가용): {DEFAULT_LLM_MODEL}")
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
        return self.QUESTION_BANK["intro"][0]
    
    def get_next_question(self, session_id: str) -> str:
        """질문 은행에서 다음 질문 가져오기"""
        session = state.get_session(session_id)
        if not session:
            return self.get_initial_greeting()
        
        current_idx = session.get("current_question_idx", 0)
        flow_idx = session.get("flow_idx", 0)
        
        # 면접 순서에 따라 질문 선택
        if flow_idx >= len(self.INTERVIEW_FLOW):
            return "면접이 종료되었습니다. 수고하셨습니다. 리포트 버튼을 눌러 결과를 확인해보세요."
        
        category = self.INTERVIEW_FLOW[flow_idx]
        questions = self.QUESTION_BANK.get(category, [])
        
        if not questions:
            return "다음 질문을 준비 중입니다..."
        
        # 해당 카테고리에서 질문 선택 (순환)
        question = questions[current_idx % len(questions)]
        
        # 다음 카테고리로 이동
        state.update_session(session_id, {
            "flow_idx": flow_idx + 1,
            "current_question_idx": 0,
            "current_category": category
        })
        
        return question
    
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
            # RAG 컨텍스트 가져오기
            session = state.get_session(session_id)
            resume_context = ""
            if session:
                session_retriever = session.get("retriever") or self.retriever
                if session_retriever:
                    try:
                        docs = session_retriever.invoke(answer)
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
            
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # JSON 파싱 시도
            import json
            # JSON 블록 추출
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                evaluation = json.loads(json_match.group())
                return evaluation
            else:
                raise ValueError("JSON 형식 응답 없음")
                
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
        """사용자 답변을 저장하고 다음 질문 반환 (질문 은행 기반)"""
        session = state.get_session(session_id)
        if not session:
            return "세션을 찾을 수 없습니다."
        
        # 대화 기록 업데이트
        chat_history = session.get("chat_history", [])
        evaluations = session.get("evaluations", [])
        
        # 현재 질문 저장 (마지막 AI 메시지)
        last_question = ""
        for msg in reversed(chat_history):
            if msg["role"] == "assistant":
                last_question = msg["content"]
                break
        
        # 사용자 답변 저장
        chat_history.append({"role": "user", "content": user_input})
        
        # 다음 질문 가져오기
        next_question = self.get_next_question(session_id)
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


# ========== 회원가입 모델 ==========
class UserRegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    birth_date: str  # YYYY-MM-DD 형식
    address: str
    gender: str  # male, female, other

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
                max-width: 800px;
            }
            h1 {
                font-size: 48px;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 20px;
            }
            p { color: #8892b0; margin-bottom: 40px; font-size: 18px; }
            .main-cta {
                display: block;
                background: linear-gradient(135deg, #00d9ff, #00ff88);
                color: #1a1a2e;
                text-decoration: none;
                font-size: 24px;
                font-weight: 700;
                padding: 24px 48px;
                border-radius: 16px;
                margin-bottom: 40px;
                transition: all 0.3s;
                box-shadow: 0 10px 40px rgba(0,217,255,0.3);
            }
            .main-cta:hover {
                transform: translateY(-5px);
                box-shadow: 0 20px 60px rgba(0,217,255,0.4);
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 30px;
            }
            .feature {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 20px;
            }
            .feature .icon { font-size: 32px; margin-bottom: 10px; }
            .feature h4 { font-size: 14px; margin-bottom: 5px; }
            .feature p { font-size: 12px; color: #8892b0; margin: 0; }
            .sub-links {
                display: flex;
                gap: 16px;
                justify-content: center;
                margin-top: 30px;
            }
            .sub-link {
                color: #8892b0;
                text-decoration: none;
                font-size: 14px;
                padding: 8px 16px;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                transition: all 0.3s;
            }
            .sub-link:hover { border-color: #00d9ff; color: #00d9ff; }
            .status { margin-top: 30px; font-size: 14px; color: #666; }
            .status span { color: #00ff88; }
            
            /* 회원가입/로그인 버튼 */
            .auth-buttons {
                display: flex;
                gap: 12px;
                justify-content: center;
                margin-bottom: 30px;
            }
            .auth-btn {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                color: #fff;
                padding: 12px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s;
            }
            .auth-btn:hover {
                background: rgba(255,255,255,0.2);
                border-color: #00d9ff;
            }
            .auth-btn.primary {
                background: linear-gradient(135deg, #00d9ff, #00ff88);
                color: #1a1a2e;
                border: none;
                font-weight: 600;
            }
            
            /* 모달 스타일 */
            .modal-overlay {
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.8);
                z-index: 1000;
                align-items: center;
                justify-content: center;
            }
            .modal-overlay.active { display: flex; }
            .modal {
                background: #1a1a2e;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 16px;
                padding: 32px;
                width: 100%;
                max-width: 450px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            }
            .modal h2 {
                font-size: 24px;
                margin-bottom: 24px;
                text-align: center;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .form-group {
                margin-bottom: 16px;
            }
            .form-group label {
                display: block;
                margin-bottom: 6px;
                color: #8892b0;
                font-size: 14px;
            }
            .form-group input, .form-group select {
                width: 100%;
                padding: 12px 16px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                color: #fff;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            .form-group input:focus, .form-group select:focus {
                outline: none;
                border-color: #00d9ff;
            }
            .form-group select option {
                background: #1a1a2e;
                color: #fff;
            }
            .modal-buttons {
                display: flex;
                gap: 12px;
                margin-top: 24px;
            }
            .modal-btn {
                flex: 1;
                padding: 14px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                transition: all 0.3s;
                border: none;
            }
            .modal-btn.cancel {
                background: rgba(255,255,255,0.1);
                color: #8892b0;
            }
            .modal-btn.submit {
                background: linear-gradient(135deg, #00d9ff, #00ff88);
                color: #1a1a2e;
                font-weight: 600;
            }
            .modal-btn:hover { transform: translateY(-2px); }
            
            /* 소셜 로그인 버튼 */
            .social-login {
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.1);
            }
            .social-login p {
                text-align: center;
                color: #8892b0;
                font-size: 14px;
                margin-bottom: 12px;
            }
            .social-buttons {
                display: flex;
                gap: 10px;
                justify-content: center;
            }
            .social-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 12px 20px;
                border-radius: 8px;
                border: none;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: all 0.3s;
                flex: 1;
                max-width: 120px;
            }
            .social-btn:hover { transform: translateY(-2px); opacity: 0.9; }
            .social-btn.kakao {
                background: #FEE500;
                color: #000;
            }
            .social-btn.google {
                background: #fff;
                color: #333;
            }
            .social-btn.naver {
                background: #03C75A;
                color: #fff;
            }
            .social-btn svg {
                width: 18px;
                height: 18px;
            }
            
            .user-info {
                background: rgba(0,255,136,0.1);
                border: 1px solid rgba(0,255,136,0.3);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 20px;
                display: none;
            }
            .user-info.active { display: block; }
            .user-info span { color: #00ff88; font-weight: 600; }
            .error-msg {
                color: #ff6b6b;
                font-size: 14px;
                margin-top: 8px;
                display: none;
            }
            .error-msg.active { display: block; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 AI 모의면접 시스템</h1>
            <p>LLM 기반 면접 평가 + 실시간 감정 분석을 통한 스마트 면접 트레이닝</p>
            
            <!-- 사용자 정보 표시 -->
            <div class="user-info" id="userInfo">
                👋 환영합니다, <span id="userName"></span>님!
            </div>
            
            <!-- 회원가입/로그인 버튼 -->
            <div class="auth-buttons" id="authButtons">
                <button class="auth-btn" onclick="showLoginModal()">로그인</button>
                <button class="auth-btn primary" onclick="showRegisterModal()">회원가입</button>
            </div>
            
            <a href="/static/integrated_interview.html" class="main-cta" id="startBtn">
                🎥 AI 화상 면접 시작하기
            </a>
            
            <div class="features">
                <div class="feature">
                    <div class="icon">📄</div>
                    <h4>이력서 RAG</h4>
                    <p>이력서 기반 맞춤 질문</p>
                </div>
                <div class="feature">
                    <div class="icon">🎤</div>
                    <h4>TTS 음성</h4>
                    <p>자연스러운 AI 면접관</p>
                </div>
                <div class="feature">
                    <div class="icon">📊</div>
                    <h4>실시간 평가</h4>
                    <p>LLM 기반 답변 분석</p>
                </div>
                <div class="feature">
                    <div class="icon">😊</div>
                    <h4>감정 분석</h4>
                    <p>표정 기반 감정 측정</p>
                </div>
            </div>
            
            <div class="sub-links">
                <a href="/static/dashboard.html" class="sub-link">📊 감정 대시보드</a>
                <a href="/docs" class="sub-link">📚 API 문서</a>
            </div>
            
            <div class="status">
                서비스 상태: 
                <span>LLM """ + ("✅" if LLM_AVAILABLE else "❌") + """</span> | 
                <span>TTS """ + ("✅" if TTS_AVAILABLE else "❌") + """</span> | 
                <span>RAG """ + ("✅" if RAG_AVAILABLE else "❌") + """</span> | 
                <span>감정분석 """ + ("✅" if EMOTION_AVAILABLE else "❌") + """</span>
            </div>
        </div>
        
        <!-- 회원가입 모달 -->
        <div class="modal-overlay" id="registerModal">
            <div class="modal">
                <h2>📝 회원가입</h2>
                <form id="registerForm" onsubmit="handleRegister(event)">
                    <div class="form-group">
                        <label>이메일 *</label>
                        <input type="email" id="regEmail" placeholder="example@email.com" required>
                    </div>
                    <div class="form-group">
                        <label>비밀번호 *</label>
                        <input type="password" id="regPassword" placeholder="8자 이상 입력" minlength="8" required>
                    </div>
                    <div class="form-group">
                        <label>비밀번호 확인 *</label>
                        <input type="password" id="regPasswordConfirm" placeholder="비밀번호 재입력" required>
                    </div>
                    <div class="form-group">
                        <label>이름 *</label>
                        <input type="text" id="regName" placeholder="홍길동" required>
                    </div>
                    <div class="form-group">
                        <label>생년월일 *</label>
                        <input type="date" id="regBirthDate" required>
                    </div>
                    <div class="form-group">
                        <label>주소 *</label>
                        <input type="text" id="regAddress" placeholder="서울시 강남구..." required>
                    </div>
                    <div class="form-group">
                        <label>성별 *</label>
                        <select id="regGender" required>
                            <option value="">선택해주세요</option>
                            <option value="male">남성</option>
                            <option value="female">여성</option>
                            <option value="other">기타</option>
                        </select>
                    </div>
                    <div class="error-msg" id="registerError"></div>
                    <div class="modal-buttons">
                        <button type="button" class="modal-btn cancel" onclick="closeModals()">취소</button>
                        <button type="submit" class="modal-btn submit">가입하기</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- 로그인 모달 -->
        <div class="modal-overlay" id="loginModal">
            <div class="modal">
                <h2>🔐 로그인</h2>
                <form id="loginForm" onsubmit="handleLogin(event)">
                    <div class="form-group">
                        <label>이메일</label>
                        <input type="email" id="loginEmail" placeholder="example@email.com" required>
                    </div>
                    <div class="form-group">
                        <label>비밀번호</label>
                        <input type="password" id="loginPassword" placeholder="비밀번호 입력" required>
                    </div>
                    <div class="error-msg" id="loginError"></div>
                    <div class="modal-buttons">
                        <button type="button" class="modal-btn cancel" onclick="closeModals()">취소</button>
                        <button type="submit" class="modal-btn submit">로그인</button>
                    </div>
                </form>
                
                <!-- 소셜 로그인 -->
                <div class="social-login">
                    <p>간편 로그인</p>
                    <div class="social-buttons">
                        <button class="social-btn kakao" onclick="socialLogin('kakao')">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.48 3 2 6.58 2 11c0 2.83 1.89 5.31 4.7 6.71l-.96 3.57c-.09.35.27.65.58.48l4.24-2.54c.47.05.95.08 1.44.08 5.52 0 10-3.58 10-8S17.52 3 12 3z"/></svg>
                            카카오
                        </button>
                        <button class="social-btn google" onclick="socialLogin('google')">
                            <svg viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                            구글
                        </button>
                        <button class="social-btn naver" onclick="socialLogin('naver')">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.273 12.845L7.376 0H0v24h7.727V11.155L16.624 24H24V0h-7.727z"/></svg>
                            네이버
                        </button>
                    </div>
                </div>
                
                <p style="text-align: center; margin-top: 16px; color: #8892b0; font-size: 14px;">
                    계정이 없으신가요? <a href="#" onclick="showRegisterModal()" style="color: #00d9ff;">회원가입</a>
                </p>
            </div>
        </div>
        
        <script>
            // 현재 로그인된 사용자
            let currentUser = null;
            
            // 페이지 로드 시 세션 확인
            window.onload = function() {
                const savedUser = localStorage.getItem('interview_user');
                if (savedUser) {
                    currentUser = JSON.parse(savedUser);
                    updateUIForLoggedInUser();
                }
            };
            
            function showRegisterModal() {
                closeModals();
                document.getElementById('registerModal').classList.add('active');
            }
            
            function showLoginModal() {
                closeModals();
                document.getElementById('loginModal').classList.add('active');
            }
            
            function closeModals() {
                document.getElementById('registerModal').classList.remove('active');
                document.getElementById('loginModal').classList.remove('active');
                document.getElementById('registerError').classList.remove('active');
                document.getElementById('loginError').classList.remove('active');
            }
            
            async function handleRegister(e) {
                e.preventDefault();
                const errorEl = document.getElementById('registerError');
                
                const password = document.getElementById('regPassword').value;
                const passwordConfirm = document.getElementById('regPasswordConfirm').value;
                
                // 비밀번호 확인
                if (password !== passwordConfirm) {
                    errorEl.textContent = '비밀번호가 일치하지 않습니다.';
                    errorEl.classList.add('active');
                    return;
                }
                
                if (password.length < 8) {
                    errorEl.textContent = '비밀번호는 8자 이상이어야 합니다.';
                    errorEl.classList.add('active');
                    return;
                }
                
                const data = {
                    email: document.getElementById('regEmail').value,
                    password: password,
                    name: document.getElementById('regName').value,
                    birth_date: document.getElementById('regBirthDate').value,
                    address: document.getElementById('regAddress').value,
                    gender: document.getElementById('regGender').value
                };
                
                try {
                    const response = await fetch('/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('회원가입이 완료되었습니다! 로그인해주세요.');
                        closeModals();
                        showLoginModal();
                        document.getElementById('loginEmail').value = data.email;
                    } else {
                        errorEl.textContent = result.message;
                        errorEl.classList.add('active');
                    }
                } catch (err) {
                    errorEl.textContent = '서버 오류가 발생했습니다.';
                    errorEl.classList.add('active');
                }
            }
            
            async function handleLogin(e) {
                e.preventDefault();
                const errorEl = document.getElementById('loginError');
                const email = document.getElementById('loginEmail').value;
                const password = document.getElementById('loginPassword').value;
                
                try {
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        currentUser = result.user;
                        localStorage.setItem('interview_user', JSON.stringify(currentUser));
                        closeModals();
                        updateUIForLoggedInUser();
                    } else {
                        errorEl.textContent = result.message;
                        errorEl.classList.add('active');
                    }
                } catch (err) {
                    errorEl.textContent = '서버 오류가 발생했습니다.';
                    errorEl.classList.add('active');
                }
            }
            
            function updateUIForLoggedInUser() {
                document.getElementById('authButtons').style.display = 'none';
                document.getElementById('userInfo').classList.add('active');
                document.getElementById('userName').textContent = currentUser.name;
            }
            
            function logout() {
                currentUser = null;
                localStorage.removeItem('interview_user');
                document.getElementById('authButtons').style.display = 'flex';
                document.getElementById('userInfo').classList.remove('active');
            }
            
            // 소셜 로그인
            function socialLogin(provider) {
                // 소셜 로그인 URL로 리다이렉트
                window.location.href = `/api/auth/social/${provider}`;
            }
            
            // OAuth 콜백 처리 (URL에 토큰이 있으면)
            function handleOAuthCallback() {
                const urlParams = new URLSearchParams(window.location.search);
                const token = urlParams.get('token');
                const error = urlParams.get('error');
                
                if (error) {
                    alert('소셜 로그인 실패: ' + error);
                    window.history.replaceState({}, '', '/');
                    return;
                }
                
                if (token) {
                    // 토큰으로 사용자 정보 가져오기
                    fetch('/api/auth/social/verify?token=' + token)
                        .then(res => res.json())
                        .then(result => {
                            if (result.success) {
                                currentUser = result.user;
                                localStorage.setItem('interview_user', JSON.stringify(currentUser));
                                updateUIForLoggedInUser();
                            }
                            window.history.replaceState({}, '', '/');
                        })
                        .catch(err => {
                            console.error('소셜 로그인 검증 실패:', err);
                            window.history.replaceState({}, '', '/');
                        });
                }
            }
            
            // 페이지 로드 시 OAuth 콜백 확인
            handleOAuthCallback();
            
            // 모달 외부 클릭 시 닫기
            document.querySelectorAll('.modal-overlay').forEach(modal => {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) closeModals();
                });
            });
        </script>
    </body>
    </html>
    """


@app.get("/interview")
async def interview_redirect():
    """채팅 면접 → 화상 면접으로 리다이렉트"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/integrated_interview.html")


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
            
            # 사용자 등록 또는 조회
            if email not in users_db:
                user_id = uuid.uuid4().hex
                users_db[email] = {
                    "user_id": user_id,
                    "email": email,
                    "password_hash": None,  # 소셜 로그인은 비밀번호 없음
                    "name": name,
                    "birth_date": None,
                    "address": None,
                    "gender": None,
                    "provider": provider,
                    "created_at": datetime.now().isoformat(),
                    "interview_history": []
                }
                print(f"✅ 소셜 회원 가입: {name} ({email}) via {provider}")
            else:
                user_id = users_db[email]["user_id"]
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
    
    user = users_db.get(token_data["email"])
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

@app.post("/api/auth/register", response_model=UserRegisterResponse)
async def register_user(request: UserRegisterRequest):
    """회원가입 API"""
    # 이메일 중복 확인
    if request.email in users_db:
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
    if request.gender not in ["male", "female", "other"]:
        return UserRegisterResponse(
            success=False,
            message="성별을 선택해주세요."
        )
    
    # 비밀번호 검증
    if len(request.password) < 8:
        return UserRegisterResponse(
            success=False,
            message="비밀번호는 8자 이상이어야 합니다."
        )
    
    # 비밀번호 해싱 (간단한 해시 사용, 실제 운영에서는 bcrypt 권장)
    import hashlib
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    
    # 회원 정보 저장
    user_id = uuid.uuid4().hex
    users_db[request.email] = {
        "user_id": user_id,
        "email": request.email,
        "password_hash": password_hash,
        "name": request.name,
        "birth_date": request.birth_date,
        "address": request.address,
        "gender": request.gender,
        "created_at": datetime.now().isoformat(),
        "interview_history": []
    }
    
    print(f"✅ 새 회원 가입: {request.name} ({request.email})")
    
    return UserRegisterResponse(
        success=True,
        message="회원가입이 완료되었습니다.",
        user_id=user_id
    )


@app.post("/api/auth/login", response_model=UserLoginResponse)
async def login_user(request: UserLoginRequest):
    """로그인 API (이메일 + 비밀번호)"""
    user = users_db.get(request.email)
    
    if not user:
        return UserLoginResponse(
            success=False,
            message="등록되지 않은 이메일입니다. 회원가입을 먼저 해주세요."
        )
    
    # 비밀번호 검증
    import hashlib
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if user.get("password_hash") != password_hash:
        return UserLoginResponse(
            success=False,
            message="비밀번호가 올바르지 않습니다."
        )
    
    # 민감 정보 제외하고 반환
    user_info = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "gender": user["gender"]
    }
    
    print(f"✅ 로그인: {user['name']} ({user['email']})")
    
    return UserLoginResponse(
        success=True,
        message="로그인 성공",
        user=user_info
    )


@app.get("/api/auth/user/{email}")
async def get_user_info(email: str):
    """회원 정보 조회"""
    user = users_db.get(email)
    
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
    session_id: Optional[str] = Form(None)
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
            # 세션별 고유 컬렉션 이름 사용
            collection_name = f"resume_{session_id[:16]}"
            connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
            
            if connection_string:
                # 새 RAG 인스턴스 생성 (세션별)
                session_rag = ResumeRAG(
                    connection_string=connection_string,
                    collection_name=collection_name
                )
                
                # PDF 인덱싱
                print(f"📚 이력서 인덱싱 시작: {file_path}")
                session_rag.load_and_index_pdf(file_path)
                
                # 세션에 retriever 저장
                retriever = session_rag.get_retriever()
                state.update_session(session_id, {
                    "resume_uploaded": True,
                    "resume_path": file_path,
                    "resume_filename": file.filename,
                    "retriever": retriever
                })
                
                # 청크 수 추정 (로그에서 가져올 수 없으므로 대략적으로)
                chunks_created = 1  # 최소 1개 이상
                print(f"✅ RAG 인덱싱 완료: {collection_name}")
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
async def delete_resume(session_id: str):
    """세션의 이력서 삭제"""
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
    
    return report


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
async def evaluate_answer(request: EvaluateRequest):
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
async def get_evaluations(session_id: str):
    """세션의 모든 평가 결과 조회"""
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
            "redis": REDIS_AVAILABLE,
            "celery": CELERY_AVAILABLE
        },
        "active_sessions": len(state.sessions),
        "active_connections": len(state.pcs),
        "celery_status": check_celery_status() if CELERY_AVAILABLE else {"status": "disabled"}
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
async def async_evaluate_answer(request: AsyncTaskRequest):
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
async def async_batch_evaluate(request: Request):
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
async def async_emotion_analysis(request: Request):
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
async def async_generate_report(session_id: str):
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
async def async_complete_interview(request: Request):
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
    print(f"    - Celery: {'✅ 활성화' if CELERY_AVAILABLE else '❌ 비활성화'}")
    print("=" * 60)
    print("  📋 Celery Worker 시작 명령어:")
    print("     celery -A celery_app worker --pool=solo --loglevel=info")
    print("=" * 60)
    print("  🌐 http://localhost:8000 에서 접속하세요")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
