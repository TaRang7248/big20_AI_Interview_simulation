"""
LangGraph 기반 면접 워크플로우 상태머신
=======================================
워크플로우 상태머신 구현

기능:
  1. 조건부 분기  — add_conditional_edges 로 감정·점수 기반 라우팅
  2. 루프 제어    — 꼬리질문 2회 제한, MAX_QUESTIONS 체크
  3. 체크포인트   — MemorySaver 로 세션 중단·재개 지원
  4. 병렬 처리    — 답변 평가 + 감정 분석 동시 실행 (asyncio.gather)
  5. 시각화/감사  — Mermaid 다이어그램 + 실행 추적 로그

Usage:
    from interview_workflow import InterviewWorkflow, WorkflowState, get_workflow_instance

    wf = get_workflow_instance()
    result = await wf.run(session_id, user_input="[START]")
    # result = {"response": "...", "phase": "greeting", ...}
"""

from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver

# ── LangGraph ──
from langgraph.graph import END, START, StateGraph

# ── Thinking 모델 추론 토큰 제거 유틸리티 (EXAONE Deep: <thought>, qwen3: <think>) ──
# integrated_interview_server.py에 정의된 strip_think_tokens를 import합니다.
# 순환 import 방지를 위해 lazy import 패턴을 사용합니다.
_strip_think_tokens = None


def _get_strip_think_tokens():
    """스트립 함수를 지연 로드 (순환 import 방지)"""
    global _strip_think_tokens
    if _strip_think_tokens is None:
        try:
            from integrated_interview_server import strip_think_tokens

            _strip_think_tokens = strip_think_tokens
        except ImportError:
            import re as _re

            # 폴백: 직접 구현 (EXAONE Deep <thought> + qwen3 <think> 모두 지원)
            def _fallback(text: str) -> str:
                cleaned = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
                cleaned = _re.sub(r"<think>.*$", "", cleaned, flags=_re.DOTALL)
                cleaned = _re.sub(
                    r"<thought>.*?</thought>", "", cleaned, flags=_re.DOTALL
                )
                cleaned = _re.sub(r"<thought>.*$", "", cleaned, flags=_re.DOTALL)
                return cleaned.strip()

            _strip_think_tokens = _fallback
    return _strip_think_tokens


# ========================================================================== #
#                            Phase & State 정의                               #
# ========================================================================== #


class InterviewPhase(str, Enum):
    """면접 단계 열거형"""

    IDLE = "idle"  # 초기 상태 (세션 생성 직후)
    GREETING = "greeting"  # 인사 / 자기소개 요청
    GENERATE_QUESTION = "generate_question"  # LLM 질문 생성
    WAIT_ANSWER = "wait_answer"  # 사용자 답변 대기
    PROCESS_ANSWER = "process_answer"  # 답변 수신 후 전처리
    EVALUATE = "evaluate"  # 답변 평가 (병렬: 평가 + 감정)
    ROUTE_NEXT = "route_next"  # 다음 단계 라우팅
    FOLLOW_UP = "follow_up"  # 꼬리질문 생성
    COMPLETE = "complete"  # 면접 종료 + 보고서 생성
    ERROR = "error"  # 오류 복구


class WorkflowState(TypedDict, total=False):
    """LangGraph 상태 — 면접 전체 컨텍스트를 하나의 딕셔너리로 관리"""

    # ── 세션 식별 ──
    session_id: str
    phase: str  # InterviewPhase 값

    # ── 입력 / 출력 ──
    user_input: str  # 현재 턴의 사용자 입력
    response: str  # AI 면접관 응답 (최종 출력)

    # ── 질문 추적 ──
    question_count: int  # 현재까지 질문 수 (1부터)
    max_questions: int  # 최대 질문 수 (기본 10)
    current_topic: str  # 현재 질문 주제
    topic_question_count: int  # 해당 주제 내 질문 수
    topic_history: List[Dict]  # 주제 변경 이력

    # ── 꼬리질문 ──
    follow_up_mode: bool
    follow_up_reason: str
    needs_follow_up: bool

    # ── 평가 ──
    last_evaluation: Optional[Dict]  # 직전 답변 평가 결과
    evaluations: List[Dict]  # 누적 평가
    pending_eval_task_id: Optional[str]  # Celery 평가 태스크 ID

    # ── 감정 ──
    last_emotion: Optional[Dict]  # 직전 감정 분석 결과 (DeepFace)
    emotion_history: List[Dict]  # 감정 변화 이력
    emotion_adaptive_mode: str  # "normal" | "encouraging" | "challenging"

    # ── 음성 감정 (Hume Prosody) ──
    last_prosody: Optional[Dict]  # 직전 Prosody 분석 결과
    prosody_history: List[Dict]  # Prosody 변화 이력

    # ── 대화 기록 ──
    chat_history: List[Dict]

    # ── RAG 사전 조회 결과 (evaluate 노드에서 병렬 조회 → generate_question에서 사용) ──
    rag_resume_context: str  # 이력서 RAG 검색 결과 → LLM 프롬프트에 주입
    rag_qa_context: str  # Q&A 참조 RAG 검색 결과 → LLM 프롬프트에 주입

    # ── 감사 / 추적 ──
    trace: List[Dict]  # [{node, timestamp, duration_ms, details}]
    error_info: Optional[str]

    # ── 외부 연결 플래그 ──
    use_rag: bool
    celery_available: bool
    llm_available: bool


