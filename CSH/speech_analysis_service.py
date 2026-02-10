"""
발화 분석 서비스 (Speech Analysis Service)
==========================================
REQ-F-006 구현: 발화 속도 및 발음 명확성 측정

기능:
  - 발화 속도(WPM, 분당 음절 수) 측정
  - 발음 명확성 (STT confidence 기반) 측정
  - 턴별 / 세션 전체 통계 집계
  - 실시간 WebSocket 이벤트 push

데이터 소스:
  - Deepgram STT의 words 배열 (단어별 start/end/confidence)
  - InterventionManager의 턴 시작/종료 시간
"""

from __future__ import annotations

import re
import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ========== 한국어 음절 수 계산 ==========

def count_syllables_ko(text: str) -> int:
    """한국어 텍스트의 음절 수를 계산합니다.
    
    한국어: 한글 문자 1자 = 1음절
    영어: 모음 그룹으로 추정
    """
    hangul = len(re.findall(r'[가-힣]', text))
    # 영어 단어의 음절 추정 (모음 클러스터 기반)
    english_words = re.findall(r'[a-zA-Z]+', text)
    english_syllables = 0
    for word in english_words:
        vowels = len(re.findall(r'[aeiouAEIOU]+', word))
        english_syllables += max(vowels, 1)
    return hangul + english_syllables


def count_words_ko(text: str) -> int:
    """한국어 텍스트의 어절(단어) 수를 계산합니다."""
    tokens = text.strip().split()
    return len(tokens)


# ========== 데이터 클래스 ==========

@dataclass
class SpeechTurnMetrics:
    """단일 답변 턴의 발화 측정값"""
    turn_index: int
    start_time: float          # 턴 시작 (epoch)
    end_time: float = 0.0      # 턴 종료 (epoch)
    text: str = ""             # 최종 인식 텍스트
    word_count: int = 0        # 어절 수
    syllable_count: int = 0    # 음절 수
    duration_seconds: float = 0.0  # 발화 시간(초)
    speech_rate_spm: float = 0.0   # 분당 음절 수 (Syllables Per Minute)
    speech_rate_wpm: float = 0.0   # 분당 어절 수 (Words Per Minute)
    avg_confidence: float = 0.0    # 평균 STT confidence
    word_confidences: List[float] = field(default_factory=list)
    filler_count: int = 0          # 필러(음... 어...) 횟수
    pause_count: int = 0           # 1초 이상 침묵 횟수
    pause_durations: List[float] = field(default_factory=list)  # 침묵 지속시간 목록


@dataclass
class SessionSpeechStats:
    """세션 전체 발화 통계"""
    session_id: str
    total_turns: int = 0
    total_duration_seconds: float = 0.0
    total_syllables: int = 0
    total_words: int = 0
    avg_speech_rate_spm: float = 0.0     # 평균 분당 음절 수
    avg_speech_rate_wpm: float = 0.0     # 평균 분당 어절 수
    speech_rate_consistency: float = 0.0  # 발화 속도 일관성 (표준편차가 낮을수록 일관)
    avg_confidence: float = 0.0           # 평균 발음 명확성
    pronunciation_grade: str = ""         # 발음 등급 (S/A/B/C/D)
    speech_rate_grade: str = ""           # 발화 속도 등급
    total_fillers: int = 0                # 총 필러 횟수
    total_pauses: int = 0                 # 총 침묵 횟수
    avg_pause_duration: float = 0.0       # 평균 침묵 시간
    speech_rate_assessment: str = ""      # 종합 평가 텍스트
    pronunciation_assessment: str = ""    # 발음 종합 평가 텍스트
    turn_details: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_turns": self.total_turns,
            "total_duration_seconds": round(self.total_duration_seconds, 1),
            "total_syllables": self.total_syllables,
            "total_words": self.total_words,
            "avg_speech_rate_spm": round(self.avg_speech_rate_spm, 1),
            "avg_speech_rate_wpm": round(self.avg_speech_rate_wpm, 1),
            "speech_rate_consistency": round(self.speech_rate_consistency, 2),
            "avg_confidence": round(self.avg_confidence, 3),
            "pronunciation_grade": self.pronunciation_grade,
            "speech_rate_grade": self.speech_rate_grade,
            "total_fillers": self.total_fillers,
            "total_pauses": self.total_pauses,
            "avg_pause_duration": round(self.avg_pause_duration, 1),
            "speech_rate_assessment": self.speech_rate_assessment,
            "pronunciation_assessment": self.pronunciation_assessment,
            "turn_details": self.turn_details,
        }


# ========== 필러 감지 ==========

# 한국어 필러 (간투사) 패턴
FILLER_PATTERNS = [
    r'\b(음+|어+|아+|으+|에+|그+)\b',
    r'(음\.\.\.|어\.\.\.|아\.\.\.|으\.\.\.)',
    r'\b(저기|그러니까|뭐랄까|있잖아|그니까|솔직히|약간)\b',
]


