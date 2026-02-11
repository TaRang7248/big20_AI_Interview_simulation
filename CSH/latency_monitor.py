"""
지연 시간 측정 및 SLA 모니터링 서비스 (REQ-N-001)
=================================================
SRS 요구사항: STT 변환 + LLM 추론을 포함한 전체 응답 지연이 1.5초를 초과하면 안 됨.

역할:
- 모든 API 요청의 응답 시간을 자동 측정 (FastAPI Middleware)
- 핵심 파이프라인(chat) 내부 단계별(Phase) 소요 시간 기록
- SLA(1.5초) 위반 자동 감지 및 로깅
- '/api/monitoring/latency' 대시보드 API 제공
"""

import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# ========== 설정 ==========
# SRS REQ-N-001: 전체 응답 지연 1.5초 이내
SLA_THRESHOLD_SEC = 1.5

# 최근 N개 요청만 메모리에 보관 (메모리 제한)
MAX_HISTORY = 500

# SLA 위반 로그 최대 보관 수
MAX_VIOLATIONS = 200


@dataclass
class LatencyRecord:
    """단일 API 요청의 지연 시간 기록"""
    endpoint: str                     # 요청 경로 (예: "/api/chat")
    method: str                       # HTTP 메서드 (GET, POST 등)
    latency_ms: float                 # 총 응답 시간 (밀리초)
    timestamp: str                    # ISO 형식 타임스탬프
    status_code: int                  # HTTP 상태 코드
    sla_violated: bool                # SLA(1.5초) 위반 여부
    phases: Dict[str, float] = field(default_factory=dict)
    # phases 예: {"rag_retrieval": 120.5, "llm_inference": 890.3, "tts_synthesis": 350.1}


