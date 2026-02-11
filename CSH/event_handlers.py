"""
이벤트 핸들러 등록 모듈
========================
서비스 간 이벤트 기반 통신을 위한 핸들러 등록

SAD 설계서의 "이벤트 기반 마이크로서비스" 패턴 구현:
- 각 서비스는 관심 있는 이벤트를 구독하고, 반응적으로 처리합니다.
- 서비스 간 직접 호출 대신 이벤트를 통해 느슨한 결합을 유지합니다.

이벤트 흐름 예시:
  답변 제출 → ANSWER_SUBMITTED 이벤트 발행
    → 평가 서비스: 비동기 평가 작업 시작 → EVALUATION_STARTED
    → 감정 분석: 현재 감정 상태 기록
    → 개입 시스템: 턴 종료 처리
  
  평가 완료 → EVALUATION_COMPLETED 이벤트 발행
    → WebSocket Push: 프론트엔드에 결과 전달
    → 리포트 서비스: 평가 결과 누적
"""

import logging
from typing import Optional

from events import EventType, Event
from event_bus import EventBus

logger = logging.getLogger("event_handlers")


def register_all_handlers(bus: EventBus):
    """
    모든 이벤트 핸들러를 EventBus에 등록합니다.
    서버 시작 시 한 번 호출됩니다.
    """
    logger.info("[EventHandlers] 이벤트 핸들러 등록 시작...")
    _register_session_handlers(bus)
    _register_interview_handlers(bus)
    _register_evaluation_handlers(bus)
    _register_emotion_handlers(bus)
    _register_stt_tts_handlers(bus)
    _register_resume_handlers(bus)
    _register_report_handlers(bus)
    _register_coding_handlers(bus)
    _register_system_handlers(bus)
    logger.info("[EventHandlers] 이벤트 핸들러 등록 완료 (%d 타입)", len(bus.get_registered_events()))


# ========== 세션 라이프사이클 핸들러 ==========

def _register_session_handlers(bus: EventBus):

    @bus.on(EventType.SESSION_CREATED)
    async def on_session_created(event: Event):
        """세션 생성 시 → 초기화 작업"""
        logger.info(
            "[Session] 📌 세션 생성: %s | user=%s",
            event.session_id, event.user_email,
        )
        # 세션 생성 시 Redis에 기본 상태 저장 가능
        # (현재는 InterviewState에서 관리, 추후 Redis 기반으로 전환 가능)

    @bus.on(EventType.SESSION_ENDED)
    async def on_session_ended(event: Event):
        """세션 종료 시 → 리포트 생성 워크플로우 트리거"""
        logger.info("[Session] 🏁 세션 종료: %s", event.session_id)
        try:
            from celery_tasks import complete_interview_workflow_task
            task = complete_interview_workflow_task.delay(event.session_id)
            await bus.publish(
                EventType.REPORT_GENERATION_STARTED,
                session_id=event.session_id,
                data={"task_id": task.id, "trigger": "session_ended"},
                source="event_handler",
            )
        except ImportError:
            logger.warning("[Session] Celery 태스크 import 실패 — 리포트 생성 스킵")
        except Exception as e:
            logger.error("[Session] 리포트 워크플로우 시작 실패: %s", e)


# ========== 면접 진행 핸들러 ==========