def count_fillers(text: str) -> int:
    """필러/간투사 횟수 계산"""
    count = 0
    for pattern in FILLER_PATTERNS:
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return count


# ========== 등급 계산 ==========

def grade_speech_rate(spm: float) -> tuple[str, str]:
    """분당 음절 수 기반 발화 속도 등급 및 평가.
    
    한국어 면접 적정 발화 속도: 약 240-320 SPM (분당 음절)
    일반 대화: 200-350 SPM
    """
    if spm == 0:
        return "N/A", "발화 데이터가 부족합니다."
    elif 240 <= spm <= 320:
        return "S", f"분당 {spm:.0f}음절 — 면접에 최적인 발화 속도입니다. 청취자가 이해하기 쉬운 템포를 유지하고 있습니다."
    elif 200 <= spm < 240 or 320 < spm <= 360:
        return "A", f"분당 {spm:.0f}음절 — 양호한 발화 속도입니다. {'조금 더 빠르게' if spm < 240 else '조금 더 천천히'} 말하면 더 좋겠습니다."
    elif 160 <= spm < 200 or 360 < spm <= 400:
        return "B", f"분당 {spm:.0f}음절 — {'다소 느린' if spm < 200 else '다소 빠른'} 편입니다. 면접관이 {'지루함을' if spm < 200 else '내용을 놓칠 수'} 느낄 수 있습니다."
    elif 120 <= spm < 160 or 400 < spm <= 450:
        return "C", f"분당 {spm:.0f}음절 — {'많이 느린' if spm < 160 else '많이 빠른'} 편입니다. 발화 속도 조절이 필요합니다."
    else:
        return "D", f"분당 {spm:.0f}음절 — {'극단적으로 느린' if spm < 120 else '극단적으로 빠른'} 발화 속도입니다. 연습을 통해 적정 속도(240-320 SPM)로 조절해보세요."


def grade_pronunciation(confidence: float) -> tuple[str, str]:
    """STT confidence 기반 발음 명확성 등급 및 평가.
    
    Deepgram confidence:
      0.95+ = 매우 명확
      0.85-0.95 = 양호
      0.75-0.85 = 보통
      0.65-0.75 = 불명확
      <0.65 = 매우 불명확
    """
    if confidence == 0:
        return "N/A", "발음 데이터가 부족합니다."
    elif confidence >= 0.95:
        return "S", f"발음 명확도 {confidence:.1%} — 매우 명확한 발음입니다. 면접관이 내용을 쉽게 이해할 수 있습니다."
    elif confidence >= 0.85:
        return "A", f"발음 명확도 {confidence:.1%} — 양호한 발음입니다. 대부분의 내용이 정확히 전달됩니다."
    elif confidence >= 0.75:
        return "B", f"발음 명확도 {confidence:.1%} — 보통 수준입니다. 일부 단어가 불명확하게 전달될 수 있습니다."
    elif confidence >= 0.65:
        return "C", f"발음 명확도 {confidence:.1%} — 불명확한 부분이 많습니다. 또박또박 말하는 연습이 필요합니다."
    else:
        return "D", f"발음 명확도 {confidence:.1%} — 상당 부분 인식이 어렵습니다. 발음과 발성 훈련을 권장합니다."


# ========== 메인 서비스 클래스 ==========

