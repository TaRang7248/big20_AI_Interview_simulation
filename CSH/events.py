"""
이벤트 정의 모듈
================
이벤트 기반 마이크로서비스 아키텍처의 핵심 이벤트 타입 정의

모든 서비스 간 통신은 이 모듈에 정의된 이벤트를 통해 이루어집니다.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ========== 이벤트 타입 열거형 ==========

class EventType(str, Enum):
    """시스템 전체 이벤트 타입"""

    # ── 세션 라이프사이클 ──
    SESSION_CREATED = "interview.session.created"
    SESSION_STARTED = "interview.session.started"
    SESSION_ENDED = "interview.session.ended"
    SESSION_TIMEOUT = "interview.session.timeout"

    # ── 면접 진행 ──
    QUESTION_GENERATED = "interview.question.generated"
    ANSWER_SUBMITTED = "interview.answer.submitted"
    FOLLOWUP_DECIDED = "interview.followup.decided"
    TURN_STARTED = "interview.turn.started"
    TURN_ENDED = "interview.turn.ended"

    # ── AI 평가 ──
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"
    BATCH_EVALUATION_COMPLETED = "evaluation.batch.completed"

    # ── 감정 분석 ──
    EMOTION_ANALYZED = "emotion.analyzed"
    EMOTION_ALERT = "emotion.alert"

    # ── STT / TTS ──
    STT_TRANSCRIBED = "stt.transcribed"
    STT_PARTIAL = "stt.partial"
    TTS_GENERATED = "tts.generated"
    TTS_PREFETCHED = "tts.prefetched"

    # ── RAG / 이력서 ──
    RESUME_UPLOADED = "resume.uploaded"
    RESUME_INDEXED = "resume.indexed"
    RAG_SEARCH_COMPLETED = "rag.search.completed"

    # ── 리포트 ──
    REPORT_GENERATION_STARTED = "report.generation.started"
    REPORT_GENERATED = "report.generated"

    # ── 코딩 테스트 ──
    CODING_PROBLEM_GENERATED = "coding.problem.generated"
    CODING_SUBMITTED = "coding.submitted"
    CODING_ANALYZED = "coding.analyzed"

    # ── 화이트보드 ──
    WHITEBOARD_SUBMITTED = "whiteboard.submitted"
    WHITEBOARD_ANALYZED = "whiteboard.analyzed"

    # ── 개입 시스템 (VAD) ──
    INTERVENTION_TRIGGERED = "intervention.triggered"
    VAD_SIGNAL = "intervention.vad.signal"

    # ── 시스템 ──
    SERVICE_HEALTH_CHECK = "system.health.check"
    SERVICE_STATUS_CHANGED = "system.service.status"
    ERROR_OCCURRED = "system.error"


# ========== 이벤트 베이스 모델 ==========

class Event(BaseModel):
    """모든 이벤트의 기본 모델"""
    event_type: str
    event_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = "unknown"          # 이벤트 발행 서비스 이름
    session_id: Optional[str] = None  # 관련 면접 세션 ID
    user_email: Optional[str] = None  # 관련 사용자
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


# ========== 도메인별 이벤트 모델 ==========

class SessionEvent(Event):
    """세션 관련 이벤트"""
    source: str = "session_manager"


class InterviewEvent(Event):
    """면접 진행 이벤트"""
    source: str = "ai_interviewer"


class EvaluationEvent(Event):
    """평가 이벤트"""
    source: str = "evaluation_service"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "task_id": None,
        "score": None,
        "feedback": None,
    })


class EmotionEvent(Event):
    """감정 분석 이벤트"""
    source: str = "emotion_engine"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "dominant_emotion": None,
        "probabilities": {},
        "confidence": 0.0,
    })


class STTEvent(Event):
    """음성 인식 이벤트"""
    source: str = "stt_service"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "transcript": "",
        "is_final": False,
        "confidence": 0.0,
    })


class TTSEvent(Event):
    """음성 합성 이벤트"""
    source: str = "tts_service"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "text": "",
        "audio_url": None,
        "duration": 0.0,
    })


class ResumeEvent(Event):
    """이력서 관련 이벤트"""
    source: str = "rag_service"


class ReportEvent(Event):
    """리포트 관련 이벤트"""
    source: str = "report_generator"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "task_id": None,
        "report_data": None,
    })


class CodingEvent(Event):
    """코딩 테스트 이벤트"""
    source: str = "coding_service"


class WhiteboardEvent(Event):
    """화이트보드 이벤트"""
    source: str = "whiteboard_service"


class InterventionEvent(Event):
    """개입 시스템 이벤트"""
    source: str = "intervention_manager"
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "should_intervene": False,
        "reason": None,
        "message": None,
    })


class SystemEvent(Event):
    """시스템 이벤트"""
    source: str = "system"


# ========== 이벤트 팩토리 ==========

class EventFactory:
    """이벤트 생성 팩토리 — 타입별 올바른 이벤트 객체 생성"""

    _TYPE_MAP = {
        EventType.SESSION_CREATED: SessionEvent,
        EventType.SESSION_STARTED: SessionEvent,
        EventType.SESSION_ENDED: SessionEvent,
        EventType.SESSION_TIMEOUT: SessionEvent,
        EventType.QUESTION_GENERATED: InterviewEvent,
        EventType.ANSWER_SUBMITTED: InterviewEvent,
        EventType.FOLLOWUP_DECIDED: InterviewEvent,
        EventType.TURN_STARTED: InterviewEvent,
        EventType.TURN_ENDED: InterviewEvent,
        EventType.EVALUATION_STARTED: EvaluationEvent,
        EventType.EVALUATION_COMPLETED: EvaluationEvent,
        EventType.BATCH_EVALUATION_COMPLETED: EvaluationEvent,
        EventType.EMOTION_ANALYZED: EmotionEvent,
        EventType.EMOTION_ALERT: EmotionEvent,
        EventType.STT_TRANSCRIBED: STTEvent,
        EventType.STT_PARTIAL: STTEvent,
        EventType.TTS_GENERATED: TTSEvent,
        EventType.TTS_PREFETCHED: TTSEvent,
        EventType.RESUME_UPLOADED: ResumeEvent,
        EventType.RESUME_INDEXED: ResumeEvent,
        EventType.RAG_SEARCH_COMPLETED: ResumeEvent,
        EventType.REPORT_GENERATION_STARTED: ReportEvent,
        EventType.REPORT_GENERATED: ReportEvent,
        EventType.CODING_PROBLEM_GENERATED: CodingEvent,
        EventType.CODING_SUBMITTED: CodingEvent,
        EventType.CODING_ANALYZED: CodingEvent,
        EventType.WHITEBOARD_SUBMITTED: WhiteboardEvent,
        EventType.WHITEBOARD_ANALYZED: WhiteboardEvent,
        EventType.INTERVENTION_TRIGGERED: InterventionEvent,
        EventType.VAD_SIGNAL: InterventionEvent,
        EventType.SERVICE_HEALTH_CHECK: SystemEvent,
        EventType.SERVICE_STATUS_CHANGED: SystemEvent,
        EventType.ERROR_OCCURRED: SystemEvent,
    }

    @classmethod
    def create(
        cls,
        event_type: EventType,
        session_id: Optional[str] = None,
        user_email: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        **kwargs,
    ) -> Event:
        """이벤트 타입에 맞는 이벤트 객체 생성"""
        event_cls = cls._TYPE_MAP.get(event_type, Event)
        params = {
            "event_type": event_type.value,
            "session_id": session_id,
            "user_email": user_email,
            "data": data or {},
            **kwargs,
        }
        if source:
            params["source"] = source
        return event_cls(**params)