def _register_interview_handlers(bus: EventBus):

    @bus.on(EventType.ANSWER_SUBMITTED)
    async def on_answer_submitted(event: Event):
        """답변 제출 시 → 비동기 평가 작업 시작"""
        answer = event.data.get("answer", "")
        question = event.data.get("question", "")
        logger.info(
            "[Interview] 📝 답변 제출: session=%s | len=%d",
            event.session_id, len(answer),
        )

        # Celery 비동기 평가 트리거
        try:
            from celery_tasks import evaluate_answer_task
            task = evaluate_answer_task.delay(
                session_id=event.session_id,
                question=question,
                answer=answer,
            )
            await bus.publish(
                EventType.EVALUATION_STARTED,
                session_id=event.session_id,
                data={"task_id": task.id, "question": question[:100]},
                source="event_handler",
            )
        except ImportError:
            logger.debug("[Interview] Celery 미사용 — 평가 이벤트 스킵")
        except Exception as e:
            logger.error("[Interview] 평가 태스크 시작 실패: %s", e)

    @bus.on(EventType.QUESTION_GENERATED)
    async def on_question_generated(event: Event):
        """질문 생성 시 → TTS 프리페칭, 로깅"""
        question = event.data.get("question", "")
        logger.info(
            "[Interview] 🎤 질문 생성: session=%s | q=%s",
            event.session_id, question[:80],
        )

    @bus.on(EventType.TURN_STARTED)
    async def on_turn_started(event: Event):
        """사용자 턴 시작 시 → 개입 타이머 시작"""
        logger.debug("[Interview] ▶ 턴 시작: session=%s", event.session_id)

    @bus.on(EventType.TURN_ENDED)
    async def on_turn_ended(event: Event):
        """사용자 턴 종료 시 → 개입 타이머 정지"""
        logger.debug("[Interview] ⏹ 턴 종료: session=%s", event.session_id)


# ========== 평가 핸들러 ==========

def _register_evaluation_handlers(bus: EventBus):

    @bus.on(EventType.EVALUATION_COMPLETED)
    async def on_evaluation_completed(event: Event):
        """평가 완료 → WebSocket으로 프론트엔드에 실시간 알림"""
        score = event.data.get("score")
        logger.info(
            "[Evaluation] ✅ 평가 완료: session=%s | score=%s",
            event.session_id, score,
        )
        # WebSocket 브로드캐스트는 EventBus.publish()에서 자동 처리됨

    @bus.on(EventType.BATCH_EVALUATION_COMPLETED)
    async def on_batch_evaluation_completed(event: Event):
        """배치 평가 완료 → 리포트 생성 가능 알림"""
        logger.info(
            "[Evaluation] ✅ 배치 평가 완료: session=%s | count=%s",
            event.session_id, event.data.get("evaluated_count"),
        )


# ========== 감정 분석 핸들러 ==========

def _register_emotion_handlers(bus: EventBus):

    @bus.on(EventType.EMOTION_ANALYZED)
    async def on_emotion_analyzed(event: Event):
        """감정 분석 완료 → 개입 시스템에 전달"""
        dominant = event.data.get("dominant_emotion")
        confidence = event.data.get("confidence", 0)
        logger.debug(
            "[Emotion] 😊 감정 분석: session=%s | %s (%.2f)",
            event.session_id, dominant, confidence,
        )

        # 극단적 감정 감지 시 알림 이벤트 발행
        negative_emotions = {"angry", "fear", "sad", "disgust"}
        if dominant in negative_emotions and confidence > 0.7:
            await bus.publish(
                EventType.EMOTION_ALERT,
                session_id=event.session_id,
                data={
                    "alert_type": "negative_emotion",
                    "emotion": dominant,
                    "confidence": confidence,
                    "message": f"면접자가 {dominant} 감정을 강하게 표현하고 있습니다.",
                },
                source="emotion_handler",
            )

    @bus.on(EventType.EMOTION_ALERT)
    async def on_emotion_alert(event: Event):
        """감정 알림 → 개입 시스템 연동"""
        logger.warning(
            "[Emotion] ⚠️ 감정 알림: session=%s | %s",
            event.session_id, event.data.get("message"),
        )

    # ── Hume Prosody 음성 감정 핸들러 ──

    @bus.on(EventType.PROSODY_ANALYZED)
    async def on_prosody_analyzed(event: Event):
        """Prosody 분석 완료 → 적응 모드 결정 보조"""
        dominant = event.data.get("dominant_indicator", "")
        mode = event.data.get("adaptive_mode", "normal")
        logger.debug(
            "[Prosody] 🎵 음성 감정 분석: session=%s | %s (mode=%s)",
            event.session_id, dominant, mode,
        )
        # 불안·긴장 높으면 알림
        indicators = event.data.get("indicators", {})
        anxiety = indicators.get("anxiety", 0)
        if anxiety > 0.6:
            await bus.publish(
                EventType.PROSODY_ALERT,
                session_id=event.session_id,
                data={
                    "alert_type": "high_anxiety",
                    "anxiety_score": anxiety,
                    "message": f"면접자의 음성에서 높은 긴장/불안({anxiety:.0%})이 감지되었습니다.",
                },
                source="prosody_handler",
            )

    @bus.on(EventType.PROSODY_ALERT)
    async def on_prosody_alert(event: Event):
        """Prosody 알림 → 개입 시스템 연동"""
        logger.warning(
            "[Prosody] ⚠️ 음성 감정 알림: session=%s | %s",
            event.session_id, event.data.get("message"),
        )


