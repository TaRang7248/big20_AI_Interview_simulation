"""
이벤트 버스 모듈 (Event Bus)
============================
Redis Pub/Sub 기반 이벤트 버스 + 인프로세스 비동기 이벤트 디스패처

SAD 설계서의 "이벤트 기반 마이크로서비스" 패턴 구현:
- Redis Pub/Sub: 프로세스 간 이벤트 전파 (API 서버 ↔ Celery Worker)
- AsyncIO 로컬 디스패처: 동일 프로세스 내 비동기 이벤트 핸들링
- WebSocket 브로드캐스트: 프론트엔드 실시간 푸시

구조:
  Publisher ─→ EventBus ─→ Redis Pub/Sub  ─→ 다른 프로세스 (Celery Worker)
                  │
                  └─→ Local Handlers ─→ 같은 프로세스 내 서비스
                  │
                  └─→ WebSocket Push ─→ 프론트엔드
"""

import asyncio
import json
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union
from datetime import datetime

from events import Event, EventType, EventFactory

logger = logging.getLogger("event_bus")
logger.setLevel(logging.INFO)


# ========== 이벤트 핸들러 타입 ==========
# 동기 핸들러:  def handler(event: Event) -> None
# 비동기 핸들러: async def handler(event: Event) -> None
EventHandler = Union[Callable[[Event], None], Callable[[Event], Coroutine]]


