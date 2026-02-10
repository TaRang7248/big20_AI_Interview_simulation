"""
시선 추적 분석 서비스 (Gaze Tracking Service)
=============================================
REQ-F-006 구현: 시선 처리(Eye Contact) 분석

기능:
  - DeepFace 분석 프레임에서 얼굴 영역 기반 시선 방향 추정
  - 정면 응시(카메라 = 면접관) 비율 계산
  - 턴별 / 세션 전체 시선 통계 집계

원리:
  DeepFace 결과의 face region(x, y, w, h)을 사용하여
  프레임 중앙 대비 얼굴 위치로 시선 방향을 추정합니다.
  (정밀 eye-gaze 모델 대신 가벼운 휴리스틱 사용)

  - 얼굴이 프레임 중앙 20% 내 → "center" (정면 응시)
  - 얼굴이 왼쪽/오른쪽으로 치우침 → "left" / "right"
  - 얼굴이 위/아래로 치우침 → "up" / "down"
  - 얼굴 미감지 → "away" (시선 이탈)
"""

from __future__ import annotations

import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ========== 데이터 클래스 ==========

@dataclass
class GazeSample:
    """단일 시선 샘플"""
    timestamp: float
    direction: str        # "center", "left", "right", "up", "down", "away"
    face_center_x: float  # 정규화 좌표 (0-1)
    face_center_y: float  # 정규화 좌표 (0-1)
    is_eye_contact: bool   # 정면 응시 여부


@dataclass
class GazeTurnStats:
    """단일 턴의 시선 통계"""
    turn_index: int
    total_samples: int = 0
    center_count: int = 0      # 정면 응시 횟수
    left_count: int = 0
    right_count: int = 0
    up_count: int = 0
    down_count: int = 0
    away_count: int = 0        # 시선 이탈 (얼굴 미감지)
    eye_contact_ratio: float = 0.0  # 정면 응시 비율 (0-1)


@dataclass
class SessionGazeStats:
    """세션 전체 시선 통계"""
    session_id: str
    total_samples: int = 0
    eye_contact_ratio: float = 0.0          # 전체 정면 응시 비율
    eye_contact_grade: str = ""             # 시선 등급
    eye_contact_assessment: str = ""        # 종합 평가
    direction_distribution: Dict[str, float] = field(default_factory=dict)
    away_ratio: float = 0.0                 # 시선 이탈 비율
    consistency_score: float = 0.0          # 시선 안정성 (0-1)
    turn_details: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_samples": self.total_samples,
            "eye_contact_ratio": round(self.eye_contact_ratio, 3),
            "eye_contact_percentage": f"{self.eye_contact_ratio * 100:.1f}%",
            "eye_contact_grade": self.eye_contact_grade,
            "eye_contact_assessment": self.eye_contact_assessment,
            "direction_distribution": {
                k: round(v, 3) for k, v in self.direction_distribution.items()
            },
            "away_ratio": round(self.away_ratio, 3),
            "consistency_score": round(self.consistency_score, 3),
            "turn_details": self.turn_details,
        }


# ========== 등급 계산 ==========

def grade_eye_contact(ratio: float) -> Tuple[str, str]:
    """정면 응시 비율 기반 시선 등급 및 평가.
    
    면접 적정 정면 응시 비율: 60-80%
    (100% 응시는 부자연스러움)
    """
    if ratio == 0:
        return "N/A", "시선 데이터가 부족합니다."
    elif 0.60 <= ratio <= 0.85:
        return "S", f"정면 응시 {ratio:.0%} — 매우 적절한 시선 처리입니다. 면접관과의 자연스러운 아이컨택을 유지하고 있습니다."
    elif 0.50 <= ratio < 0.60 or 0.85 < ratio <= 0.95:
        return "A", f"정면 응시 {ratio:.0%} — 양호한 시선 처리입니다. {'조금 더 면접관을 바라보면' if ratio < 0.60 else '가끔 시선을 자연스럽게 돌리면'} 더 좋겠습니다."
    elif 0.35 <= ratio < 0.50 or ratio > 0.95:
        return "B", f"정면 응시 {ratio:.0%} — {'시선이 자주 흔들립니다.' if ratio < 0.50 else '시선이 고정되어 부자연스러울 수 있습니다.'}"
    elif 0.20 <= ratio < 0.35:
        return "C", f"정면 응시 {ratio:.0%} — 시선 이탈이 잦아 자신감 부족으로 보일 수 있습니다. 카메라를 더 자주 바라보세요."
    else:
        return "D", f"정면 응시 {ratio:.0%} — 면접관과의 아이컨택이 매우 부족합니다. 카메라 렌즈를 면접관이라 생각하고 바라보는 연습이 필요합니다."


# ========== 시선 방향 추정 ==========

def estimate_gaze_direction(
    face_x: float, face_y: float, face_w: float, face_h: float,
    frame_width: int, frame_height: int,
    center_threshold: float = 0.20,
) -> Tuple[str, float, float, bool]:
    """얼굴 영역으로 시선 방향을 추정합니다.
    
    Args:
        face_x, face_y, face_w, face_h: 얼굴 바운딩 박스 (픽셀)
        frame_width, frame_height: 프레임 크기
        center_threshold: 중앙으로 판정할 범위 (0-0.5)
    
    Returns:
        (direction, norm_cx, norm_cy, is_eye_contact)
    """
    # 얼굴 중심의 정규화 좌표 (0~1)
    cx = (face_x + face_w / 2) / frame_width
    cy = (face_y + face_h / 2) / frame_height
    
    # 중심(0.5)으로부터의 편차
    dx = cx - 0.5
    dy = cy - 0.5
    
    if abs(dx) <= center_threshold and abs(dy) <= center_threshold:
        return "center", cx, cy, True
    
    # 가장 큰 편차 방향으로 분류
    if abs(dx) > abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"
    
    return direction, cx, cy, False


