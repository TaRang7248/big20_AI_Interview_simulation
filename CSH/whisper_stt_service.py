"""
Whisper 오프라인 STT 폴백 서비스
=================================
Deepgram(클라우드) 연결 불가 시 로컬 Whisper 모델로 음성→텍스트 변환.

주요 기능:
- faster-whisper 기반 고속 로컬 추론 (CPU/GPU)
- 한국어 최적화 (language="ko")
- word-level 타이밍/confidence 지원 (SpeechAnalysisService 연동)
- 실시간 오디오 버퍼링 + 주기적 변환 (VAD 기반)
- Deepgram API 장애 시 자동 폴백
- pykospacing 띄어쓰기 보정 연동

사용:
    service = WhisperSTTService()
    service.start_session("session_id")
    service.feed_audio(session_id, pcm_bytes)
    results = service.flush(session_id)  # 즉시 변환
"""

import os
import io
import time
import wave
import struct
import asyncio
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# ========== faster-whisper 로드 ==========
_WHISPER_AVAILABLE = False
_WhisperModel = None

try:
    from faster_whisper import WhisperModel as _FasterWhisperModel
    _WhisperModel = _FasterWhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    pass

# openai-whisper 폴백
if not _WHISPER_AVAILABLE:
    try:
        import whisper as _openai_whisper
        _WHISPER_AVAILABLE = True
    except ImportError:
        _openai_whisper = None


def is_whisper_available() -> bool:
    """Whisper STT 사용 가능 여부"""
    return _WHISPER_AVAILABLE


# ========== 데이터 모델 ==========

@dataclass
class WhisperSegment:
    """Whisper 변환 결과 세그먼트"""
    text: str
    start: float  # 초
    end: float    # 초
    confidence: float  # 평균 확률
    words: Optional[List[Dict]] = None  # word-level: [{"word", "start", "end", "confidence"}]


@dataclass
class WhisperResult:
    """Whisper 변환 전체 결과"""
    transcript: str
    segments: List[WhisperSegment]
    language: str = "ko"
    duration: float = 0.0
    is_final: bool = True
    words: Optional[List[Dict]] = None  # 모든 세그먼트의 word 통합


@dataclass
class _SessionBuffer:
    """세션별 오디오 버퍼"""
    audio_chunks: deque = field(default_factory=deque)
    total_bytes: int = 0
    last_feed_time: float = 0.0
    is_active: bool = True
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16bit = 2 bytes
    # VAD: 음성 활동 감지용 에너지 추적
    silence_start: Optional[float] = None
    last_transcript: str = ""


