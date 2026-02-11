"""
Hume AI Prosody 감정 분석 서비스
================================
면접 지원자의 **음성 톤(Prosody)** 에서 48종 감정을 분석합니다.

기능:
  - Hume Expression Measurement Streaming API (WebSocket) 기반 실시간 분석
  - Hume Expression Measurement Batch API (REST) 기반 녹음 후 분석
  - DeepFace 7종 표정 감정과 병합하여 멀티모달 감정 융합
  - 면접 맥락에 최적화된 10종 핵심 지표 추출

48종 감정 → 면접 핵심 지표 매핑:
  - 자신감(Confidence): Determination, Pride, Triumph
  - 불안(Anxiety): Anxiety, Fear, Distress
  - 집중(Focus): Concentration, Contemplation, Interest
  - 당황(Confusion): Confusion, Awkwardness, Embarrassment
  - 긍정(Positivity): Joy, Satisfaction, Excitement
  - 진정(Calmness): Calmness, Contentment, Relief
  - 부정(Negativity): Anger, Disgust, Contempt
  - 슬픔(Sadness): Sadness, Disappointment, Doubt
  - 놀람(Surprise): Surprise (positive), Surprise (negative), Realization
  - 피로(Fatigue): Boredom, Tiredness
"""

import os
import asyncio
import base64
import json
import time
import statistics
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter

import httpx
from dotenv import load_dotenv

load_dotenv()

# ========== Hume AI API 키 (hume_tts_service.py와 공유) ==========
HUME_API_KEY = os.getenv("HUME_API_KEY")
HUME_SECRET_KEY = os.getenv("HUME_SECRET_KEY")

# ========== 면접 핵심 지표 매핑 ==========
INTERVIEW_EMOTION_MAP: Dict[str, List[str]] = {
    "confidence": ["Determination", "Pride", "Triumph"],
    "anxiety": ["Anxiety", "Fear", "Distress"],
    "focus": ["Concentration", "Contemplation", "Interest"],
    "confusion": ["Confusion", "Awkwardness", "Embarrassment"],
    "positivity": ["Joy", "Satisfaction", "Excitement"],
    "calmness": ["Calmness", "Contentment", "Relief"],
    "negativity": ["Anger", "Disgust", "Contempt"],
    "sadness": ["Sadness", "Disappointment", "Doubt"],
    "surprise": ["Surprise (positive)", "Surprise (negative)", "Realization"],
    "fatigue": ["Boredom", "Tiredness"],
}

# 48종 전체 감정 목록
ALL_PROSODY_EMOTIONS = [
    "Admiration", "Adoration", "Aesthetic Appreciation", "Amusement",
    "Anger", "Anxiety", "Awe", "Awkwardness",
    "Boredom", "Calmness", "Concentration", "Contemplation",
    "Contentment", "Craving", "Desire", "Determination",
    "Disappointment", "Disgust", "Distress", "Doubt",
    "Ecstasy", "Embarrassment", "Empathic Pain", "Entrancement",
    "Envy", "Excitement", "Fear", "Guilt",
    "Horror", "Interest", "Joy", "Love",
    "Nostalgia", "Pain", "Pride", "Realization",
    "Relief", "Romance", "Sadness", "Satisfaction",
    "Shame", "Surprise (negative)", "Surprise (positive)", "Sympathy",
    "Tiredness", "Triumph", "Confusion", "Contempt",
]


# ========== 데이터 클래스 ==========

@dataclass
class ProsodyEmotionSample:
    """단일 Prosody 감정 분석 샘플"""
    timestamp: float
    text: str                       # 발화 텍스트
    time_begin: float               # 오디오 내 시작 시각 (초)
    time_end: float                 # 오디오 내 종료 시각 (초)
    raw_emotions: Dict[str, float]  # 48종 감정 {이름: 스코어}
    interview_indicators: Dict[str, float]  # 10종 면접 지표
    dominant_emotion: str           # 가장 높은 감정
    dominant_indicator: str         # 가장 높은 면접 지표


@dataclass
class ProsodyTurnStats:
    """단일 턴의 Prosody 감정 통계"""
    turn_index: int
    sample_count: int = 0
    dominant_indicator: str = ""
    indicator_averages: Dict[str, float] = field(default_factory=dict)
    top_emotions: List[Tuple[str, float]] = field(default_factory=list)
    confidence_trend: str = ""  # "rising", "stable", "falling"


