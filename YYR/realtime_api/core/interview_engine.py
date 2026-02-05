import os
import re
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from .models import Turn

# (선택) LLM import는 실패해도 돌아가게 처리
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
except Exception:
    ChatOpenAI = None
    HumanMessage = AIMessage = SystemMessage = None


def clean_text(s: str) -> str:
    s = s.replace("\u200b", "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def classify_question(q: str) -> str:
    if any(k in q for k in ["경험", "사례", "활동", "수행", "프로젝트", "갈등", "해결"]):
        return "experience"
    if any(k in q for k in ["역량", "강점", "준비", "노력", "개발", "전문성", "자기개발"]):
        return "competency"
    if any(k in q for k in ["지원", "동기", "포부", "계획", "비전", "성장", "목표"]):
        return "motivation"
    if any(k in q for k in ["직무", "역할", "특징", "정의", "중요성", "덕목"]):
        return "job_understanding"
    return "other"


FOLLOW_UP: Dict[str, str] = {
    "motivation": "좋아요. 그 동기를 뒷받침하는 구체적인 경험 한 가지를 말해줄 수 있나요?",
    "experience": "그 상황에서 본인이 맡은 역할과 결과를 조금 더 구체적으로 말해볼까요?",
    "competency": "그 역량을 보여준 사례를 하나 더 들어볼 수 있나요?",
    "job_understanding": "그 직무에서 성과를 판단하는 기준(지표)은 무엇이라고 생각하나요?",
    "other": "조금 더 구체적으로(상황-행동-결과) 순서로 말해볼까요?",
}


def rule_next_question(prev_q: str, prev_type: str, user_answer: str) -> str:
    ua = user_answer

    if prev_type == "job_understanding":
        if any(k in ua for k in ["수집", "정리", "구조화", "대안", "의사결정"]):
            return "좋아요. 그 역할을 잘 수행하기 위해 가장 중요한 역량은 무엇이라고 생각하나요?"
        return FOLLOW_UP["job_understanding"]

    if prev_type == "experience":
        if any(k in ua for k in ["결과", "성과", "개선", "%", "단축"]):
            return "그 결과를 만들기 위해 본인이 직접 한 핵심 행동은 무엇이었나요?"
        return FOLLOW_UP["experience"]

    return FOLLOW_UP.get(prev_type, FOLLOW_UP["other"])


SYSTEM_PROMPT = (
    "당신은 IT 직무 모의면접을 진행하는 전문 면접관입니다. "
    "이전 질문과 지원자 답변을 참고해서 자연스러운 꼬리 질문 1개만 생성하세요. "
    "한국어로, 한 문장으로, 너무 길지 않게."
)


def build_llm() -> Optional[object]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or ChatOpenAI is None:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temp = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
    return ChatOpenAI(model=model, temperature=temp)


def llm_next_question(llm, history: List[object], prev_q: str, prev_type: str, user_answer: str) -> str:
    prompt = (
        f"[이전 질문 유형] {prev_type}\n"
        f"[이전 질문] {prev_q}\n"
        f"[지원자 답변] {user_answer}\n\n"
        "꼬리 질문 1개를 생성하세요."
    )
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(history[-6:])
    messages.append(HumanMessage(content=prompt))
    resp = llm.invoke(messages)
    q = resp.content.strip().split("\n")[0].strip()
    return q


class InterviewEngine:
    """
    - 룰 기반으로 100% 동작
    - LLM이 가능하면 next_question만 LLM로 '옵션' 사용
    """

    def __init__(self, use_llm: bool = False):
        self.llm = build_llm() if use_llm else None
        self.history: List[object] = []  # LLM 메시지 히스토리(최소)
        self.turns: List[Turn] = []

    def start(self, first_question: str) -> str:
        self.turns = []
        self.history = []
        return clean_text(first_question)

    def step(self, user_answer: str) -> Tuple[str, Dict]:
        if not self.turns:
            raise ValueError("Interview not started. Call start() and set first question in session.")

        prev = self.turns[-1]
        ua = clean_text(user_answer)

        next_q = rule_next_question(prev.question, prev.q_type, ua)

        if self.llm is not None and SystemMessage is not None:
            try:
                next_q_llm = llm_next_question(
                    llm=self.llm,
                    history=self.history,
                    prev_q=prev.question,
                    prev_type=prev.q_type,
                    user_answer=ua,
                )
                if next_q_llm:
                    next_q = next_q_llm
            except Exception:
                pass

        if HumanMessage is not None and AIMessage is not None:
            self.history.append(HumanMessage(content=prev.question))
            self.history.append(AIMessage(content=ua))

        debug = {
            "prev_q_type": prev.q_type,
            "used_llm": self.llm is not None,
            "turn": prev.turn,
        }
        return clean_text(next_q), debug

    def add_question(self, question: str, user_answer: str = "") -> Turn:
        q = clean_text(question)
        qt = classify_question(q)
        t = Turn(turn=len(self.turns) + 1, question=q, q_type=qt, user_answer=clean_text(user_answer))
        self.turns.append(t)
        return t

    def export_turns(self) -> List[Dict]:
        return [asdict(t) for t in self.turns]