class LatencyMonitor:
    """
    지연 시간 모니터링 서비스 (Thread-Safe)

    사용법:
    1. FastAPI 미들웨어로 자동 측정: 모든 /api/** 요청
    2. 수동 측정: monitor.start_phase() / monitor.end_phase() 로 세부 단계 측정
    3. 대시보드: monitor.get_dashboard() 로 통계 조회
    """

    def __init__(self, sla_threshold: float = SLA_THRESHOLD_SEC):
        self._lock = threading.Lock()
        self.sla_threshold = sla_threshold  # 초 단위

        # 엔드포인트별 지연 시간 기록 (최근 MAX_HISTORY개)
        self._history: deque = deque(maxlen=MAX_HISTORY)

        # SLA 위반 로그
        self._violations: deque = deque(maxlen=MAX_VIOLATIONS)

        # 엔드포인트별 누적 통계
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_ms": 0.0,
            "min_ms": float("inf"),
            "max_ms": 0.0,
            "sla_violations": 0,
        })

        # 진행 중인 단계별 측정 (request_id → {phase_name: start_time})
        self._active_phases: Dict[str, Dict[str, float]] = {}
        # 완료된 단계별 측정 결과 (request_id → {phase_name: elapsed_ms})
        self._completed_phases: Dict[str, Dict[str, float]] = {}

    # ───────── 단계별(Phase) 측정 ─────────

    def start_phase(self, request_id: str, phase_name: str) -> None:
        """특정 단계의 시작 시간을 기록합니다.

        Args:
            request_id: 요청 ID (request.state.request_id 등)
            phase_name: 단계 이름 (예: "rag_retrieval", "llm_inference", "tts_synthesis")
        """
        with self._lock:
            if request_id not in self._active_phases:
                self._active_phases[request_id] = {}
            self._active_phases[request_id][phase_name] = time.perf_counter()

    def end_phase(self, request_id: str, phase_name: str) -> float:
        """특정 단계의 종료 시간을 기록하고 소요 시간을 반환합니다.

        Returns:
            소요 시간 (밀리초), 시작 기록이 없으면 0.0
        """
        with self._lock:
            start = self._active_phases.get(request_id, {}).pop(phase_name, None)
            if start is None:
                return 0.0
            elapsed = (time.perf_counter() - start) * 1000  # ms
            if request_id not in self._completed_phases:
                self._completed_phases[request_id] = {}
            self._completed_phases[request_id][phase_name] = round(elapsed, 2)
            return elapsed

    def get_phases(self, request_id: str) -> Dict[str, float]:
        """완료된 단계별 측정 결과를 가져오고 정리합니다."""
        with self._lock:
            phases = self._completed_phases.pop(request_id, {})
            self._active_phases.pop(request_id, None)
            return phases

    # ───────── 요청 기록 ─────────

    def record(self, endpoint: str, method: str, latency_ms: float,
               status_code: int, request_id: Optional[str] = None) -> LatencyRecord:
        """API 요청 지연 시간을 기록합니다.

        미들웨어에서 자동 호출됩니다.
        """
        sla_violated = (latency_ms / 1000) > self.sla_threshold
        phases = self.get_phases(request_id) if request_id else {}

        record = LatencyRecord(
            endpoint=endpoint,
            method=method,
            latency_ms=round(latency_ms, 2),
            timestamp=datetime.now().isoformat(),
            status_code=status_code,
            sla_violated=sla_violated,
            phases=phases,
        )

        with self._lock:
            self._history.append(record)

            # 엔드포인트별 누적 통계 업데이트
            stat = self._stats[endpoint]
            stat["count"] += 1
            stat["total_ms"] += latency_ms
            stat["min_ms"] = min(stat["min_ms"], latency_ms)
            stat["max_ms"] = max(stat["max_ms"], latency_ms)
            if sla_violated:
                stat["sla_violations"] += 1
                self._violations.append(record)

        # SLA 위반 시 경고 로그 출력
        if sla_violated:
            phase_info = ""
            if phases:
                phase_info = " | " + ", ".join(
                    f"{k}={v:.0f}ms" for k, v in phases.items()
                )
            print(
                f"⚠️ [SLA 위반] {method} {endpoint} → {latency_ms:.0f}ms "
                f"(임계값 {self.sla_threshold * 1000:.0f}ms){phase_info}"
            )

        return record

    # ───────── 대시보드 / 통계 ─────────

    def get_dashboard(self) -> Dict[str, Any]:
        """모니터링 대시보드 데이터를 반환합니다.

        /api/monitoring/latency 엔드포인트에서 사용됩니다.
        """
        with self._lock:
            # 전체 통계
            total_requests = sum(s["count"] for s in self._stats.values())
            total_violations = sum(s["sla_violations"] for s in self._stats.values())

            # 엔드포인트별 통계 집계
            endpoint_stats = {}
            for ep, s in self._stats.items():
                avg_ms = s["total_ms"] / s["count"] if s["count"] > 0 else 0
                endpoint_stats[ep] = {
                    "count": s["count"],
                    "avg_ms": round(avg_ms, 2),
                    "min_ms": round(s["min_ms"], 2) if s["min_ms"] != float("inf") else 0,
                    "max_ms": round(s["max_ms"], 2),
                    "sla_violations": s["sla_violations"],
                    "sla_compliance_pct": round(
                        (1 - s["sla_violations"] / s["count"]) * 100, 1
                    ) if s["count"] > 0 else 100.0,
                }

            # 최근 SLA 위반 내역 (최신 10건)
            recent_violations = [
                {
                    "endpoint": v.endpoint,
                    "method": v.method,
                    "latency_ms": v.latency_ms,
                    "timestamp": v.timestamp,
                    "phases": v.phases,
                }
                for v in list(self._violations)[-10:]
            ]

            # 최근 요청 히스토리 (최신 20건)
            recent_requests = [
                {
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "latency_ms": r.latency_ms,
                    "timestamp": r.timestamp,
                    "status_code": r.status_code,
                    "sla_violated": r.sla_violated,
                    "phases": r.phases,
                }
                for r in list(self._history)[-20:]
            ]

        return {
            "sla_threshold_ms": self.sla_threshold * 1000,
            "summary": {
                "total_requests": total_requests,
                "total_sla_violations": total_violations,
                "sla_compliance_pct": round(
                    (1 - total_violations / total_requests) * 100, 1
                ) if total_requests > 0 else 100.0,
            },
            "endpoint_stats": endpoint_stats,
            "recent_violations": recent_violations,
            "recent_requests": recent_requests,
        }

    def reset(self) -> None:
        """모든 통계를 초기화합니다."""
        with self._lock:
            self._history.clear()
            self._violations.clear()
            self._stats.clear()
            self._active_phases.clear()
            self._completed_phases.clear()


# 전역 싱글톤 인스턴스
latency_monitor = LatencyMonitor()
