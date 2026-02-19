"""
Celery 애플리케이션 설정
========================
Redis를 브로커 및 결과 백엔드로 사용하여
AI 면접 시스템의 비동기 작업을 처리합니다.

실행 방법:
    # Worker 시작 (Windows)
    celery -A celery_app worker --pool=solo --loglevel=info

    # Worker 시작 (Linux/Mac - 여러 프로세스)
    celery -A celery_app worker --concurrency=4 --loglevel=info

    # Flower 모니터링 (선택사항)
    celery -A celery_app flower --port=5555
"""

import os

from celery import Celery
from dotenv import load_dotenv
from kombu import Exchange, Queue

load_dotenv()

# Redis 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery 앱 생성
celery_app = Celery(
    "ai_interview",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["celery_tasks"],  # 태스크 모듈
)

# Celery 설정
celery_app.conf.update(
    # 직렬화 설정
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # 시간대 설정
    timezone="Asia/Seoul",
    enable_utc=True,
    # 작업 설정
    task_track_started=True,
    task_time_limit=300,  # 5분 타임아웃
    task_soft_time_limit=240,  # 4분 소프트 타임아웃
    # 재시도 설정
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=10,  # 10초 후 재시도
    task_max_retries=3,
    # 결과 설정
    result_expires=3600,  # 1시간 후 결과 만료
    result_extended=True,
    # Worker 설정
    worker_prefetch_multiplier=1,  # 한 번에 하나의 작업만 가져옴
    worker_concurrency=4,  # 기본 동시 작업 수
    # 큐 설정
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("llm_evaluation", Exchange("llm"), routing_key="llm.#"),
        Queue("emotion_analysis", Exchange("emotion"), routing_key="emotion.#"),
        Queue("report_generation", Exchange("report"), routing_key="report.#"),
        Queue("tts_generation", Exchange("tts"), routing_key="tts.#"),
        Queue("rag_processing", Exchange("rag"), routing_key="rag.#"),
        Queue("question_generation", Exchange("question"), routing_key="question.#"),
        Queue("media_processing", Exchange("media"), routing_key="media.#"),
    ),
    # 라우팅 설정
    task_routes={
        "celery_tasks.evaluate_answer_task": {"queue": "llm_evaluation"},
        "celery_tasks.analyze_emotion_task": {"queue": "emotion_analysis"},
        "celery_tasks.generate_report_task": {"queue": "report_generation"},
        "celery_tasks.generate_tts_task": {"queue": "tts_generation"},
        "celery_tasks.process_resume_task": {"queue": "rag_processing"},
        "celery_tasks.batch_evaluate_task": {"queue": "llm_evaluation"},
        "celery_tasks.prefetch_tts_task": {"queue": "tts_generation"},
        "celery_tasks.generate_question_task": {"queue": "question_generation"},
        "celery_tasks.save_session_to_redis_task": {"queue": "default"},
        "celery_tasks.batch_emotion_analysis_task": {"queue": "emotion_analysis"},
        "celery_tasks.complete_interview_workflow_task": {"queue": "report_generation"},
        "celery_tasks.transcode_recording_task": {"queue": "media_processing"},
        "celery_tasks.cleanup_recording_task": {"queue": "media_processing"},
        "celery_tasks.pre_generate_coding_problem_task": {"queue": "llm_evaluation"},
    },
    # 로깅 설정
    worker_hijack_root_logger=False,
)

# Beat 스케줄 설정 (주기적 작업용)
celery_app.conf.beat_schedule = {
    # 매 5분마다 만료된 세션 정리
    "cleanup-expired-sessions": {
        "task": "celery_tasks.cleanup_sessions_task",
        "schedule": 300.0,  # 5분
    },
    # 매 1시간마다 통계 집계
    "aggregate-statistics": {
        "task": "celery_tasks.aggregate_statistics_task",
        "schedule": 3600.0,  # 1시간
    },
}


# Celery 상태 확인 함수
def check_celery_status():
    """Celery 연결 상태 확인"""
    try:
        # 브로커 연결 확인
        celery_app.control.ping(timeout=1)
        return {"status": "connected", "broker": CELERY_BROKER_URL}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


if __name__ == "__main__":
    # 테스트용 실행
    status = check_celery_status()
    print(f"Celery Status: {status}")