# ========================================================================== #
#                          Trace / Audit Helpers                              #
# ========================================================================== #


def _trace_entry(node: str, details: str = "", duration_ms: float = 0) -> Dict:
    """감사 추적 엔트리 생성"""
    return {
        "node": node,
        "timestamp": datetime.now().isoformat(),
        "duration_ms": round(duration_ms, 2),
        "details": details,
    }


# ========================================================================== #
#                            Node 함수 정의                                    #
# ========================================================================== #


class InterviewNodes:
    """
    각 grpah 노드에서 실행되는 순수 함수(또는 코루틴)들을 모은 클래스.
    외부 서비스(interviewer, state 등)는 run-time에 주입됩니다.
    """

    def __init__(self, server_state, interviewer_instance, event_bus=None):
        """
        Parameters
        ----------
        server_state : InterviewState   — 서버 세션 상태 관리자
        interviewer_instance : AIInterviewer — LLM 면접관
        event_bus : EventBus | None     — 이벤트 퍼블리셔
        """
        self._state_mgr = server_state
        self._interviewer = interviewer_instance
        self._event_bus = event_bus

    # ------------------------------------------------------------------ #
    #  1. greeting — 인사 / 자기소개 요청                                    #
    # ------------------------------------------------------------------ #
    async def greeting(self, ws: WorkflowState) -> Dict:
        """최초 [START] 신호 시 인사말 반환"""
        t0 = time.perf_counter()
        session_id = ws["session_id"]

        greeting_msg = self._interviewer.get_initial_greeting()

        # 서버 세션에도 반영
        session = self._state_mgr.get_session(session_id)
        if session:
            chat_history = session.get("chat_history", [])
            chat_history.append({"role": "assistant", "content": greeting_msg})
            self._state_mgr.update_session(
                session_id,
                {
                    "chat_history": chat_history,
                    "question_count": 1,
                },
            )

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(_trace_entry("greeting", "초기 인사말 생성", elapsed))

        return {
            "response": greeting_msg,
            "phase": InterviewPhase.GREETING.value,
            "question_count": 1,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  2. process_answer — 사용자 답변 수신 및 전처리                         #
    # ------------------------------------------------------------------ #
    async def process_answer(self, ws: WorkflowState) -> Dict:
        """사용자 답변을 세션에 기록하고, 이전 질문 정보를 추출"""
        t0 = time.perf_counter()
        session_id = ws["session_id"]
        user_input = ws.get("user_input", "")

        session = self._state_mgr.get_session(session_id)
        if not session:
            return {"error_info": "세션 없음", "phase": InterviewPhase.ERROR.value}

        chat_history = session.get("chat_history", [])
        chat_history.append({"role": "user", "content": user_input})
        self._state_mgr.update_session(session_id, {"chat_history": chat_history})

        # 이전 질문 찾기 (평가용)
        previous_question = ""
        for msg in reversed(chat_history[:-1]):
            if msg["role"] == "assistant":
                previous_question = msg["content"]
                break

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "process_answer",
                f"답변 길이={len(user_input)}자, 이전질문 존재={bool(previous_question)}",
                elapsed,
            )
        )

        return {
            "phase": InterviewPhase.PROCESS_ANSWER.value,
            "chat_history": chat_history,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  3. evaluate — 병렬: 답변 평가 + 감정 분석                             #
    # ------------------------------------------------------------------ #
    async def evaluate(self, ws: WorkflowState) -> Dict:
        """답변 평가 + 감정 분석을 병렬로 실행"""
        t0 = time.perf_counter()
        session_id = ws["session_id"]
        user_input = ws.get("user_input", "")

        session = self._state_mgr.get_session(session_id)
        if not session:
            return {"error_info": "세션 없음", "phase": InterviewPhase.ERROR.value}

        chat_history = session.get("chat_history", [])

        # 이전 질문 가져오기
        previous_question = ""
        for msg in reversed(chat_history):
            if msg["role"] == "assistant":
                previous_question = msg["content"]
                break

        # ── 병렬 태스크 구성 ──
        eval_result: Optional[Dict] = None
        emotion_result: Optional[Dict] = None
        prosody_result: Optional[Dict] = None
        pending_task_id: Optional[str] = None

        async def _run_evaluation():
            nonlocal eval_result, pending_task_id
            try:
                # Celery가 가용하면 비동기 오프로드
                if ws.get("celery_available") and previous_question:
                    try:
                        # 동적 import (순환 방지)
                        from celery_tasks import evaluate_answer_task

                        task = evaluate_answer_task.delay(
                            session_id, previous_question, user_input, ""
                        )
                        pending_task_id = task.id
                        # 태스크 ID를 세션에 저장
                        pending_tasks = session.get("pending_eval_tasks", [])
                        pending_tasks.append(
                            {
                                "task_id": task.id,
                                "question": previous_question,
                                "answer": user_input,
                                "submitted_at": time.time(),
                            }
                        )
                        self._state_mgr.update_session(
                            session_id,
                            {
                                "pending_eval_tasks": pending_tasks,
                            },
                        )
                    except Exception as e:
                        print(f"⚠️ [Workflow] Celery 평가 오프로드 실패: {e}")
                # Celery 불가 시 → 인라인 평가 스킵 (LLM 이중 호출 방지)
                # 평가는 면접 종료 후 collect_celery_evaluations 또는
                # start_interview_completion_workflow에서 일괄 처리
                elif previous_question and self._interviewer.llm:
                    # evaluate_answer를 여기서 호출하면 generate_question과 합쳐
                    # LLM 2회 순차 호출 → 응답 시간 2배 증가 (GPU 경합)
                    # 대신 세션에 pending 정보만 기록하고 스킵
                    pending_tasks = session.get("pending_eval_tasks", [])
                    pending_tasks.append(
                        {
                            "task_id": f"deferred_{time.time()}",
                            "question": previous_question,
                            "answer": user_input,
                            "submitted_at": time.time(),
                            "deferred": True,  # Celery 미사용, 나중에 일괄 평가 표시
                        }
                    )
                    self._state_mgr.update_session(
                        session_id,
                        {
                            "pending_eval_tasks": pending_tasks,
                        },
                    )
                    print("📋 [Workflow] 평가 지연 저장 (Celery 미가용, LLM 경합 방지)")
            except Exception as e:
                print(f"⚠️ [Workflow] 평가 오류: {e}")

        async def _run_emotion():
            nonlocal emotion_result
            try:
                # 세션에 저장된 마지막 감정 데이터 활용
                last_emotion = self._state_mgr.last_emotion
                if last_emotion:
                    emotion_result = last_emotion
            except Exception:
                pass

        async def _run_prosody():
            """Hume Prosody 음성 감정 데이터 수집"""
            nonlocal prosody_result
            try:
                last_prosody = self._state_mgr.last_prosody
                if last_prosody:
                    prosody_result = last_prosody
            except Exception:
                pass

        # ── RAG 사전 조회 (질문 생성 노드에서 사용할 컨텍스트) ──
        # ⚡ GPU 경합 방지: RAG 임베딩(nomic-embed-text)이 Ollama를 호출하므로
        #    LLM과 동시에 실행하면 GPU 직렬 큐잉으로 타임아웃 발생.
        #    RAG를 먼저 완료한 뒤 평가(Celery/LLM)를 실행하여 GPU 경합을 회피합니다.
        #    generate_question 시점에는 이미 State에 RAG 결과가 준비되어 LLM 호출만 수행
        rag_resume_ctx = ""
        rag_qa_ctx = ""

        try:
            rag_resume_ctx, rag_qa_ctx = await self._interviewer.fetch_rag_contexts(
                session_id, user_input
            )
        except Exception as e:
            print(f"⚠️ [Workflow] RAG 사전 조회 실패 (무시): {e}")

        # 병렬 실행 (평가 + 감정 + Prosody) — RAG는 위에서 이미 완료됨
        await asyncio.gather(_run_evaluation(), _run_emotion(), _run_prosody())

        # ── 감정 기반 적응 모드 결정 (★ 멀티모달 융합: Prosody + DeepFace 동시) ──
        emotion_adaptive_mode = ws.get("emotion_adaptive_mode", "normal")
        multimodal_fusion: Optional[Dict] = None

        if prosody_result and emotion_result:
            # ── 양쪽 다 있을 때: 멀티모달 가중 융합 (Prosody 60% + DeepFace 40%) ──
            try:
                from hume_prosody_service import get_prosody_service

                svc = get_prosody_service()
                if svc:
                    prosody_indicators = prosody_result.get("interview_indicators", {})
                    fusion = svc.merge_with_deepface(
                        prosody_indicators=prosody_indicators,
                        deepface_emotion=emotion_result,
                        prosody_weight=0.5,
                    )
                    emotion_adaptive_mode = fusion.get(
                        "emotion_adaptive_mode", "normal"
                    )
                    multimodal_fusion = fusion
            except Exception:
                # 융합 실패 시 Prosody 단독 사용
                emotion_adaptive_mode = prosody_result.get("adaptive_mode", "normal")
        elif prosody_result:
            # ── Prosody만 있을 때: 48감정 10지표 기반 결정 ──
            emotion_adaptive_mode = prosody_result.get("adaptive_mode", "normal")
        elif emotion_result:
            # ── DeepFace만 있을 때: 7감정 기반 결정 (폴백) ──
            dominant = emotion_result.get("dominant_emotion", "neutral")
            if dominant in ("sad", "fear", "disgust"):
                emotion_adaptive_mode = "encouraging"
            elif dominant in ("happy", "surprise"):
                emotion_adaptive_mode = "challenging"
            else:
                emotion_adaptive_mode = "normal"

        # 감정 이력 업데이트
        emotion_history = ws.get("emotion_history", [])
        if emotion_result:
            emotion_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "emotion": emotion_result,
                }
            )

        # Prosody 이력 업데이트
        prosody_history = ws.get("prosody_history", [])
        if prosody_result:
            prosody_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "prosody": prosody_result,
                }
            )

        # 평가 누적
        evaluations = ws.get("evaluations", [])
        if eval_result:
            evaluations.append(eval_result)

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "evaluate",
                f"celery_task={pending_task_id or 'N/A'}, "
                f"emotion={emotion_adaptive_mode}, "
                f"prosody={prosody_result.get('dominant_indicator') if prosody_result else 'N/A'}, "
                f"fusion={'yes' if multimodal_fusion else 'no'}, "
                f"eval_score={eval_result.get('total_score') if eval_result else 'pending'}",
                elapsed,
            )
        )

        return {
            "phase": InterviewPhase.EVALUATE.value,
            "last_evaluation": eval_result,
            "evaluations": evaluations,
            "last_emotion": emotion_result,
            "emotion_history": emotion_history,
            "emotion_adaptive_mode": emotion_adaptive_mode,
            "last_prosody": prosody_result,
            "prosody_history": prosody_history,
            "pending_eval_task_id": pending_task_id,
            "rag_resume_context": rag_resume_ctx,
            "rag_qa_context": rag_qa_ctx,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  4. route_next — 조건부 분기 결정                                      #
    # ------------------------------------------------------------------ #
    async def route_next(self, ws: WorkflowState) -> Dict:
        """
        다음 액션을 결정하는 라우팅 노드.
        - MAX_QUESTIONS 도달 → complete
        - 꼬리질문 필요 → follow_up
        - 그 외 → generate_question
        """
        t0 = time.perf_counter()
        session_id = ws["session_id"]
        user_input = ws.get("user_input", "")

        session = self._state_mgr.get_session(session_id)
        question_count = ws.get(
            "question_count", session.get("question_count", 1) if session else 1
        )
        max_questions = ws.get("max_questions", 10)

        # ── 꼬리질문 판단 ──
        needs_follow_up = False
        follow_up_reason = ""
        topic_count = ws.get("topic_question_count", 0)

        if user_input and user_input not in ("[START]", "[NEXT]"):
            needs_follow_up, follow_up_reason = self._interviewer.should_follow_up(
                session_id, user_input
            )
            # 주제당 2회 이상이면 꼬리질문 중단
            if topic_count >= 2:
                needs_follow_up = False
                follow_up_reason = "주제 전환 필요"

        # LangGraph의 노드(Node) 내부에서 실행되는 로직으로, 사용자의 감정 상태에 따라 그래프의 흐름(다음 동작)을 결정하는 오케스트레이션의 핵심 로직
        # ── 감정 기반 적응 (조건부 분기 확장) ──
        emotion_mode = ws.get("emotion_adaptive_mode", "normal")
        # 불안/공포 감지 시 → 꼬리질문/압박 질문 완화
        if emotion_mode == "encouraging" and needs_follow_up:
            needs_follow_up = False
            follow_up_reason = "감정 적응: 격려 모드 (꼬리질문 완화)"

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "route_next",
                f"q={question_count}/{max_questions}, follow_up={needs_follow_up}, "
                f"emotion_mode={emotion_mode}, reason={follow_up_reason}",
                elapsed,
            )
        )

        return {
            "phase": InterviewPhase.ROUTE_NEXT.value,
            "needs_follow_up": needs_follow_up,
            "follow_up_reason": follow_up_reason,
            "follow_up_mode": needs_follow_up,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  5. generate_question — LLM 질문 생성 (독립적 상태 변환)              #
    # ------------------------------------------------------------------ #
    async def generate_question(self, ws: WorkflowState) -> Dict:
        """State에서 조립된 데이터로 LLM 질문 생성 (독립적 상태 변환)

        이전 Thin Wrapper 방식과 달리, 각 노드가 담당하는 데이터를 State에서
        직접 수신하여 build_and_call_llm()에 전달합니다:
          - RAG 컨텍스트: evaluate 노드에서 사전 조회 → State 경유
          - 감정 적응: evaluate 노드에서 결정 → State 경유
          - 꼬리질문 정보: route_next 노드에서 판단 → State 경유
          - 주제 추적/질문 카운트: 이 노드에서만 1회 업데이트 (중복 제거)
        """
        t0 = time.perf_counter()
        session_id = ws["session_id"]
        user_input = ws.get("user_input", "")

        session = self._state_mgr.get_session(session_id)
        if not session:
            return {"error_info": "세션 없음", "phase": InterviewPhase.ERROR.value}

        # ── State에서 사전 조회된 컨텍스트 수신 (evaluate 노드에서 준비) ──
        resume_context = ws.get("rag_resume_context", "")
        qa_context = ws.get("rag_qa_context", "")
        emotion_mode = ws.get("emotion_adaptive_mode", "normal")
        needs_follow_up = ws.get("needs_follow_up", False)
        follow_up_reason = ws.get("follow_up_reason", "")
        current_topic = ws.get("current_topic", "general")
        topic_count = ws.get("topic_question_count", 0)

        # ── 감정 적응 모드 세션에 동기화 ──
        if emotion_mode != "normal":
            self._state_mgr.update_session(
                session_id, {"emotion_adaptive_mode": emotion_mode}
            )

        # ── LLM 질문 생성 (build_and_call_llm: 순수 프롬프트 조립 + LLM 호출) ──
        # 판단 로직(should_follow_up, RAG, topic_tracking)은 이미 각 노드에서 처리됨
        question = await self._interviewer.build_and_call_llm(
            session_id,
            user_input,
            resume_context=resume_context,
            qa_context=qa_context,
            needs_follow_up=needs_follow_up,
            follow_up_reason=follow_up_reason,
            current_topic=current_topic,
            topic_count=topic_count,
            emotion_mode=emotion_mode,
        )

        # ── 대화 기록 업데이트 ──
        session = self._state_mgr.get_session(session_id)
        chat_history = session.get("chat_history", [])
        chat_history.append({"role": "assistant", "content": question})

        # ── 주제 추적 업데이트 (이 노드에서만 1회 호출 — 중복 제거) ──
        if user_input and user_input not in ("[START]", "[NEXT]"):
            is_follow_up = ws.get("follow_up_mode", False)
            self._interviewer.update_topic_tracking(
                session_id, user_input, is_follow_up
            )

        # ── 질문 카운트 증가 (이 노드에서만 1회 처리 — 중복 제거) ──
        question_count = session.get("question_count", 1)
        new_q_count = question_count + 1
        self._state_mgr.update_session(
            session_id,
            {
                "chat_history": chat_history,
                "question_count": new_q_count,
            },
        )

        session = self._state_mgr.get_session(session_id)

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "generate_question",
                f"질문 길이={len(question)}자, emotion_mode={emotion_mode}, "
                f"q_count={new_q_count}, rag_resume={bool(resume_context)}, "
                f"rag_qa={bool(qa_context)}",
                elapsed,
            )
        )

        return {
            "response": question,
            "phase": InterviewPhase.GENERATE_QUESTION.value,
            "question_count": new_q_count,
            "current_topic": session.get("current_topic", "general"),
            "topic_question_count": session.get("topic_question_count", 0),
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  6. follow_up — 꼬리질문 생성 (독립적 상태 변환)                       #
    # ------------------------------------------------------------------ #
    async def follow_up(self, ws: WorkflowState) -> Dict:
        """꼬리질문 전용 노드 — State에서 조립된 데이터로 LLM 호출

        generate_question과 동일하게 build_and_call_llm()을 사용하되,
        needs_follow_up=True를 강제 전달하여 꼬리질문 프롬프트를 활성화합니다.
        주제 추적 시 is_follow_up=True로 기록하여 추적 통계에 반영합니다.
        """
        t0 = time.perf_counter()
        session_id = ws["session_id"]
        user_input = ws.get("user_input", "")

        # ── State에서 사전 조회된 컨텍스트 수신 ──
        resume_context = ws.get("rag_resume_context", "")
        qa_context = ws.get("rag_qa_context", "")
        emotion_mode = ws.get("emotion_adaptive_mode", "normal")
        follow_up_reason = ws.get("follow_up_reason", "")
        current_topic = ws.get("current_topic", "general")
        topic_count = ws.get("topic_question_count", 0)

        # follow_up_mode 세팅
        self._state_mgr.update_session(session_id, {"follow_up_mode": True})

        # ── LLM 질문 생성 (꼬리질문 모드: needs_follow_up=True 강제) ──
        question = await self._interviewer.build_and_call_llm(
            session_id,
            user_input,
            resume_context=resume_context,
            qa_context=qa_context,
            needs_follow_up=True,
            follow_up_reason=follow_up_reason,
            current_topic=current_topic,
            topic_count=topic_count,
            emotion_mode=emotion_mode,
        )

        # ── 대화 기록 + 주제 추적 + 질문 카운트 ──
        session = self._state_mgr.get_session(session_id)
        chat_history = session.get("chat_history", [])
        chat_history.append({"role": "assistant", "content": question})

        # 주제 추적 (꼬리질문: is_follow_up=True)
        self._interviewer.update_topic_tracking(session_id, user_input, True)

        # 질문 카운트 증가
        question_count = session.get("question_count", 1)
        new_q_count = question_count + 1
        self._state_mgr.update_session(
            session_id,
            {
                "chat_history": chat_history,
                "question_count": new_q_count,
            },
        )

        session = self._state_mgr.get_session(session_id)

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "follow_up",
                f"꼬리질문 생성, 길이={len(question)}자, reason={follow_up_reason}, "
                f"rag_resume={bool(resume_context)}, rag_qa={bool(qa_context)}",
                elapsed,
            )
        )

        return {
            "response": question,
            "phase": InterviewPhase.FOLLOW_UP.value,
            "question_count": new_q_count,
            "current_topic": session.get("current_topic", "general"),
            "topic_question_count": session.get("topic_question_count", 0),
            "follow_up_mode": True,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  7. complete — 면접 종료 + 워크플로우 시작                              #
    # ------------------------------------------------------------------ #
    async def complete(self, ws: WorkflowState) -> Dict:
        """면접 종료 처리: 종료 메시지 + 리포트 생성 워크플로우 트리거"""
        t0 = time.perf_counter()
        session_id = ws["session_id"]

        closing_msg = (
            "면접이 종료되었습니다. 수고하셨습니다. 결과 보고서를 확인해주세요."
        )

        # 서버 세션 업데이트
        session = self._state_mgr.get_session(session_id)
        if session:
            chat_history = session.get("chat_history", [])
            chat_history.append({"role": "assistant", "content": closing_msg})
            self._state_mgr.update_session(
                session_id,
                {
                    "chat_history": chat_history,
                    "status": "completed",
                },
            )

        # 백그라운드 리포트 워크플로우 시작
        try:
            await self._interviewer.start_interview_completion_workflow(session_id)
        except Exception as e:
            print(f"⚠️ [Workflow] 완료 워크플로우 시작 실패: {e}")

        # 이벤트 발행
        if self._event_bus:
            try:
                from events import EventType as AppEventType

                await self._event_bus.publish(
                    AppEventType.SESSION_ENDED,
                    session_id=session_id,
                    data={"reason": "max_questions_reached"},
                    source="interview_workflow",
                )
            except Exception:
                pass

        elapsed = (time.perf_counter() - t0) * 1000
        trace = ws.get("trace", [])
        trace.append(
            _trace_entry("complete", "면접 종료 + 리포트 워크플로우 시작", elapsed)
        )

        return {
            "response": closing_msg,
            "phase": InterviewPhase.COMPLETE.value,
            "trace": trace,
        }

    # ------------------------------------------------------------------ #
    #  8. error — 오류 복구                                                #
    # ------------------------------------------------------------------ #
    async def error_recovery(self, ws: WorkflowState) -> Dict:
        """오류 발생 시 폴백 응답"""
        t0 = time.perf_counter()
        error_info = ws.get("error_info", "알 수 없는 오류")

        fallback_msg = "죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해 주세요."

        trace = ws.get("trace", [])
        trace.append(
            _trace_entry(
                "error_recovery",
                f"오류: {error_info}",
                (time.perf_counter() - t0) * 1000,
            )
        )

        return {
            "response": fallback_msg,
            "phase": InterviewPhase.ERROR.value,
            "trace": trace,
        }


# ========================================================================== #
#                         Edge 라우팅 함수                                     #
# ========================================================================== #


def route_after_process(state: WorkflowState) -> str:
    """process_answer 후 → evaluate 로 이동"""
    if state.get("error_info"):
        return "error_recovery"
    return "evaluate"


def route_after_evaluate(state: WorkflowState) -> str:
    """evaluate 후 → route_next 로 이동"""
    if state.get("error_info"):
        return "error_recovery"
    return "route_next"


def route_after_routing(state: WorkflowState) -> str:
    """
    route_next 후 조건부 분기:
      - MAX 도달 → complete
      - 꼬리질문  → follow_up
      - 일반      → generate_question
    """
    session_id = state.get("session_id", "")
    question_count = state.get("question_count", 1)
    max_questions = state.get("max_questions", 10)

    # 면접 종료 조건
    if question_count >= max_questions:
        return "complete"

    # 꼬리질문 분기
    if state.get("needs_follow_up", False):
        return "follow_up"

    # 일반 질문
    return "generate_question"


def route_initial(state: WorkflowState) -> str:
    """
    최초 입력 라우팅:
      - [START]  → greeting
      - [NEXT]   → generate_question
      - 일반 답변 → process_answer
    """
    user_input = state.get("user_input", "")
    if user_input == "[START]":
        return "greeting"
    elif user_input == "[NEXT]":
        return "generate_question"
    else:
        return "process_answer"


# ========================================================================== #
#                     InterviewWorkflow — 그래프 빌더                          #
# ========================================================================== #


class InterviewWorkflow:
    """
    LangGraph StateGraph 를 빌드하고 실행하는 메인 클래스.
    MemorySaver 체크포인터로 세션별 상태 중단·재개를 지원합니다.
    """

    def __init__(self, server_state, interviewer_instance, event_bus=None):
        self._nodes = InterviewNodes(server_state, interviewer_instance, event_bus)
        self._checkpointer = MemorySaver()
        self._graph = self._build_graph()
        self._compiled = self._graph.compile(checkpointer=self._checkpointer)

        # 실행 추적 저장소 (session_id → List[WorkflowState snapshots])
        self._execution_traces: Dict[str, List[Dict]] = {}

        print("✅ LangGraph InterviewWorkflow 빌드 완료 (StateGraph + MemorySaver)")

    # ------------------------------------------------------------------ #
    #  그래프 구축                                                          #
    # ------------------------------------------------------------------ #
    def _build_graph(self) -> StateGraph:
        """StateGraph 정의: 노드 + 엣지 + 조건부 엣지"""
        builder = StateGraph(WorkflowState)

        # ── 노드 등록 ──
        builder.add_node("greeting", self._nodes.greeting)
        builder.add_node("process_answer", self._nodes.process_answer)
        builder.add_node("evaluate", self._nodes.evaluate)
        builder.add_node("route_next", self._nodes.route_next)
        builder.add_node("generate_question", self._nodes.generate_question)
        builder.add_node("follow_up", self._nodes.follow_up)
        builder.add_node("complete", self._nodes.complete)
        builder.add_node("error_recovery", self._nodes.error_recovery)

        # ── 시작 → 초기 라우팅 (조건부) ──
        builder.add_conditional_edges(
            START,
            route_initial,
            {
                "greeting": "greeting",
                "generate_question": "generate_question",
                "process_answer": "process_answer",
            },
        )

        # ── greeting → END (턴 종료, 다음 호출 대기) ──
        builder.add_edge("greeting", END)

        # ── process_answer → evaluate (조건부: 오류 시 error_recovery) ──
        builder.add_conditional_edges(
            "process_answer",
            route_after_process,
            {
                "evaluate": "evaluate",
                "error_recovery": "error_recovery",
            },
        )

        # ── evaluate → route_next (조건부: 오류 시 error_recovery) ──
        builder.add_conditional_edges(
            "evaluate",
            route_after_evaluate,
            {
                "route_next": "route_next",
                "error_recovery": "error_recovery",
            },
        )

        # ── route_next → {complete | follow_up | generate_question} (조건부 분기) ──
        builder.add_conditional_edges(
            "route_next",
            route_after_routing,
            {
                "complete": "complete",
                "follow_up": "follow_up",
                "generate_question": "generate_question",
            },
        )

        # ── generate_question → END (턴 종료) ──
        builder.add_edge("generate_question", END)

        # ── follow_up → END (턴 종료) ──
        builder.add_edge("follow_up", END)

        # ── complete → END ──
        builder.add_edge("complete", END)

        # ── error_recovery → END ──
        builder.add_edge("error_recovery", END)

        return builder

    # ------------------------------------------------------------------ #
    #  실행                                                                #
    # ------------------------------------------------------------------ #
    async def run(
        self,
        session_id: str,
        user_input: str,
        *,
        use_rag: bool = True,
        celery_available: bool = False,
        llm_available: bool = True,
        extra_state: Optional[Dict] = None,
    ) -> Dict:
        """
        한 턴의 면접 워크플로우를 실행합니다.

        Parameters
        ----------
        session_id : str — 면접 세션 ID
        user_input : str — 사용자 입력 ("[START]", "[NEXT]", 또는 답변 텍스트)
        use_rag    : bool — RAG 사용 여부
        celery_available : bool — Celery 가용 여부
        llm_available : bool — LLM 가용 여부
        extra_state : dict — 추가 초기 상태

        Returns
        -------
        Dict — 최종 WorkflowState (response, phase, trace 등 포함)
        """
        # ── 초기 상태 구성 ──
        # 서버 세션에서 기존 상태 복원
        session = self._nodes._state_mgr.get_session(session_id)
        current_question_count = 1
        current_topic = "general"
        topic_question_count = 0
        emotion_adaptive_mode = "normal"

        if session:
            current_question_count = session.get("question_count", 1)
            current_topic = session.get("current_topic", "general")
            topic_question_count = session.get("topic_question_count", 0)
            emotion_adaptive_mode = session.get("emotion_adaptive_mode", "normal")

        initial_state: WorkflowState = {
            "session_id": session_id,
            "user_input": user_input,
            "phase": InterviewPhase.IDLE.value,
            "response": "",
            "question_count": current_question_count,
            "max_questions": 10,
            "current_topic": current_topic,
            "topic_question_count": topic_question_count,
            "topic_history": session.get("topic_history", []) if session else [],
            "follow_up_mode": session.get("follow_up_mode", False)
            if session
            else False,
            "follow_up_reason": "",
            "needs_follow_up": False,
            "last_evaluation": None,
            "evaluations": session.get("evaluations", []) if session else [],
            "pending_eval_task_id": None,
            "last_emotion": None,
            "emotion_history": [],
            "emotion_adaptive_mode": emotion_adaptive_mode,
            "chat_history": session.get("chat_history", []) if session else [],
            "rag_resume_context": "",  # evaluate 노드에서 RAG 병렬 조회 후 저장
            "rag_qa_context": "",  # evaluate 노드에서 RAG 병렬 조회 후 저장
            "trace": [],
            "error_info": None,
            "use_rag": use_rag,
            "celery_available": celery_available,
            "llm_available": llm_available,
        }

        if extra_state:
            initial_state.update(extra_state)

        # ── LangGraph 실행 (체크포인트 설정) ──
        config = {
            "configurable": {
                "thread_id": session_id,
            }
        }

        try:
            result = await self._compiled.ainvoke(initial_state, config=config)
        except Exception as e:
            print(f"❌ [Workflow] 그래프 실행 오류: {e}")
            traceback.print_exc()
            result = {
                "response": "죄송합니다. 일시적인 오류가 발생했습니다.",
                "phase": InterviewPhase.ERROR.value,
                "trace": [_trace_entry("graph_error", str(e))],
                "error_info": str(e),
            }

        # ── 실행 추적 저장 ──
        if session_id not in self._execution_traces:
            self._execution_traces[session_id] = []
        self._execution_traces[session_id].append(
            {
                "turn": len(self._execution_traces[session_id]) + 1,
                "user_input": user_input[:100],
                "phase": result.get("phase", "unknown"),
                "response_preview": result.get("response", "")[:100],
                "trace": result.get("trace", []),
                "timestamp": datetime.now().isoformat(),
            }
        )

        return result

    # ------------------------------------------------------------------ #
    #  체크포인트 관련                                                       #
    # ------------------------------------------------------------------ #
    def get_checkpoint(self, session_id: str) -> Optional[Dict]:
        """세션의 마지막 체크포인트 상태를 반환"""
        config = {"configurable": {"thread_id": session_id}}
        try:
            checkpoint = self._checkpointer.get(config)
            if checkpoint:
                return {
                    "session_id": session_id,
                    "checkpoint_id": checkpoint.get("id"),
                    "timestamp": checkpoint.get("ts"),
                    "channel_values": checkpoint.get("channel_values", {}),
                }
        except Exception as e:
            print(f"⚠️ 체크포인트 조회 실패: {e}")
        return None

    def list_checkpoints(self, session_id: str, limit: int = 10) -> List[Dict]:
        """세션의 체크포인트 이력을 반환"""
        config = {"configurable": {"thread_id": session_id}}
        results = []
        try:
            for cp in self._checkpointer.list(config, limit=limit):
                results.append(
                    {
                        "checkpoint_id": cp.get("id"),
                        "timestamp": cp.get("ts"),
                        "metadata": cp.get("metadata", {}),
                    }
                )
        except Exception as e:
            print(f"⚠️ 체크포인트 목록 조회 실패: {e}")
        return results

    # ------------------------------------------------------------------ #
    #  시각화 / 감사                                                        #
    # ------------------------------------------------------------------ #
    def get_graph_mermaid(self) -> str:
        """Mermaid 다이어그램 문자열을 반환"""
        try:
            return self._compiled.get_graph().draw_mermaid()
        except Exception as e:
            print(f"⚠️ Mermaid 생성 실패: {e}")
            # 폴백: 수동 Mermaid
            return self._fallback_mermaid()

    def _fallback_mermaid(self) -> str:
        """draw_mermaid() 실패 시 수동 Mermaid 다이어그램"""
        return """graph TD
    __start__([START]) --> |"[START]"| greeting
    __start__ --> |"[NEXT]"| generate_question
    __start__ --> |"답변"| process_answer
    greeting --> __end__([END])
    process_answer --> evaluate
    process_answer --> |"오류"| error_recovery
    evaluate --> route_next
    evaluate --> |"오류"| error_recovery
    route_next --> |"MAX 도달"| complete
    route_next --> |"꼬리질문"| follow_up
    route_next --> |"일반"| generate_question
    generate_question --> __end__
    follow_up --> __end__
    complete --> __end__
    error_recovery --> __end__

    style greeting fill:#4ade80,color:#000
    style evaluate fill:#60a5fa,color:#000
    style route_next fill:#fbbf24,color:#000
    style follow_up fill:#f97316,color:#000
    style complete fill:#a78bfa,color:#000
    style error_recovery fill:#f87171,color:#000
"""

    def get_execution_trace(self, session_id: str) -> List[Dict]:
        """세션의 전체 실행 추적 이력을 반환"""
        return self._execution_traces.get(session_id, [])

    def get_current_state_summary(self, session_id: str) -> Dict:
        """세션의 현재 워크플로우 상태 요약"""
        checkpoint = self.get_checkpoint(session_id)
        traces = self.get_execution_trace(session_id)

        return {
            "session_id": session_id,
            "total_turns": len(traces),
            "last_phase": traces[-1]["phase"] if traces else "idle",
            "last_timestamp": traces[-1]["timestamp"] if traces else None,
            "checkpoint_available": checkpoint is not None,
            "traces": traces,
        }

    def get_graph_definition(self) -> Dict:
        """정적 그래프 구조 정보를 반환"""
        return {
            "nodes": [
                {"id": "greeting", "description": "인사 / 자기소개 요청"},
                {"id": "process_answer", "description": "사용자 답변 수신 및 전처리"},
                {"id": "evaluate", "description": "답변 평가 + 감정 분석 (병렬)"},
                {"id": "route_next", "description": "조건부 분기 결정"},
                {"id": "generate_question", "description": "LLM 질문 생성"},
                {"id": "follow_up", "description": "꼬리질문 생성"},
                {"id": "complete", "description": "면접 종료 + 리포트 생성"},
                {"id": "error_recovery", "description": "오류 복구"},
            ],
            "edges": [
                {
                    "from": "START",
                    "to": "greeting",
                    "condition": "user_input == '[START]'",
                },
                {
                    "from": "START",
                    "to": "generate_question",
                    "condition": "user_input == '[NEXT]'",
                },
                {"from": "START", "to": "process_answer", "condition": "일반 답변"},
                {"from": "greeting", "to": "END", "condition": None},
                {"from": "process_answer", "to": "evaluate", "condition": "정상"},
                {"from": "process_answer", "to": "error_recovery", "condition": "오류"},
                {"from": "evaluate", "to": "route_next", "condition": "정상"},
                {"from": "evaluate", "to": "error_recovery", "condition": "오류"},
                {
                    "from": "route_next",
                    "to": "complete",
                    "condition": "question_count >= max_questions",
                },
                {
                    "from": "route_next",
                    "to": "follow_up",
                    "condition": "needs_follow_up && topic_count < 2",
                },
                {"from": "route_next", "to": "generate_question", "condition": "그 외"},
                {"from": "generate_question", "to": "END", "condition": None},
                {"from": "follow_up", "to": "END", "condition": None},
                {"from": "complete", "to": "END", "condition": None},
                {"from": "error_recovery", "to": "END", "condition": None},
            ],
            "conditional_features": [
                "감정 기반 적응 모드 (encouraging/challenging/normal)",
                "꼬리질문 루프 제어 (주제당 2회 제한)",
                "MAX_QUESTIONS 도달 시 자동 종료",
            ],
            "checkpointer": "MemorySaver (세션별 상태 중단·재개)",
            "parallel_processing": "evaluate 노드에서 답변 평가 + 감정 분석 동시 실행",
        }


# ========================================================================== #
#                         Singleton / Factory                                 #
# ========================================================================== #

_workflow_instance: Optional[InterviewWorkflow] = None


def init_workflow(
    server_state, interviewer_instance, event_bus=None
) -> InterviewWorkflow:
    """워크플로우 인스턴스를 초기화하고 반환"""
    global _workflow_instance
    _workflow_instance = InterviewWorkflow(
        server_state, interviewer_instance, event_bus
    )
    return _workflow_instance


def get_workflow_instance() -> Optional[InterviewWorkflow]:
    """초기화된 워크플로우 인스턴스를 반환"""
    return _workflow_instance