@dataclass
class ProsodySessionStats:
    """세션 전체 Prosody 감정 통계"""
    session_id: str
    total_samples: int = 0
    indicator_averages: Dict[str, float] = field(default_factory=dict)
    indicator_grades: Dict[str, str] = field(default_factory=dict)
    dominant_indicator: str = ""
    overall_assessment: str = ""
    confidence_level: str = ""      # 자신감 수준 평가
    anxiety_level: str = ""         # 불안 수준 평가
    engagement_level: str = ""      # 참여도 수준 평가
    emotional_stability: float = 0.0  # 감정 안정성 (0-1)
    turn_details: List[Dict] = field(default_factory=list)
    emotion_timeline: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_samples": self.total_samples,
            "indicator_averages": {
                k: round(v, 4) for k, v in self.indicator_averages.items()
            },
            "indicator_grades": self.indicator_grades,
            "dominant_indicator": self.dominant_indicator,
            "overall_assessment": self.overall_assessment,
            "confidence_level": self.confidence_level,
            "anxiety_level": self.anxiety_level,
            "engagement_level": self.engagement_level,
            "emotional_stability": round(self.emotional_stability, 3),
            "turn_details": self.turn_details,
            "emotion_timeline": self.emotion_timeline,
        }


# ========== 토큰 인증 (hume_tts_service와 독립 캐싱) ==========
_prosody_access_token: Optional[str] = None
_prosody_token_expires_at: float = 0


async def _get_prosody_access_token() -> Optional[str]:
    """Hume AI OAuth2 토큰 인증 (Prosody 전용 캐시)"""
    global _prosody_access_token, _prosody_token_expires_at

    if _prosody_access_token and time.time() < _prosody_token_expires_at - 300:
        return _prosody_access_token

    if not HUME_API_KEY or not HUME_SECRET_KEY:
        print("⚠️ [HumeProsody] HUME_API_KEY 또는 HUME_SECRET_KEY가 설정되지 않았습니다.")
        return None

    try:
        auth = f"{HUME_API_KEY}:{HUME_SECRET_KEY}"
        encoded_auth = base64.b64encode(auth.encode()).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url="https://api.hume.ai/oauth2-cc/token",
                headers={"Authorization": f"Basic {encoded_auth}"},
                data={"grant_type": "client_credentials"},
            )
            if resp.status_code == 200:
                data = resp.json()
                _prosody_access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                _prosody_token_expires_at = time.time() + expires_in
                print("✅ [HumeProsody] 토큰 인증 성공")
                return _prosody_access_token
            else:
                print(f"❌ [HumeProsody] 토큰 인증 실패: {resp.status_code}")
                return None
    except Exception as e:
        print(f"❌ [HumeProsody] 토큰 인증 오류: {e}")
        return None


# ========== 감정 스코어 → 면접 지표 변환 ==========

def extract_interview_indicators(raw_emotions: Dict[str, float]) -> Dict[str, float]:
    """
    48종 Hume Prosody 감정 스코어를 10종 면접 핵심 지표로 변환합니다.

    각 지표는 해당 감정 그룹의 평균 스코어입니다.
    """
    indicators: Dict[str, float] = {}
    for indicator_name, emotion_names in INTERVIEW_EMOTION_MAP.items():
        scores = [raw_emotions.get(name, 0.0) for name in emotion_names]
        indicators[indicator_name] = sum(scores) / len(scores) if scores else 0.0
    return indicators


def get_dominant_indicator(indicators: Dict[str, float]) -> str:
    """가장 높은 면접 지표 반환"""
    if not indicators:
        return "unknown"
    return max(indicators, key=indicators.get)


def determine_emotion_adaptive_mode(indicators: Dict[str, float]) -> str:
    """
    Prosody 면접 지표 기반 감정 적응 모드 결정.

    DeepFace 의 3분류(encouraging/challenging/normal) 와 호환.
    Prosody 는 더 세밀한 지표를 활용하므로 정확도가 높습니다.
    """
    anxiety = indicators.get("anxiety", 0)
    sadness = indicators.get("sadness", 0)
    negativity = indicators.get("negativity", 0)
    confidence = indicators.get("confidence", 0)
    positivity = indicators.get("positivity", 0)
    confusion = indicators.get("confusion", 0)

    # 부정적 상태가 강하면 격려 모드
    if (anxiety + sadness + negativity) / 3 > 0.15 or confusion > 0.2:
        return "encouraging"
    # 자신감+긍정이 높으면 심화 모드
    elif (confidence + positivity) / 2 > 0.2:
        return "challenging"
    else:
        return "normal"