# ========== 메인 서비스 클래스 ==========

class GazeTrackingService:
    """세션별 시선 추적 분석 서비스
    
    사용법:
        service = GazeTrackingService()
        service.start_turn(session_id, 0)
        service.add_face_detection(session_id, face_region, frame_size)
        service.end_turn(session_id)
        stats = service.get_session_stats(session_id)
    """
    
    def __init__(self, center_threshold: float = 0.20):
        self._center_threshold = center_threshold
        self._sessions: Dict[str, List[GazeTurnStats]] = {}
        self._active_turns: Dict[str, int] = {}  # session_id -> turn_index
        self._turn_samples: Dict[str, List[GazeSample]] = {}
    
    def start_turn(self, session_id: str, turn_index: int = -1) -> None:
        """시선 추적 턴 시작"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        if turn_index < 0:
            turn_index = len(self._sessions[session_id])
        self._active_turns[session_id] = turn_index
        self._turn_samples[session_id] = []
    
    def add_face_detection(
        self,
        session_id: str,
        face_region: Optional[Dict],
        frame_width: int = 640,
        frame_height: int = 480,
    ) -> Optional[GazeSample]:
        """DeepFace 분석 결과에서 시선 샘플 추가.
        
        Args:
            face_region: DeepFace 결과의 "region" 딕셔너리
                         {"x": int, "y": int, "w": int, "h": int}
                         None이면 얼굴 미감지 → "away"
        """
        if session_id not in self._active_turns:
            return None
        
        if face_region and face_region.get("w", 0) > 0:
            direction, cx, cy, is_contact = estimate_gaze_direction(
                face_region["x"], face_region["y"],
                face_region["w"], face_region["h"],
                frame_width, frame_height,
                self._center_threshold,
            )
        else:
            # 얼굴 미감지
            direction, cx, cy, is_contact = "away", 0.0, 0.0, False
        
        sample = GazeSample(
            timestamp=time.time(),
            direction=direction,
            face_center_x=cx,
            face_center_y=cy,
            is_eye_contact=is_contact,
        )
        self._turn_samples.setdefault(session_id, []).append(sample)
        return sample
    
    def end_turn(self, session_id: str) -> Optional[GazeTurnStats]:
        """시선 추적 턴 종료"""
        turn_idx = self._active_turns.pop(session_id, None)
        if turn_idx is None:
            return None
        
        samples = self._turn_samples.pop(session_id, [])
        
        turn_stats = GazeTurnStats(turn_index=turn_idx, total_samples=len(samples))
        if not samples:
            self._sessions.setdefault(session_id, []).append(turn_stats)
            return turn_stats
        
        for s in samples:
            if s.direction == "center":
                turn_stats.center_count += 1
            elif s.direction == "left":
                turn_stats.left_count += 1
            elif s.direction == "right":
                turn_stats.right_count += 1
            elif s.direction == "up":
                turn_stats.up_count += 1
            elif s.direction == "down":
                turn_stats.down_count += 1
            else:
                turn_stats.away_count += 1
        
        turn_stats.eye_contact_ratio = turn_stats.center_count / turn_stats.total_samples
        
        self._sessions.setdefault(session_id, []).append(turn_stats)
        return turn_stats
    
    def get_session_stats(self, session_id: str) -> SessionGazeStats:
        """세션 전체 시선 통계 집계"""
        turns = self._sessions.get(session_id, [])
        stats = SessionGazeStats(session_id=session_id)
        
        if not turns:
            stats.eye_contact_assessment = "시선 데이터가 없습니다."
            return stats
        
        total = sum(t.total_samples for t in turns)
        stats.total_samples = total
        
        if total == 0:
            stats.eye_contact_assessment = "시선 데이터가 부족합니다."
            return stats
        
        # 전체 방향 분포
        center_total = sum(t.center_count for t in turns)
        left_total = sum(t.left_count for t in turns)
        right_total = sum(t.right_count for t in turns)
        up_total = sum(t.up_count for t in turns)
        down_total = sum(t.down_count for t in turns)
        away_total = sum(t.away_count for t in turns)
        
        stats.eye_contact_ratio = center_total / total
        stats.away_ratio = away_total / total
        stats.direction_distribution = {
            "center": center_total / total,
            "left": left_total / total,
            "right": right_total / total,
            "up": up_total / total,
            "down": down_total / total,
            "away": away_total / total,
        }
        
        # 시선 안정성: 턴별 정면 응시 비율의 일관성
        ratios = [t.eye_contact_ratio for t in turns if t.total_samples > 0]
        if len(ratios) > 1:
            std = statistics.stdev(ratios)
            stats.consistency_score = max(0.0, 1.0 - std)  # 표준편차 낮을수록 안정적
        elif ratios:
            stats.consistency_score = 1.0
        
        # 등급 및 평가
        stats.eye_contact_grade, stats.eye_contact_assessment = grade_eye_contact(
            stats.eye_contact_ratio
        )
        
        # 턴별 상세
        stats.turn_details = [
            {
                "turn": t.turn_index + 1,
                "samples": t.total_samples,
                "eye_contact_ratio": round(t.eye_contact_ratio, 3),
                "center": t.center_count,
                "away": t.away_count,
            }
            for t in turns
        ]
        
        return stats
    
    def clear_session(self, session_id: str) -> None:
        """세션 데이터 정리"""
        self._sessions.pop(session_id, None)
        self._active_turns.pop(session_id, None)
        self._turn_samples.pop(session_id, None)