class EventBus:
    """
    Redis Pub/Sub + 로컬 비동기 이벤트 버스

    사용법:
        bus = EventBus.get_instance()

        # 이벤트 구독
        @bus.on(EventType.SESSION_CREATED)
        async def on_session_created(event):
            print(f"세션 생성: {event.session_id}")

        # 이벤트 발행
        await bus.publish(EventType.SESSION_CREATED, session_id="abc", data={...})
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __init__(self):
        # 로컬 핸들러 레지스트리: EventType -> [handler, ...]
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        # 와일드카드 핸들러 (모든 이벤트 수신)
        self._global_handlers: List[EventHandler] = []
        # Redis 연결
        self._redis = None
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None
        # WebSocket 연결 관리: session_id -> set of websocket connections
        self._ws_connections: Dict[str, Set] = defaultdict(set)
        # 이벤트 히스토리 (디버깅용, 최근 N개)
        self._history: List[Dict] = []
        self._max_history = 500
        # 채널 이름 접두사
        self._channel_prefix = "interview_events"
        # 실행 상태
        self._running = False
        # 이벤트 통계
        self._stats: Dict[str, int] = defaultdict(int)

    @classmethod
    def get_instance(cls) -> "EventBus":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ========== 초기화 / 종료 ==========

    async def initialize(self, redis_url: str = "redis://localhost:6379/0"):
        """Redis 연결 초기화 및 Pub/Sub 리스너 시작"""
        if self._running:
            return

        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                redis_url,
                decode_responses=True,
                max_connections=10,
            )
            await self._redis.ping()
            logger.info("[EventBus] Redis 연결 성공: %s", redis_url)

            # Pub/Sub 리스너 시작
            self._pubsub = self._redis.pubsub()
            await self._pubsub.psubscribe(f"{self._channel_prefix}:*")
            self._listener_task = asyncio.create_task(self._listen_redis())
            self._running = True
            logger.info("[EventBus] Redis Pub/Sub 리스너 시작")

        except ImportError:
            logger.warning("[EventBus] redis.asyncio 미설치 — 로컬 모드로 동작")
            self._running = True
        except Exception as e:
            logger.warning("[EventBus] Redis 연결 실패 (%s) — 로컬 모드로 동작", e)
            self._running = True

    async def shutdown(self):
        """이벤트 버스 종료"""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.punsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("[EventBus] 종료 완료")

    # ========== 이벤트 구독 ==========

    def on(self, event_type: Union[EventType, str]) -> Callable:
        """
        데코레이터: 이벤트 핸들러 등록

        @bus.on(EventType.SESSION_CREATED)
        async def handle_session_created(event: Event):
            ...
        """
        def decorator(handler: EventHandler) -> EventHandler:
            key = event_type.value if isinstance(event_type, EventType) else event_type
            self._handlers[key].append(handler)
            logger.debug("[EventBus] 핸들러 등록: %s -> %s", key, handler.__name__)
            return handler
        return decorator

    def subscribe(self, event_type: Union[EventType, str], handler: EventHandler):
        """명시적 이벤트 핸들러 등록"""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._handlers[key].append(handler)

    def subscribe_all(self, handler: EventHandler):
        """모든 이벤트를 수신하는 글로벌 핸들러 등록"""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: Union[EventType, str], handler: EventHandler):
        """핸들러 제거"""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        if key in self._handlers:
            self._handlers[key] = [h for h in self._handlers[key] if h != handler]

    # ========== 이벤트 발행 ==========

    async def publish(
        self,
        event_type: EventType,
        session_id: Optional[str] = None,
        user_email: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        broadcast_ws: bool = True,
        propagate_redis: bool = True,
        **kwargs,
    ) -> Event:
        """
        이벤트 발행

        Args:
            event_type: 이벤트 타입
            session_id: 관련 세션 ID
            user_email: 관련 사용자 이메일
            data: 이벤트 페이로드
            source: 발행 서비스명
            broadcast_ws: WebSocket으로 프론트엔드에 푸시 여부
            propagate_redis: Redis Pub/Sub로 다른 프로세스에 전파 여부
        """
        # 이벤트 객체 생성
        event = EventFactory.create(
            event_type=event_type,
            session_id=session_id,
            user_email=user_email,
            data=data,
            source=source,
            **kwargs,
        )

        # 통계 기록
        self._stats[event.event_type] += 1

        # 히스토리 기록
        self._record_history(event)

        logger.info(
            "[EventBus] 📤 PUBLISH: %s | session=%s | source=%s",
            event.event_type, event.session_id, event.source,
        )

        # 1) 로컬 핸들러 디스패치 (비동기)
        await self._dispatch_local(event)

        # 2) Redis Pub/Sub 전파
        if propagate_redis and self._redis:
            await self._publish_redis(event)

        # 3) WebSocket 브로드캐스트
        if broadcast_ws and event.session_id:
            await self._broadcast_ws(event)

        return event

    def publish_sync(
        self,
        event_type: EventType,
        session_id: Optional[str] = None,
        user_email: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
    ):
        """
        동기 컨텍스트에서 이벤트 발행 (Celery 태스크 내부에서 사용)
        Redis에만 발행하고, 수신 측에서 로컬 디스패치 처리
        """
        event = EventFactory.create(
            event_type=event_type,
            session_id=session_id,
            user_email=user_email,
            data=data,
            source=source,
        )

        try:
            import redis
            r = redis.from_url("redis://localhost:6379/0", decode_responses=True)
            channel = f"{self._channel_prefix}:{event.event_type}"
            r.publish(channel, event.json())
            r.close()
            logger.info(
                "[EventBus] 📤 PUBLISH_SYNC: %s | session=%s",
                event.event_type, event.session_id,
            )
        except Exception as e:
            logger.warning("[EventBus] 동기 발행 실패: %s", e)

        return event

    # ========== WebSocket 관리 ==========

    def register_ws(self, session_id: str, websocket):
        """WebSocket 연결 등록"""
        self._ws_connections[session_id].add(websocket)
        logger.debug("[EventBus] WS 등록: session=%s (총 %d)", session_id, len(self._ws_connections[session_id]))

    def unregister_ws(self, session_id: str, websocket):
        """WebSocket 연결 해제"""
        self._ws_connections[session_id].discard(websocket)
        if not self._ws_connections[session_id]:
            del self._ws_connections[session_id]

    async def _broadcast_ws(self, event: Event):
        """세션의 모든 WebSocket 연결에 이벤트 전송"""
        if not event.session_id or event.session_id not in self._ws_connections:
            return

        message = {
            "type": "event",
            "event_type": event.event_type,
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "source": event.source,
            "data": event.data,
        }
        payload = json.dumps(message, ensure_ascii=False)

        dead_connections = []
        for ws in self._ws_connections[event.session_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.append(ws)

        # 죽은 연결 정리
        for ws in dead_connections:
            self._ws_connections[event.session_id].discard(ws)

    # ========== 내부 메서드 ==========

    async def _dispatch_local(self, event: Event):
        """로컬 핸들러에 이벤트 디스패치"""
        handlers = list(self._handlers.get(event.event_type, []))
        handlers.extend(self._global_handlers)

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    "[EventBus] 핸들러 오류: %s -> %s: %s",
                    event.event_type, handler.__name__, e,
                )

    async def _publish_redis(self, event: Event):
        """Redis Pub/Sub에 이벤트 발행"""
        try:
            channel = f"{self._channel_prefix}:{event.event_type}"
            await self._redis.publish(channel, event.json())
        except Exception as e:
            logger.warning("[EventBus] Redis 발행 실패: %s", e)

    async def _listen_redis(self):
        """Redis Pub/Sub 메시지 수신 루프"""
        logger.info("[EventBus] Redis 리스너 시작")
        try:
            while self._running:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "pmessage":
                    try:
                        event_data = json.loads(message["data"])
                        event = Event(**event_data)

                        # 로컬 핸들러 디스패치 (Redis에서 수신한 이벤트)
                        await self._dispatch_local(event)

                        # WebSocket 브로드캐스트
                        if event.session_id:
                            await self._broadcast_ws(event)

                    except Exception as e:
                        logger.warning("[EventBus] Redis 메시지 처리 오류: %s", e)

                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("[EventBus] Redis 리스너 종료")

    def _record_history(self, event: Event):
        """이벤트 히스토리 기록"""
        self._history.append({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "session_id": event.session_id,
            "source": event.source,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    # ========== 조회 / 디버깅 ==========

    def get_stats(self) -> Dict[str, Any]:
        """이벤트 통계 반환"""
        return {
            "total_events": sum(self._stats.values()),
            "by_type": dict(self._stats),
            "registered_handlers": {
                k: len(v) for k, v in self._handlers.items() if v
            },
            "global_handlers": len(self._global_handlers),
            "active_ws_sessions": len(self._ws_connections),
            "active_ws_connections": sum(len(v) for v in self._ws_connections.values()),
            "redis_connected": self._redis is not None,
        }

    def get_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        """이벤트 히스토리 반환"""
        history = self._history
        if event_type:
            history = [h for h in history if h["event_type"] == event_type]
        return history[-limit:]

    def get_registered_events(self) -> List[str]:
        """등록된 이벤트 타입 목록 반환"""
        return sorted(k for k, v in self._handlers.items() if v)
