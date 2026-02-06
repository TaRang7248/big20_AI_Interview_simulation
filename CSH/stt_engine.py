# Deepgram을 활용한 실시간 음성 인식 시스템
# pykospacing을 활용하여 한국어 띄어쓰기 보정 후처리 지원

import os
import logging  # 프로그램이 실행되는 동안 발생하는 일들을 기록(로그)하는 도구
import threading
from typing import Optional, List  # 타입 힌트라는 기능을 위해 특정 형식을 가져오는 코드

# 필요한 패키지: deepgram-sdk, pyaudio, python-dotenv, pykospacing

# .env라는 별도의 파일에 저장된 비밀 정보(예: Deepgram API Key)를 프로그램으로 읽어오는 기능을 가져오기
from dotenv import load_dotenv


from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import (
    ListenV1SocketClientResponse,
    ListenV1MediaMessage,
    ListenV1ControlMessage,
)

# 로깅 설정
# 프로그램이 실행되는 동안 발생하는 일들을 기록(Log)하기 위한 설계도
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()


# ========== pykospacing 사용 가능 여부 확인 ==========
_PYKOSPACING_AVAILABLE = False
try:
    from pykospacing import Spacing  # type: ignore
    _PYKOSPACING_AVAILABLE = True
    logger.info("✅ pykospacing 로드 성공 - 한국어 띄어쓰기 보정 활성화")
except ImportError:
    logger.warning(
        "⚠️ pykospacing 미설치 - 한국어 띄어쓰기 보정 비활성화. "
        "설치하려면: pip install pykospacing"
    )


class KoreanSpacingCorrector:
    """
    pykospacing을 활용한 한국어 띄어쓰기 보정기
    
    STT(음성→텍스트) 결과는 띄어쓰기가 부정확한 경우가 많습니다.
    이 클래스는 pykospacing 모델을 사용하여 한국어 텍스트의 
    띄어쓰기를 자동으로 교정합니다.
    
    사용 예시:
        corrector = KoreanSpacingCorrector()
        if corrector.is_available:
            fixed = corrector.correct("안녕하세요저는개발자입니다")
            # → "안녕하세요 저는 개발자입니다"
    """
    
    def __init__(self):
        """보정기 초기화 (Lazy Loading - 첫 호출 시 모델 로드)"""
        self._spacing = None      # pykospacing 모델 인스턴스 (캐싱)
        self._initialized = False  # 초기화 시도 여부
        self._available = _PYKOSPACING_AVAILABLE  # 패키지 설치 여부
    
    @property
    def is_available(self) -> bool:
        """pykospacing 사용 가능 여부"""
        return self._available
    
    def _ensure_initialized(self) -> bool:
        """모델이 로드되지 않았으면 로드 시도. 성공 시 True 반환."""
        if self._spacing is not None:
            return True
        if self._initialized or not self._available:
            return False
        
        self._initialized = True
        try:
            self._spacing = Spacing()
            logger.info("✅ pykospacing 모델 초기화 완료")
            return True
        except Exception as e:
            logger.error("❌ pykospacing 모델 초기화 실패: %s", e)
            self._available = False
            return False
    
    def correct(self, text: str) -> str:
        """
        한국어 텍스트의 띄어쓰기를 보정합니다.
        
        Args:
            text: 띄어쓰기 보정이 필요한 한국어 텍스트
            
        Returns:
            띄어쓰기가 보정된 텍스트. 
            pykospacing을 사용할 수 없거나 오류 발생 시 원본 텍스트 반환.
        """
        if not text or not text.strip():
            return text
        
        if not self._ensure_initialized():
            return text
        
        try:
            corrected = self._spacing(text)
            # pykospacing이 빈 문자열을 반환하는 예외 상황 방어
            return corrected if corrected and corrected.strip() else text
        except Exception as e:
            logger.warning("⚠️ 띄어쓰기 보정 중 오류 (원본 유지): %s", e)
            return text
    
    def correct_batch(self, texts: List[str]) -> List[str]:
        """
        여러 텍스트의 띄어쓰기를 일괄 보정합니다.
        
        Args:
            texts: 보정할 텍스트 리스트
            
        Returns:
            보정된 텍스트 리스트
        """
        return [self.correct(t) for t in texts]