# ========== Hume Prosody 분석 서비스 ==========

class HumeProsodyService:
    """
    Hume AI Expression Measurement API를 사용하여
    면접 지원자의 음성 톤에서 48종 감정을 분석하는 서비스.
    """

    def __init__(self):
        self.api_key = HUME_API_KEY
        self.secret_key = HUME_SECRET_KEY
        self._is_available = bool(self.api_key)

        # 세션별 데이터 저장소
        self._session_samples: Dict[str, List[ProsodyEmotionSample]] = {}
        self._session_turn_indices: Dict[str, int] = {}
        self._session_turn_boundaries: Dict[str, List[int]] = {}  # 턴 시작 sample index

        if not self._is_available:
            print("⚠️ [HumeProsody] HUME_API_KEY 미설정 — 서비스 비활성화")
        else:
            print("✅ [HumeProsody] 서비스 초기화 완료")

    @property
    def is_available(self) -> bool:
        return self._is_available

    # ------------------------------------------------------------------ #
    #  Batch API — 오디오 파일/바이트 분석                                    #
    # ------------------------------------------------------------------ #
    async def analyze_audio_bytes(
        self,
        audio_data: bytes,
        session_id: str,
        content_type: str = "audio/wav",
    ) -> Optional[List[ProsodyEmotionSample]]:
        """
        오디오 바이트 데이터를 Hume Batch API로 분석합니다.

        Args:
            audio_data: 오디오 파일 바이트 (wav, mp3 등)
            session_id: 세션 ID
            content_type: MIME 타입

        Returns:
            ProsodyEmotionSample 리스트 또는 None
        """
        if not self._is_available:
            return None

        token = await _get_prosody_access_token()
        if not token:
            # API Key 인증 폴백
            headers = {
                "X-Hume-Api-Key": self.api_key,
            }
        else:
            headers = {
                "Authorization": f"Bearer {token}",
            }

        try:
            # Batch Job 제출
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 파일 업로드 + Prosody 모델 설정
                files = {"file": ("audio.wav", audio_data, content_type)}
                models_config = json.dumps({
                    "models": {
                        "prosody": {
                            "granularity": "utterance",
                            "identify_speakers": False,
                        }
                    }
                })

                resp = await client.post(
                    "https://api.hume.ai/v0/batch/jobs",
                    headers=headers,
                    files=files,
                    data={"json": models_config},
                )

                if resp.status_code != 200:
                    print(f"❌ [HumeProsody] Batch Job 제출 실패: {resp.status_code} {resp.text[:200]}")
                    return None

                job_data = resp.json()
                job_id = job_data.get("job_id")
                if not job_id:
                    print(f"❌ [HumeProsody] Job ID 없음: {job_data}")
                    return None

                print(f"🔄 [HumeProsody] Batch Job 제출: {job_id}")

                # 폴링으로 완료 대기
                predictions = await self._poll_batch_job(client, headers, job_id)
                if predictions is None:
                    return None

                # 파싱
                samples = self._parse_prosody_predictions(predictions, session_id)
                return samples

        except Exception as e:
            print(f"❌ [HumeProsody] Batch 분석 오류: {e}")
            return None

    async def _poll_batch_job(
        self, client: httpx.AsyncClient, headers: dict, job_id: str,
        max_wait: int = 120, interval: float = 2.0,
    ) -> Optional[Dict]:
        """Batch Job 완료 폴링"""
        elapsed = 0.0
        while elapsed < max_wait:
            resp = await client.get(
                f"https://api.hume.ai/v0/batch/jobs/{job_id}",
                headers=headers,
            )
            if resp.status_code == 200:
                status_data = resp.json()
                status = status_data.get("state", {}).get("status", "")
                if status == "COMPLETED":
                    # 예측 결과 가져오기
                    pred_resp = await client.get(
                        f"https://api.hume.ai/v0/batch/jobs/{job_id}/predictions",
                        headers=headers,
                    )
                    if pred_resp.status_code == 200:
                        return pred_resp.json()
                    print(f"❌ [HumeProsody] 예측 결과 조회 실패: {pred_resp.status_code}")
                    return None
                elif status == "FAILED":
                    print(f"❌ [HumeProsody] Batch Job 실패: {status_data}")
                    return None
                # IN_PROGRESS — 계속 대기
            await asyncio.sleep(interval)
            elapsed += interval

        print(f"⚠️ [HumeProsody] Batch Job 타임아웃 ({max_wait}초)")
        return None

    # ------------------------------------------------------------------ #
    #  Streaming API — 실시간 오디오 스트림 분석                                #
    # ------------------------------------------------------------------ #
    async def analyze_audio_stream(
        self,
        audio_chunk: bytes,
        session_id: str,
    ) -> Optional[ProsodyEmotionSample]:
        """
        오디오 청크를 Hume Streaming API (WebSocket)로 분석합니다.

        현재는 REST 기반 간이 구현 — 프레임 누적 후 Batch 분석.
        본격 WebSocket 스트리밍은 hume SDK 의 connect 를 활용합니다.

        Args:
            audio_chunk: PCM16 오디오 청크
            session_id: 세션 ID

        Returns:
            ProsodyEmotionSample 또는 None
        """
        if not self._is_available:
            return None

        token = await _get_prosody_access_token()
        if not token and not self.api_key:
            return None

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["X-Hume-Api-Key"] = self.api_key

        try:
            audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.hume.ai/v0/stream/models",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "data": audio_b64,
                        "models": {"prosody": {}},
                        "raw_text": False,
                    },
                )

                if resp.status_code != 200:
                    return None

                result = resp.json()
                prosody_preds = result.get("prosody", {}).get("predictions", [])

                if not prosody_preds:
                    return None

                # 첫 번째 예측 사용
                pred = prosody_preds[0]
                raw_emotions = {
                    e["name"]: e["score"]
                    for e in pred.get("emotions", [])
                }
                indicators = extract_interview_indicators(raw_emotions)
                dominant = max(raw_emotions, key=raw_emotions.get) if raw_emotions else "neutral"

                sample = ProsodyEmotionSample(
                    timestamp=time.time(),
                    text=pred.get("text", ""),
                    time_begin=pred.get("time", {}).get("begin", 0),
                    time_end=pred.get("time", {}).get("end", 0),
                    raw_emotions=raw_emotions,
                    interview_indicators=indicators,
                    dominant_emotion=dominant,
                    dominant_indicator=get_dominant_indicator(indicators),
                )

                # 세션에 저장
                self._session_samples.setdefault(session_id, []).append(sample)
                return sample

        except Exception as e:
            print(f"⚠️ [HumeProsody] 스트리밍 분석 오류: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  예측 결과 파싱                                                        #
    # ------------------------------------------------------------------ #
    def _parse_prosody_predictions(
        self, predictions_data: Any, session_id: str
    ) -> List[ProsodyEmotionSample]:
        """Hume API Batch 응답을 ProsodyEmotionSample 리스트로 변환"""
        samples: List[ProsodyEmotionSample] = []

        try:
            # Batch API 응답 구조: [{source: {}, results: {predictions: [{models: {prosody: ...}}]}}]
            for source_entry in predictions_data:
                results = source_entry.get("results", {})
                preds = results.get("predictions", [])
                for pred_group in preds:
                    prosody_model = pred_group.get("models", {}).get("prosody", {})
                    grouped = prosody_model.get("grouped_predictions", [])
                    for group in grouped:
                        for pred in group.get("predictions", []):
                            raw_emotions = {
                                e["name"]: e["score"]
                                for e in pred.get("emotions", [])
                            }
                            indicators = extract_interview_indicators(raw_emotions)
                            dominant = (
                                max(raw_emotions, key=raw_emotions.get)
                                if raw_emotions
                                else "neutral"
                            )

                            sample = ProsodyEmotionSample(
                                timestamp=time.time(),
                                text=pred.get("text", ""),
                                time_begin=pred.get("time", {}).get("begin", 0),
                                time_end=pred.get("time", {}).get("end", 0),
                                raw_emotions=raw_emotions,
                                interview_indicators=indicators,
                                dominant_emotion=dominant,
                                dominant_indicator=get_dominant_indicator(indicators),
                            )
                            samples.append(sample)
        except Exception as e:
            print(f"⚠️ [HumeProsody] 파싱 오류: {e}")

        # 세션에 저장
        self._session_samples.setdefault(session_id, []).extend(samples)
        print(f"✅ [HumeProsody] {len(samples)}개 샘플 파싱 완료 (session={session_id[:8]}...)")
        return samples

    # ------------------------------------------------------------------ #
    #  수동 샘플 추가 (Celery Worker 등에서 사용)                              #
    # ------------------------------------------------------------------ #
    def add_sample_from_dict(self, session_id: str, data: Dict) -> ProsodyEmotionSample:
        """딕셔너리에서 ProsodyEmotionSample 생성 및 저장"""
        raw_emotions = data.get("raw_emotions", {})
        indicators = extract_interview_indicators(raw_emotions)
        dominant = max(raw_emotions, key=raw_emotions.get) if raw_emotions else "neutral"

        sample = ProsodyEmotionSample(
            timestamp=data.get("timestamp", time.time()),
            text=data.get("text", ""),
            time_begin=data.get("time_begin", 0),
            time_end=data.get("time_end", 0),
            raw_emotions=raw_emotions,
            interview_indicators=indicators,
            dominant_emotion=dominant,
            dominant_indicator=get_dominant_indicator(indicators),
        )
        self._session_samples.setdefault(session_id, []).append(sample)
        return sample

    # ------------------------------------------------------------------ #
    #  턴 경계 관리                                                          #
    # ------------------------------------------------------------------ #
    def start_new_turn(self, session_id: str):
        """새 답변 턴 시작 시 호출"""
        idx = len(self._session_samples.get(session_id, []))
        self._session_turn_boundaries.setdefault(session_id, []).append(idx)
        turn_num = len(self._session_turn_boundaries[session_id])
        self._session_turn_indices[session_id] = turn_num

    # ------------------------------------------------------------------ #
    #  통계 계산                                                             #
    # ------------------------------------------------------------------ #
    def get_latest_indicators(self, session_id: str) -> Optional[Dict[str, float]]:
        """세션의 최신 면접 지표 반환"""
        samples = self._session_samples.get(session_id, [])
        if not samples:
            return None
        return samples[-1].interview_indicators

    def get_latest_adaptive_mode(self, session_id: str) -> str:
        """세션의 최신 Prosody 기반 적응 모드 반환"""
        indicators = self.get_latest_indicators(session_id)
        if not indicators:
            return "normal"
        return determine_emotion_adaptive_mode(indicators)

    def get_session_stats(self, session_id: str) -> ProsodySessionStats:
        """세션 전체 Prosody 감정 통계 계산"""
        samples = self._session_samples.get(session_id, [])
        stats = ProsodySessionStats(session_id=session_id)
        stats.total_samples = len(samples)

        if not samples:
            stats.overall_assessment = "Prosody 분석 데이터 없음"
            return stats

        # 지표별 평균
        indicator_values: Dict[str, List[float]] = {k: [] for k in INTERVIEW_EMOTION_MAP}
        for s in samples:
            for k, v in s.interview_indicators.items():
                indicator_values[k].append(v)

        for k, vals in indicator_values.items():
            stats.indicator_averages[k] = sum(vals) / len(vals) if vals else 0

        # 지표별 등급
        for k, avg in stats.indicator_averages.items():
            stats.indicator_grades[k] = self._grade_indicator(k, avg)

        # 주요 지표
        stats.dominant_indicator = get_dominant_indicator(stats.indicator_averages)

        # 자신감 / 불안 / 참여도 수준 평가
        stats.confidence_level = self._assess_level(
            stats.indicator_averages.get("confidence", 0), "confidence"
        )
        stats.anxiety_level = self._assess_level(
            stats.indicator_averages.get("anxiety", 0), "anxiety"
        )
        engagement = (
            stats.indicator_averages.get("focus", 0)
            + stats.indicator_averages.get("positivity", 0)
        ) / 2
        stats.engagement_level = self._assess_level(engagement, "engagement")

        # 감정 안정성 (지표 분산의 역수)
        all_indicator_stds = []
        for k, vals in indicator_values.items():
            if len(vals) >= 2:
                all_indicator_stds.append(statistics.stdev(vals))
        if all_indicator_stds:
            avg_std = sum(all_indicator_stds) / len(all_indicator_stds)
            stats.emotional_stability = max(0, 1.0 - avg_std * 5)  # 정규화
        else:
            stats.emotional_stability = 0.5

        # 턴별 통계
        boundaries = self._session_turn_boundaries.get(session_id, [])
        for i, start_idx in enumerate(boundaries):
            end_idx = boundaries[i + 1] if i + 1 < len(boundaries) else len(samples)
            turn_samples = samples[start_idx:end_idx]
            if not turn_samples:
                continue

            turn_indicators: Dict[str, float] = {k: 0 for k in INTERVIEW_EMOTION_MAP}
            for s in turn_samples:
                for k, v in s.interview_indicators.items():
                    turn_indicators[k] += v
            for k in turn_indicators:
                turn_indicators[k] /= len(turn_samples)

            # 자신감 추세
            conf_vals = [s.interview_indicators.get("confidence", 0) for s in turn_samples]
            if len(conf_vals) >= 2:
                trend = "rising" if conf_vals[-1] > conf_vals[0] * 1.1 else (
                    "falling" if conf_vals[-1] < conf_vals[0] * 0.9 else "stable"
                )
            else:
                trend = "stable"

            stats.turn_details.append({
                "turn_index": i + 1,
                "sample_count": len(turn_samples),
                "dominant_indicator": get_dominant_indicator(turn_indicators),
                "indicator_averages": {k: round(v, 4) for k, v in turn_indicators.items()},
                "confidence_trend": trend,
            })

        # 타임라인 (최대 50 포인트)
        step = max(1, len(samples) // 50)
        for i in range(0, len(samples), step):
            s = samples[i]
            stats.emotion_timeline.append({
                "timestamp": s.timestamp,
                "text": s.text[:50] if s.text else "",
                "dominant_emotion": s.dominant_emotion,
                "dominant_indicator": s.dominant_indicator,
                "confidence": round(s.interview_indicators.get("confidence", 0), 4),
                "anxiety": round(s.interview_indicators.get("anxiety", 0), 4),
                "focus": round(s.interview_indicators.get("focus", 0), 4),
            })

        # 종합 평가
        stats.overall_assessment = self._generate_assessment(stats)

        return stats

    def get_session_stats_dict(self, session_id: str) -> Dict:
        """세션 통계를 딕셔너리로 반환 (리포트 생성용)"""
        return self.get_session_stats(session_id).to_dict()

    # ------------------------------------------------------------------ #
    #  DeepFace + Prosody 멀티모달 융합                                      #
    # ------------------------------------------------------------------ #
    def merge_with_deepface(
        self,
        prosody_indicators: Dict[str, float],
        deepface_emotion: Dict[str, Any],
        prosody_weight: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Prosody 면접 지표와 DeepFace 감정을 융합합니다.

        Args:
            prosody_indicators: 10종 Prosody 면접 지표
            deepface_emotion: DeepFace 결과 {dominant_emotion, probabilities}
            prosody_weight: Prosody 가중치 (0-1, 기본 0.5)

        Returns:
            융합된 감정 데이터
        """
        deepface_weight = 1.0 - prosody_weight

        # DeepFace 7종 → 면접 지표 매핑
        deepface_probs = deepface_emotion.get("probabilities", {})
        deepface_indicators = {
            "confidence": deepface_probs.get("happy", 0) * 0.5 + deepface_probs.get("surprise", 0) * 0.3,
            "anxiety": deepface_probs.get("fear", 0) * 0.6 + deepface_probs.get("sad", 0) * 0.3,
            "focus": deepface_probs.get("neutral", 0) * 0.7,
            "confusion": deepface_probs.get("surprise", 0) * 0.3 + deepface_probs.get("fear", 0) * 0.2,
            "positivity": deepface_probs.get("happy", 0) * 0.8,
            "calmness": deepface_probs.get("neutral", 0) * 0.6,
            "negativity": deepface_probs.get("angry", 0) * 0.5 + deepface_probs.get("disgust", 0) * 0.4,
            "sadness": deepface_probs.get("sad", 0) * 0.8,
            "surprise": deepface_probs.get("surprise", 0) * 0.7,
            "fatigue": deepface_probs.get("neutral", 0) * 0.2 + deepface_probs.get("sad", 0) * 0.2,
        }

        # 가중 평균 융합
        merged = {}
        for key in INTERVIEW_EMOTION_MAP:
            p_val = prosody_indicators.get(key, 0)
            d_val = deepface_indicators.get(key, 0)
            merged[key] = p_val * prosody_weight + d_val * deepface_weight

        # 융합 적응 모드
        adaptive_mode = determine_emotion_adaptive_mode(merged)

        return {
            "merged_indicators": merged,
            "dominant_indicator": get_dominant_indicator(merged),
            "emotion_adaptive_mode": adaptive_mode,
            "prosody_indicators": prosody_indicators,
            "deepface_indicators": deepface_indicators,
            "prosody_weight": prosody_weight,
            "source": "multimodal_fusion",
        }

    # ------------------------------------------------------------------ #
    #  세션 정리                                                             #
    # ------------------------------------------------------------------ #
    def cleanup_session(self, session_id: str):
        """세션 데이터 정리"""
        self._session_samples.pop(session_id, None)
        self._session_turn_indices.pop(session_id, None)
        self._session_turn_boundaries.pop(session_id, None)

    # ------------------------------------------------------------------ #
    #  내부 헬퍼                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _grade_indicator(indicator: str, value: float) -> str:
        """지표값을 등급으로 변환"""
        # 부정적 지표 (낮을수록 좋음)
        negative_indicators = {"anxiety", "confusion", "negativity", "sadness", "fatigue"}
        if indicator in negative_indicators:
            if value < 0.05:
                return "A"
            elif value < 0.10:
                return "B"
            elif value < 0.20:
                return "C"
            else:
                return "D"
        # 긍정적 지표 (높을수록 좋음)
        else:
            if value > 0.20:
                return "A"
            elif value > 0.10:
                return "B"
            elif value > 0.05:
                return "C"
            else:
                return "D"

    @staticmethod
    def _assess_level(value: float, indicator_type: str) -> str:
        """수준 평가 문자열 반환"""
        if indicator_type == "anxiety":
            # 불안은 낮을수록 좋음
            if value < 0.05:
                return "매우 안정적"
            elif value < 0.10:
                return "안정적"
            elif value < 0.20:
                return "약간 불안"
            else:
                return "높은 불안"
        else:
            # 자신감/참여도는 높을수록 좋음
            if value > 0.20:
                return "매우 높음"
            elif value > 0.10:
                return "높음"
            elif value > 0.05:
                return "보통"
            else:
                return "낮음"

    @staticmethod
    def _generate_assessment(stats: "ProsodySessionStats") -> str:
        """종합 평가 문자열 생성"""
        parts = []

        conf = stats.indicator_averages.get("confidence", 0)
        anx = stats.indicator_averages.get("anxiety", 0)
        focus = stats.indicator_averages.get("focus", 0)

        if conf > 0.15:
            parts.append("자신감 있는 음성 톤으로 답변하였습니다")
        elif conf > 0.08:
            parts.append("적절한 자신감을 보여주었습니다")
        else:
            parts.append("음성에서 자신감이 다소 부족하게 느껴졌습니다")

        if anx > 0.15:
            parts.append("불안감이 음성에서 감지되었으므로 긴장 관리 연습이 필요합니다")
        elif anx < 0.05:
            parts.append("긴장을 잘 관리하며 안정적인 음성을 유지했습니다")

        if focus > 0.15:
            parts.append("높은 집중력을 보여주었습니다")

        if stats.emotional_stability > 0.7:
            parts.append("전반적으로 감정이 안정적이었습니다")
        elif stats.emotional_stability < 0.4:
            parts.append("감정 변화가 큰 편이므로 일정한 톤 유지를 연습하면 좋겠습니다")

        return ". ".join(parts) + "." if parts else "음성 감정 분석 데이터가 충분하지 않습니다."


# ========== 싱글톤 인스턴스 ==========
_prosody_service: Optional[HumeProsodyService] = None


def get_prosody_service() -> Optional[HumeProsodyService]:
    """Prosody 서비스 싱글톤 인스턴스 반환"""
    global _prosody_service
    if _prosody_service is None:
        _prosody_service = HumeProsodyService()
    return _prosody_service


def is_prosody_available() -> bool:
    """Prosody 서비스 사용 가능 여부"""
    svc = get_prosody_service()
    return svc is not None and svc.is_available
