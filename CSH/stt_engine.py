# Deepgram을 활용한 실시간 음성 인식 시스템

import os
import logging # 프로그램이 실행되는 동안 발생하는 일들을 기록(로그)하는 도구
from typing import Optional # 타입 힌트라는 기능을 위해 특정 형식을 가져오는 코드

# 필요한 패키지: deepgram-sdk, pyaudio, python-dotenv

# .env라는 별도의 파일에 저장된 비밀 정보(예: Deepgram API Key)를 프로그램으로 읽어오는 기능을 가져오기
from dotenv import load_dotenv


from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
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
        
        # Deepgram 클라이언트 초기화
        # Deepgram에 접속할 때의 상세 설정서를 작성
        config = DeepgramClientOptions(
            verbose=logging.DEBUG,
        )
        self.client = DeepgramClient(self.api_key, config)

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

        # Deepgram Live Connection 설정
        dg_connection = self.client.listen.live.v("1")

        # 이벤트 핸들러 정의
        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) > 0:
                print(f"Transcript: {sentence}")

        def on_error(self, error, **kwargs):
            logger.error(f"Deepgram Error: {error}")

        # 이벤트 연결
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # 연결 옵션
        options = LiveOptions(
            model="nova-2",
            language="ko",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True, # 중간 결과 실시간 표시
        )

        # 연결 시작
        if dg_connection.start(options) is False:
            logger.error("Failed to connect to Deepgram")
            return

        # PyAudio 설정 (마이크 입력)
        # 컴퓨터에 달린 마이크를 실제로 활성화시키는 단계
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        print("\n🔴 듣는 중... 중단하려면 Ctrl+C를 누르세요.\n")

        try:
            while True:
                data = stream.read(1024)
                dg_connection.send(data)
        except KeyboardInterrupt:
            print("\n🛑 중단하는 중...")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            dg_connection.finish()

if __name__ == "__main__":
    # 사용 예시
    deepgram_service = DeepgramService()
    deepgram_service.transcribe_live_microphone()