# ========== STT / TTS 핸들러 ==========

def _register_stt_tts_handlers(bus: EventBus):

    @bus.on(EventType.STT_TRANSCRIBED)
    async def on_stt_transcribed(event: Event):
        """STT 완료 → 전사 결과 기록"""
        transcript = event.data.get("transcript", "")
        logger.debug(
            "[STT] 🎙 전사 완료: session=%s | len=%d",
            event.session_id, len(transcript),
        )

    @bus.on(EventType.TTS_GENERATED)
    async def on_tts_generated(event: Event):
        """TTS 생성 완료 → 오디오 준비 알림"""
        logger.debug(
            "[TTS] 🔊 TTS 생성: session=%s | duration=%.1fs",
            event.session_id, event.data.get("duration", 0),
        )

    @bus.on(EventType.TTS_PREFETCHED)
    async def on_tts_prefetched(event: Event):
        """TTS 프리페치 완료 → 캐시 상태 업데이트"""
        logger.debug("[TTS] 💾 프리페치 완료: session=%s", event.session_id)


# ========== 이력서 / RAG 핸들러 ==========

def _register_resume_handlers(bus: EventBus):

    @bus.on(EventType.RESUME_UPLOADED)
    async def on_resume_uploaded(event: Event):
        """이력서 업로드 → RAG 인덱싱 트리거"""
        logger.info(
            "[Resume] 📄 이력서 업로드: session=%s | file=%s",
            event.session_id, event.data.get("filename"),
        )

    @bus.on(EventType.RESUME_INDEXED)
    async def on_resume_indexed(event: Event):
        """이력서 인덱싱 완료 → 면접 시작 가능 알림"""
        chunk_count = event.data.get("chunk_count", 0)
        logger.info(
            "[Resume] ✅ 인덱싱 완료: session=%s | chunks=%d",
            event.session_id, chunk_count,
        )


# ========== 리포트 핸들러 ==========

def _register_report_handlers(bus: EventBus):

    @bus.on(EventType.REPORT_GENERATED)
    async def on_report_generated(event: Event):
        """리포트 생성 완료 → 프론트엔드 알림"""
        logger.info(
            "[Report] 📊 리포트 생성 완료: session=%s",
            event.session_id,
        )
        # WebSocket을 통해 프론트엔드에 리포트 준비 알림이 자동 전송됨


# ========== 코딩 테스트 핸들러 ==========

def _register_coding_handlers(bus: EventBus):

    @bus.on(EventType.CODING_PROBLEM_GENERATED)
    async def on_coding_problem_generated(event: Event):
        """코딩 문제 생성 완료"""
        logger.info(
            "[Coding] 💻 문제 생성: session=%s | title=%s",
            event.session_id, event.data.get("title"),
        )

    @bus.on(EventType.CODING_ANALYZED)
    async def on_coding_analyzed(event: Event):
        """코딩 분석 완료 → 결과 WebSocket 전송"""
        logger.info(
            "[Coding] ✅ 코드 분석 완료: session=%s | score=%s",
            event.session_id, event.data.get("score"),
        )


# ========== 시스템 핸들러 ==========

def _register_system_handlers(bus: EventBus):

    @bus.on(EventType.ERROR_OCCURRED)
    async def on_error(event: Event):
        """시스템 에러 발생"""
        logger.error(
            "[System] ❌ 에러 발생: source=%s | error=%s",
            event.source, event.data.get("error"),
        )

    @bus.on(EventType.SERVICE_STATUS_CHANGED)
    async def on_service_status(event: Event):
        """서비스 상태 변경"""
        logger.info(
            "[System] 🔄 서비스 상태: %s → %s",
            event.data.get("service"), event.data.get("status"),
        )