class SpeechAnalysisService:
    """세션별 발화 분석 서비스
    
    사용법:
        service = SpeechAnalysisService()
        service.start_turn(session_id, turn_index=0)
        service.add_stt_result(session_id, transcript, is_final, confidence, words)
        service.end_turn(session_id, final_text="...")
        stats = service.get_session_stats(session_id)
    """
    
    def __init__(self):
        self._sessions: Dict[str, List[SpeechTurnMetrics]] = {}
        self._active_turns: Dict[str, SpeechTurnMetrics] = {}
        # 턴별 word-level confidence 누적
        self._turn_confidences: Dict[str, List[float]] = {}
        # 턴별 word timestamps (pause 감지용)
        self._turn_word_times: Dict[str, List[tuple]] = {}  # [(start, end), ...]
    
    def start_turn(self, session_id: str, turn_index: int = -1) -> None:
        """발화 턴 시작"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        
        if turn_index < 0:
            turn_index = len(self._sessions[session_id])
        
        turn = SpeechTurnMetrics(
            turn_index=turn_index,
            start_time=time.time(),
        )
        self._active_turns[session_id] = turn
        self._turn_confidences[session_id] = []
        self._turn_word_times[session_id] = []
    
    def add_stt_result(
        self,
        session_id: str,
        transcript: str,
        is_final: bool,
        confidence: float = 0.0,
        words: Optional[List[Dict]] = None,
    ) -> None:
        """STT 결과 수신 시 호출. Deepgram words 배열이 있으면 상세 분석.
        
        words 형식: [{"word": "안녕하세요", "start": 0.5, "end": 1.1, "confidence": 0.97}, ...]
        """
        if session_id not in self._active_turns:
            return
        
        # word-level confidence 수집
        if words:
            for w in words:
                conf = w.get("confidence", 0.0)
                if conf > 0:
                    self._turn_confidences.setdefault(session_id, []).append(conf)
                
                start = w.get("start", 0)
                end = w.get("end", 0)
                if start > 0 and end > 0:
                    self._turn_word_times.setdefault(session_id, []).append((start, end))
        elif confidence > 0 and is_final:
            # words 배열이 없으면 문장 단위 confidence 사용
            self._turn_confidences.setdefault(session_id, []).append(confidence)
    
    def end_turn(self, session_id: str, final_text: str = "") -> Optional[SpeechTurnMetrics]:
        """발화 턴 종료. 최종 텍스트로 메트릭 계산."""
        turn = self._active_turns.pop(session_id, None)
        if not turn:
            return None
        
        turn.end_time = time.time()
        turn.text = final_text
        turn.duration_seconds = turn.end_time - turn.start_time
        turn.word_count = count_words_ko(final_text)
        turn.syllable_count = count_syllables_ko(final_text)
        turn.filler_count = count_fillers(final_text)
        
        # 발화 속도 계산 (0으로 나누기 방지)
        if turn.duration_seconds > 1:
            minutes = turn.duration_seconds / 60.0
            turn.speech_rate_spm = turn.syllable_count / minutes
            turn.speech_rate_wpm = turn.word_count / minutes
        
        # confidence 통계
        confidences = self._turn_confidences.pop(session_id, [])
        turn.word_confidences = confidences
        turn.avg_confidence = statistics.mean(confidences) if confidences else 0.0
        
        # pause 분석 (word timestamps 기반)
        word_times = self._turn_word_times.pop(session_id, [])
        if len(word_times) > 1:
            word_times.sort(key=lambda x: x[0])
            for i in range(1, len(word_times)):
                gap = word_times[i][0] - word_times[i - 1][1]
                if gap >= 1.0:  # 1초 이상 침묵
                    turn.pause_count += 1
                    turn.pause_durations.append(round(gap, 2))
        
        self._sessions.setdefault(session_id, []).append(turn)
        return turn
    
    def get_session_stats(self, session_id: str) -> SessionSpeechStats:
        """세션 전체 발화 통계 집계"""
        turns = self._sessions.get(session_id, [])
        stats = SessionSpeechStats(session_id=session_id)
        
        if not turns:
            stats.speech_rate_assessment = "발화 데이터가 없습니다."
            stats.pronunciation_assessment = "발음 데이터가 없습니다."
            return stats
        
        stats.total_turns = len(turns)
        stats.total_duration_seconds = sum(t.duration_seconds for t in turns)
        stats.total_syllables = sum(t.syllable_count for t in turns)
        stats.total_words = sum(t.word_count for t in turns)
        stats.total_fillers = sum(t.filler_count for t in turns)
        stats.total_pauses = sum(t.pause_count for t in turns)
        
        # 평균 발화 속도
        spm_values = [t.speech_rate_spm for t in turns if t.speech_rate_spm > 0]
        if spm_values:
            stats.avg_speech_rate_spm = statistics.mean(spm_values)
            stats.avg_speech_rate_wpm = statistics.mean(
                [t.speech_rate_wpm for t in turns if t.speech_rate_wpm > 0]
            )
            if len(spm_values) > 1:
                stats.speech_rate_consistency = statistics.stdev(spm_values)
        
        # 평균 confidence
        all_confs = [c for t in turns for c in t.word_confidences]
        if all_confs:
            stats.avg_confidence = statistics.mean(all_confs)
        else:
            # word-level이 없으면 turn-level 평균 사용
            turn_confs = [t.avg_confidence for t in turns if t.avg_confidence > 0]
            stats.avg_confidence = statistics.mean(turn_confs) if turn_confs else 0.0
        
        # 평균 침묵 시간
        all_pauses = [p for t in turns for p in t.pause_durations]
        stats.avg_pause_duration = statistics.mean(all_pauses) if all_pauses else 0.0
        
        # 등급 및 평가
        stats.speech_rate_grade, stats.speech_rate_assessment = grade_speech_rate(
            stats.avg_speech_rate_spm
        )
        stats.pronunciation_grade, stats.pronunciation_assessment = grade_pronunciation(
            stats.avg_confidence
        )
        
        # 턴별 상세
        stats.turn_details = [
            {
                "turn": t.turn_index + 1,
                "duration_sec": round(t.duration_seconds, 1),
                "syllables": t.syllable_count,
                "words": t.word_count,
                "spm": round(t.speech_rate_spm, 1),
                "wpm": round(t.speech_rate_wpm, 1),
                "confidence": round(t.avg_confidence, 3),
                "fillers": t.filler_count,
                "pauses": t.pause_count,
            }
            for t in turns
        ]
        
        return stats
    
    def clear_session(self, session_id: str) -> None:
        """세션 데이터 정리"""
        self._sessions.pop(session_id, None)
        self._active_turns.pop(session_id, None)
        self._turn_confidences.pop(session_id, None)
        self._turn_word_times.pop(session_id, None)
