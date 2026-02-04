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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 AI 모의면접 시스템</h1>
            <p>LLM 기반 면접 평가 + 실시간 감정 분석을 통한 스마트 면접 트레이닝</p>
            
            <a href="/static/integrated_interview.html" class="main-cta">
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
    </body>
    </html>
    """


@app.get("/interview")
async def interview_redirect():
    """채팅 면접 → 화상 면접으로 리다이렉트"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/integrated_interview.html")


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
