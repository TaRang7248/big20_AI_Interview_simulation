# Deepgram을 활용한 실시간 음성 인식 시스템

import os
import logging # 프로그램이 실행되는 동안 발생하는 일들을 기록(로그)하는 도구
import threading
from typing import Optional # 타입 힌트라는 기능을 위해 특정 형식을 가져오는 코드

# 필요한 패키지: deepgram-sdk, pyaudio, python-dotenv

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

class DeepgramService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment or provided.")
        
        # Deepgram 클라이언트 초기화 (v5.3.2는 키워드 인자 사용)
        self.client = DeepgramClient(api_key=self.api_key)
        # 선택적 한글 띄어쓰기 후처리기 캐시
        self._ko_spacing = None

    def _postprocess_transcript(self, text: str) -> str:
        """한국어 띄어쓰기가 부족한 경우, 설치되어 있으면 pykospacing으로 보정.
        라이브러리가 없거나 오류가 나면 원문을 그대로 반환.
        """
        if not text:
            return text
        try:
            # 지연 로딩 + 재사용
            if self._ko_spacing is None:
                from pykospacing import Spacing  # type: ignore
                self._ko_spacing = Spacing()
            return self._ko_spacing(text)
        except Exception:
            return text

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
    # 사용 예시
    deepgram_service = DeepgramService()
    deepgram_service.transcribe_live_microphone()
