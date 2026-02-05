# FastAPI
import os
import uuid
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from interview_core import InterviewEngine

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Simulator Interview API",
    description="텍스트 기반 AI 모의면접 엔진",
    version="0.8.1",
    swagger_ui_parameters={
        "docExpansion": "none",      # 펼침 최소화
        "defaultModelsExpandDepth": -1,  # Schemas 숨기기
        "displayRequestDuration": True,  # 응답 시간 표시
        "filter": True,                  # 검색창 활성화
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 아주 간단한 메모리 세션 저장(데모용)
SESSIONS: Dict[str, Dict] = {}


class StartRequest(BaseModel):
    first_question: str
    use_llm: Optional[bool] = False  # True면 (키 있을 때) LLM next_question 사용


class StartResponse(BaseModel):
    session_id: str
    question: str
    turn: int
    debug: Dict


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class AnswerResponse(BaseModel):
    question: str
    turn: int
    debug: Dict


@app.get("/health")
def health():
    return {
        "ok": True,
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }


@app.post("/start", response_model=StartResponse)
def start(req: StartRequest):
    session_id = str(uuid.uuid4())
    engine = InterviewEngine(use_llm=bool(req.use_llm))

    q1 = engine.start(req.first_question)
    t1 = engine.add_question(q1)

    SESSIONS[session_id] = {"engine": engine}

    return StartResponse(
        session_id=session_id,
        question=t1.question,
        turn=t1.turn,
        debug={"q_type": t1.q_type, "use_llm_requested": bool(req.use_llm), "llm_active": engine.llm is not None},
    )


@app.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session_id. Call /start first.")

    engine: InterviewEngine = session["engine"]

    # 마지막 질문(현재 턴)에 사용자 답 저장
    engine.turns[-1].user_answer = req.answer

    # 다음 질문 생성
    next_q, debug = engine.step(req.answer)

    # 다음 질문을 새 턴으로 추가
    t_next = engine.add_question(next_q)

    return AnswerResponse(
        question=t_next.question,
        turn=t_next.turn,
        debug={"q_type": t_next.q_type, **debug},
    )