class DeepgramService:
    def __init__(self, api_key: Optional[str] = None, enable_spacing_correction: bool = True):
        """
        Deepgram STT 서비스 초기화
        
        Args:
            api_key: Deepgram API 키 (없으면 환경변수에서 로드)
            enable_spacing_correction: 한국어 띄어쓰기 보정 활성화 여부 (기본: True)
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment or provided.")
        
        # Deepgram 클라이언트 초기화 (v5.3.2는 키워드 인자 사용)
        self.client = DeepgramClient(api_key=self.api_key)
        
        # 한국어 띄어쓰기 보정기
        self.enable_spacing_correction = enable_spacing_correction
        self._spacing_corrector = KoreanSpacingCorrector()
        
        if self.enable_spacing_correction and self._spacing_corrector.is_available:
            logger.info("✅ STT 띄어쓰기 보정 기능 활성화됨")
        elif self.enable_spacing_correction:
            logger.warning("⚠️ pykospacing 미설치로 띄어쓰기 보정 비활성화")
    
    @property
    def spacing_corrector(self) -> KoreanSpacingCorrector:
        """외부에서 띄어쓰기 보정기에 직접 접근할 수 있도록 제공"""
        return self._spacing_corrector

    def _postprocess_transcript(self, text: str) -> str:
        """
        STT 결과 후처리: 한국어 띄어쓰기 보정
        
        Deepgram의 STT 결과는 한국어 띄어쓰기가 부정확할 수 있습니다.
        pykospacing이 설치되어 있고 활성화된 경우 자동으로 보정합니다.
        
        Args:
            text: Deepgram에서 반환된 원본 텍스트
            
        Returns:
            띄어쓰기가 보정된 텍스트 (보정 불가 시 원본 반환)
        """
        if not text:
            return text
        
        # 띄어쓰기 보정이 비활성화된 경우 원본 반환
        if not self.enable_spacing_correction:
            return text
        
        return self._spacing_corrector.correct(text)

    def transcribe_live_microphone(self):
        """
        마이크 입력을 실시간으로 텍스트로 변환 (Live Streaming)
        """
        # PyAudio는 파이썬이 내 컴퓨터의 마이크 하드웨어에 접근할 수 있게 해주는 필수 라이브러리
        try:
            import pyaudio
        except ImportError:
            logger.error("PyAudio is required for microphone input. Install with: pip install pyaudio")
            return
        # Deepgram WebSocket 연결 (Listen v1, SDK v5.3.2 스타일)
        try:
            with self.client.listen.v1.connect(
                model="nova-3",
                language="ko",
                smart_format=True,
                encoding="linear16",
                sample_rate="16000",
                punctuate=True,
                interim_results=False,
                vad_events=True,
                endpointing=300,
            ) as connection:
                # 이벤트 핸들러 정의
                def on_message(message: ListenV1SocketClientResponse) -> None:
                    # 가능한 스키마를 방어적으로 처리하여 transcript를 추출
                    transcript = None
                    msg_type = getattr(message, "type", "Unknown")
                    try:
                        if hasattr(message, "results") and getattr(message.results, "channels", None):
                            # 최종 결과만 출력하여 띄어쓰기/문장부호가 적용된 문장을 사용
                            if getattr(message.results, "is_final", False):
                                alts = message.results.channels[0].alternatives
                                if alts:
                                    transcript = alts[0].transcript
                        elif hasattr(message, "channel") and getattr(message.channel, "alternatives", None):
                            # 일부 이벤트는 channel 경로를 사용할 수 있으나, 최종 여부 확인 후 출력
                            if getattr(message, "is_final", True):
                                alts = message.channel.alternatives
                                if alts:
                                    transcript = alts[0].transcript
                    except (AttributeError, IndexError, TypeError) as e:
                        logger.debug(
                            "Unhandled message parse: %s: %s",
                            getattr(message, "type", "Unknown"),
                            e,
                        )

                    if transcript:
                        fixed = self._postprocess_transcript(transcript)
                        # 보정이 적용된 경우 원본과 비교 로그 출력
                        if fixed != transcript:
                            logger.debug("[원본] %s", transcript)
                            logger.debug("[보정] %s", fixed)
                        print(f"Transcript: {fixed}")
                    else:
                        # VAD 이벤트를 식별해 로그로 출력 (타입명이 환경에 따라 다를 수 있으므로 포괄적으로 처리)
                        if "VAD" in str(msg_type).upper() or "UTTERANCE" in str(msg_type).upper():
                            print(f"VAD event: {msg_type}")

                connection.on(EventType.OPEN, lambda _: print("Connection opened"))
                connection.on(EventType.MESSAGE, on_message)
                connection.on(EventType.CLOSE, lambda _: print("Connection closed"))
                connection.on(EventType.ERROR, lambda error: logger.error("Deepgram Error: %s", error))

                # 수신 루프를 백그라운드에서 시작 (동기 코드 흐름 유지)
                threading.Thread(target=connection.start_listening, daemon=True).start()

                # PyAudio 설정 (마이크 입력)
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=1024,
                )

                print("\n🔴 듣는 중... 중단하려면 Ctrl+C를 누르세요.\n")

                try:
                    while True:
                        data = stream.read(1024, exception_on_overflow=False)
                        # 오디오 프레임을 전송 (v5 Listen v1)
                        connection.send_media(ListenV1MediaMessage(data))
                except KeyboardInterrupt:
                    print("\n🛑 중단하는 중...")
                    try:
                        # 전송 종료를 명시적으로 알림
                        connection.send_control(ListenV1ControlMessage(type="Finalize"))
                    except RuntimeError:
                        pass
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
        except (RuntimeError, OSError) as e:
            logger.error("Failed to connect/send to Deepgram: %s", e)

if __name__ == "__main__":
    import sys
    
    # --test-spacing 옵션: 띄어쓰기 보정 기능만 테스트
    if "--test-spacing" in sys.argv:
        print("=" * 50)
        print("🔤 한국어 띄어쓰기 보정 테스트")
        print("=" * 50)
        
        corrector = KoreanSpacingCorrector()
        if not corrector.is_available:
            print("❌ pykospacing이 설치되지 않았습니다.")
            print("   설치 명령: pip install pykospacing")
            sys.exit(1)
        
        # 테스트 문장 (띄어쓰기가 없거나 부정확한 예시)
        test_sentences = [
            "안녕하세요저는소프트웨어개발자입니다",
            "프로젝트에서가장어려웠던점은데이터베이스최적화였습니다",
            "리액트와타입스크립트를사용하여프론트엔드를개발했습니다",
            "팀원들과의소통을통해문제를해결할수있었습니다",
            "도커와쿠버네티스를활용한배포자동화경험이있습니다",
        ]
        
        print()
        for sentence in test_sentences:
            corrected = corrector.correct(sentence)
            changed = "✅" if corrected != sentence else "➖"
            print(f"{changed} 원본: {sentence}")
            print(f"   보정: {corrected}")
            print()
        
        print("=" * 50)
        print("테스트 완료!")
    else:
        # 기본 동작: 마이크 실시간 음성 인식
        deepgram_service = DeepgramService()
        print(f"\n📌 띄어쓰기 보정: {'활성화 ✅' if deepgram_service.spacing_corrector.is_available else '비활성화 ❌'}")
        deepgram_service.transcribe_live_microphone()