class WhisperSTTService:
    """
    Whisper 기반 오프라인 STT 서비스

    Deepgram 클라우드 STT 불가 시 로컬 Whisper 모델로 폴백.
    - faster-whisper (우선) 또는 openai-whisper 사용
    - 오디오 청크를 버퍼링하고 일정 단위(VAD 기반)로 변환
    """

    # 모델 크기: tiny < base < small < medium < large
    DEFAULT_MODEL_SIZE = "base"
    # 오디오 청크를 모아서 변환하는 최소 단위 (초)
    MIN_AUDIO_DURATION = 1.5
    # 침묵 감지 후 자동 flush 시간 (초)
    SILENCE_FLUSH_SECONDS = 1.0
    # 에너지 기반 침묵 임계값 (RMS)
    SILENCE_RMS_THRESHOLD = 300
    # 최대 버퍼 크기 (초) — 메모리 보호
    MAX_BUFFER_SECONDS = 30
    # 변환 스레드풀 크기
    WORKER_THREADS = 2

    def __init__(
        self,
        model_size: str = None,
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "ko",
    ):
        """
        Args:
            model_size: Whisper 모델 크기 (tiny/base/small/medium/large-v3)
            device: "cpu", "cuda", "auto"
            compute_type: "int8", "float16", "float32", "auto"
            language: 언어 코드
        """
        self.model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", self.DEFAULT_MODEL_SIZE)
        self.device = device
        self.compute_type = compute_type
        self.language = language

        self._model = None
        self._model_lock = threading.Lock()
        self._model_loaded = False
        self._use_faster_whisper = _WhisperModel is not None

        # 세션별 버퍼
        self._sessions: Dict[str, _SessionBuffer] = {}
        self._sessions_lock = threading.Lock()

        # 변환 스레드풀
        self._executor = ThreadPoolExecutor(
            max_workers=self.WORKER_THREADS,
            thread_name_prefix="whisper-stt"
        )

        # 띄어쓰기 보정기
        self._spacing_corrector = None
        try:
            from stt_engine import KoreanSpacingCorrector
            self._spacing_corrector = KoreanSpacingCorrector()
            if not self._spacing_corrector.is_available:
                self._spacing_corrector = None
        except ImportError:
            pass

        # 콜백: 결과를 외부로 전달 (session_id, WhisperResult)
        self.on_result: Optional[Callable] = None

        print(f"🔧 [WhisperSTT] 초기화: model={self.model_size}, "
              f"engine={'faster-whisper' if self._use_faster_whisper else 'openai-whisper'}, "
              f"device={self.device}")

    # ──────── 모델 관리 ────────

    def _ensure_model(self):
        """Lazy loading: 첫 변환 시 모델 로드"""
        if self._model_loaded:
            return

        with self._model_lock:
            if self._model_loaded:
                return

            print(f"⏳ [WhisperSTT] 모델 로딩 중: {self.model_size} ...")
            start = time.time()

            if self._use_faster_whisper:
                # faster-whisper: CTranslate2 기반 고속 추론
                device = self.device
                compute = self.compute_type

                if device == "auto":
                    try:
                        import torch
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except ImportError:
                        device = "cpu"

                if compute == "auto":
                    compute = "float16" if device == "cuda" else "int8"

                self._model = _WhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute,
                )
            else:
                # openai-whisper 폴백
                self._model = _openai_whisper.load_model(self.model_size)

            elapsed = time.time() - start
            self._model_loaded = True
            print(f"✅ [WhisperSTT] 모델 로드 완료 ({elapsed:.1f}초)")

    # ──────── 세션 관리 ────────

    def start_session(self, session_id: str, sample_rate: int = 16000):
        """세션 오디오 버퍼 초기화"""
        with self._sessions_lock:
            self._sessions[session_id] = _SessionBuffer(
                sample_rate=sample_rate,
                last_feed_time=time.time(),
            )
        print(f"🎙️ [WhisperSTT] 세션 {session_id[:8]}... 시작")

    def end_session(self, session_id: str) -> Optional[WhisperResult]:
        """세션 종료: 남은 버퍼 flush 후 정리"""
        result = self.flush(session_id)
        with self._sessions_lock:
            self._sessions.pop(session_id, None)
        return result

    # ──────── 오디오 입력 ────────

    def feed_audio(self, session_id: str, pcm_bytes: bytes):
        """
        PCM 오디오 데이터(16-bit, mono, 16kHz)를 버퍼에 추가.
        일정 분량이 쌓이거나 침묵이 감지되면 자동 flush.
        """
        with self._sessions_lock:
            buf = self._sessions.get(session_id)
            if not buf or not buf.is_active:
                return

        buf.audio_chunks.append(pcm_bytes)
        buf.total_bytes += len(pcm_bytes)
        buf.last_feed_time = time.time()

        # RMS 에너지로 침묵 감지
        rms = self._compute_rms(pcm_bytes)
        if rms < self.SILENCE_RMS_THRESHOLD:
            if buf.silence_start is None:
                buf.silence_start = time.time()
            elif (time.time() - buf.silence_start) >= self.SILENCE_FLUSH_SECONDS:
                # 침묵이 충분히 지속됨 → flush
                duration = self._buffer_duration(buf)
                if duration >= self.MIN_AUDIO_DURATION:
                    self._async_flush(session_id)
                    buf.silence_start = None
        else:
            buf.silence_start = None

        # 최대 버퍼 초과 시 강제 flush
        if self._buffer_duration(buf) >= self.MAX_BUFFER_SECONDS:
            self._async_flush(session_id)

    @staticmethod
    def _compute_rms(pcm_bytes: bytes) -> float:
        """16-bit PCM의 RMS 에너지 계산"""
        if len(pcm_bytes) < 2:
            return 0.0
        n_samples = len(pcm_bytes) // 2
        samples = struct.unpack(f"<{n_samples}h", pcm_bytes[:n_samples * 2])
        if not samples:
            return 0.0
        sq_sum = sum(s * s for s in samples)
        return (sq_sum / n_samples) ** 0.5

    @staticmethod
    def _buffer_duration(buf: _SessionBuffer) -> float:
        """버퍼에 쌓인 오디오 길이 (초)"""
        bytes_per_second = buf.sample_rate * buf.channels * buf.sample_width
        return buf.total_bytes / bytes_per_second if bytes_per_second > 0 else 0.0

    # ──────── 변환 ────────

    def flush(self, session_id: str) -> Optional[WhisperResult]:
        """
        버퍼의 모든 오디오를 즉시 Whisper로 변환.
        동기 호출 — 결과를 직접 반환.
        """
        buf = self._sessions.get(session_id)
        if not buf or buf.total_bytes == 0:
            return None

        # 버퍼에서 오디오 추출 및 초기화
        chunks = list(buf.audio_chunks)
        buf.audio_chunks.clear()
        buf.total_bytes = 0

        pcm_data = b"".join(chunks)
        if len(pcm_data) < buf.sample_rate * buf.sample_width:
            # 0.5초 미만은 무시
            return None

        return self._transcribe(pcm_data, buf.sample_rate, session_id)

    def _async_flush(self, session_id: str):
        """비동기 flush — 스레드풀에서 변환"""
        buf = self._sessions.get(session_id)
        if not buf or buf.total_bytes == 0:
            return

        chunks = list(buf.audio_chunks)
        buf.audio_chunks.clear()
        buf.total_bytes = 0

        pcm_data = b"".join(chunks)
        if len(pcm_data) < buf.sample_rate * buf.sample_width:
            return

        def _worker():
            result = self._transcribe(pcm_data, buf.sample_rate, session_id)
            if result and self.on_result:
                self.on_result(session_id, result)

        self._executor.submit(_worker)

    def _transcribe(
        self, pcm_data: bytes, sample_rate: int, session_id: str = ""
    ) -> Optional[WhisperResult]:
        """PCM 데이터를 Whisper로 변환"""
        self._ensure_model()

        # PCM → WAV (in-memory)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        wav_buffer.seek(0)

        try:
            if self._use_faster_whisper:
                return self._transcribe_faster_whisper(wav_buffer, session_id)
            else:
                return self._transcribe_openai_whisper(wav_buffer, session_id)
        except Exception as e:
            print(f"[WhisperSTT] 변환 오류: {e}")
            return None

    def _transcribe_faster_whisper(
        self, wav_buffer: io.BytesIO, session_id: str
    ) -> Optional[WhisperResult]:
        """faster-whisper로 변환"""
        import numpy as np

        # WAV → numpy array
        wav_buffer.seek(0)
        with wave.open(wav_buffer, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        segments_iter, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        segments = []
        all_words = []
        full_text_parts = []

        for seg in segments_iter:
            words_list = []
            if seg.words:
                for w in seg.words:
                    word_dict = {
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "confidence": round(w.probability, 4),
                    }
                    words_list.append(word_dict)
                    all_words.append(word_dict)

            seg_obj = WhisperSegment(
                text=seg.text.strip(),
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                confidence=round(seg.avg_log_prob if hasattr(seg, 'avg_log_prob') else 0.0, 4),
                words=words_list if words_list else None,
            )
            segments.append(seg_obj)
            full_text_parts.append(seg.text.strip())

        transcript = " ".join(full_text_parts)
        if not transcript.strip():
            return None

        # 띄어쓰기 보정
        if self._spacing_corrector:
            corrected = self._spacing_corrector.correct(transcript)
            if corrected and corrected.strip():
                transcript = corrected

        return WhisperResult(
            transcript=transcript,
            segments=segments,
            language=info.language if hasattr(info, 'language') else self.language,
            duration=round(info.duration if hasattr(info, 'duration') else 0.0, 3),
            is_final=True,
            words=all_words if all_words else None,
        )

    def _transcribe_openai_whisper(
        self, wav_buffer: io.BytesIO, session_id: str
    ) -> Optional[WhisperResult]:
        """openai-whisper로 변환 (폴백)"""
        import tempfile
        import numpy as np

        # WAV를 임시 파일로 저장 (openai-whisper는 파일 경로 필요)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_buffer.read())
            tmp_path = tmp.name

        try:
            result = self._model.transcribe(
                tmp_path,
                language=self.language,
                word_timestamps=True,
                fp16=False,
            )

            segments = []
            all_words = []
            for seg in result.get("segments", []):
                words_list = []
                for w in seg.get("words", []):
                    word_dict = {
                        "word": w.get("word", "").strip(),
                        "start": round(w.get("start", 0.0), 3),
                        "end": round(w.get("end", 0.0), 3),
                        "confidence": round(w.get("probability", 0.0), 4),
                    }
                    words_list.append(word_dict)
                    all_words.append(word_dict)

                seg_obj = WhisperSegment(
                    text=seg.get("text", "").strip(),
                    start=round(seg.get("start", 0.0), 3),
                    end=round(seg.get("end", 0.0), 3),
                    confidence=round(seg.get("avg_logprob", 0.0), 4),
                    words=words_list if words_list else None,
                )
                segments.append(seg_obj)

            transcript = result.get("text", "").strip()
            if not transcript:
                return None

            # 띄어쓰기 보정
            if self._spacing_corrector:
                corrected = self._spacing_corrector.correct(transcript)
                if corrected and corrected.strip():
                    transcript = corrected

            return WhisperResult(
                transcript=transcript,
                segments=segments,
                language=result.get("language", self.language),
                duration=0.0,
                is_final=True,
                words=all_words if all_words else None,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ──────── 상태 조회 ────────

    def get_status(self) -> Dict[str, Any]:
        """서비스 상태 정보"""
        return {
            "available": _WHISPER_AVAILABLE,
            "model_loaded": self._model_loaded,
            "model_size": self.model_size,
            "engine": "faster-whisper" if self._use_faster_whisper else "openai-whisper",
            "device": self.device,
            "language": self.language,
            "active_sessions": len(self._sessions),
            "spacing_correction": self._spacing_corrector is not None,
        }

    def cleanup(self):
        """리소스 정리"""
        self._executor.shutdown(wait=False)
        self._sessions.clear()
        print("[WhisperSTT] 리소스 정리 완료")


# ========== 비동기 어댑터 (서버 통합용) ==========

async def process_audio_with_whisper(
    track,
    session_id: str,
    whisper_service: WhisperSTTService,
    broadcast_fn: Callable,
    speech_service=None,
):
    """
    aiortc 오디오 트랙을 Whisper STT로 처리.
    Deepgram의 `_process_audio_with_stt`와 동일한 인터페이스.

    Args:
        track: aiortc AudioStreamTrack
        session_id: 면접 세션 ID
        whisper_service: WhisperSTTService 인스턴스
        broadcast_fn: async (session_id, data_dict) → None
        speech_service: SpeechAnalysisService (Optional)
    """
    import numpy as np

    whisper_service.start_session(session_id)

    # 결과 콜백 설정 (비동기 flush용)
    loop = asyncio.get_event_loop()

    def _on_result(sid: str, result: WhisperResult):
        """Whisper 변환 결과를 WebSocket으로 브로드캐스트"""
        if not result or not result.transcript:
            return

        data = {
            "type": "stt_result",
            "transcript": result.transcript,
            "is_final": result.is_final,
            "timestamp": time.time(),
            "source": "whisper",
        }

        # 발화 분석 서비스에 데이터 전달
        if speech_service:
            try:
                words_list = result.words
                avg_confidence = None
                if words_list:
                    confs = [w.get("confidence", 0) for w in words_list]
                    avg_confidence = sum(confs) / len(confs) if confs else None

                speech_service.add_stt_result(
                    sid,
                    result.transcript,
                    result.is_final,
                    confidence=avg_confidence,
                    words=words_list,
                )
            except Exception as e:
                print(f"[WhisperSTT] SpeechAnalysis 전달 오류: {e}")

        # 이벤트 루프에 브로드캐스트 태스크 예약
        asyncio.run_coroutine_threadsafe(broadcast_fn(sid, data), loop)

    whisper_service.on_result = _on_result

    print(f"[WhisperSTT] 세션 {session_id} 오디오 처리 시작 (오프라인)")

    try:
        while True:
            frame = await track.recv()
            try:
                audio_data = frame.to_ndarray()
                # 16bit PCM 변환
                if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                    audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                else:
                    audio_bytes = audio_data.astype(np.int16).tobytes()

                whisper_service.feed_audio(session_id, audio_bytes)
            except Exception:
                pass
    except Exception as e:
        print(f"[WhisperSTT] 오디오 처리 종료: {e}")
    finally:
        # 남은 버퍼 flush
        final_result = whisper_service.end_session(session_id)
        if final_result and final_result.transcript:
            _on_result(session_id, final_result)
