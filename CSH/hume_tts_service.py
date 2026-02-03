"""
Hume AI TTS 서비스
- Hume AI의 EVI(Empathic Voice Interface)를 사용한 감정적 TTS 구현
- 면접관의 음성을 자연스럽고 감정적으로 생성
"""

import os
import asyncio
import base64
import json
import wave
import io
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Hume AI API 키 설정
HUME_API_KEY = os.getenv("HUME_API_KEY")
HUME_CONFIG_ID = os.getenv("HUME_CONFIG_ID")  # EVI 설정 ID (선택사항)


@dataclass
class HumeVoiceConfig:
    """Hume AI 음성 설정"""
    voice_name: str = "ITO"  # Hume 기본 음성
    language: str = "ko"  # 한국어 지원 (EVI 4-mini)
    speaking_rate: float = 1.0
    emotion_style: str = "professional"  # professional, friendly, empathetic


class HumeTTSService:
    """
    Hume AI EVI를 사용한 TTS 서비스
    
    특징:
    - 감정 인식 기반 자연스러운 음성 생성
    - 한국어 지원 (EVI 4-mini)
    - 실시간 스트리밍 가능
    """
    
    def __init__(self, api_key: Optional[str] = None, config_id: Optional[str] = None):
        self.api_key = api_key or HUME_API_KEY
        self.config_id = config_id or HUME_CONFIG_ID
        self._client = None
        self._audio_queue = asyncio.Queue()
        
        if not self.api_key:
            print("⚠️ HUME_API_KEY가 설정되지 않았습니다. .env 파일에 추가해주세요.")
    
    async def _get_client(self):
        """Hume 클라이언트 초기화 (lazy loading)"""
        if self._client is None:
            try:
                from hume.client import AsyncHumeClient
                self._client = AsyncHumeClient(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Hume SDK가 설치되지 않았습니다. "
                    "다음 명령어로 설치하세요: pip install hume[microphone]"
                )
        return self._client
    
    async def generate_speech_stream(
        self, 
        text: str, 
        on_audio_chunk: Optional[Callable[[bytes], None]] = None
    ) -> bytes:
        """
        텍스트를 음성으로 변환 (스트리밍)
        
        Args:
            text: 변환할 텍스트
            on_audio_chunk: 오디오 청크가 도착할 때마다 호출되는 콜백
            
        Returns:
            전체 오디오 데이터 (bytes)
        """
        client = await self._get_client()
        audio_chunks = []
        
        try:
            from hume.empathic_voice.chat.socket_client import ChatConnectOptions
            from hume.empathic_voice.chat.types import SubscribeEvent
            from hume import Stream
            
            stream = Stream.new()
            
            async def on_message(message: SubscribeEvent):
                if message.type == "audio_output":
                    audio_data = base64.b64decode(message.data.encode("utf-8"))
                    audio_chunks.append(audio_data)
                    if on_audio_chunk:
                        on_audio_chunk(audio_data)
                    await stream.put(audio_data)
                elif message.type == "assistant_end":
                    # 음성 생성 완료
                    pass
            
            options = ChatConnectOptions(config_id=self.config_id) if self.config_id else ChatConnectOptions()
            
            async with client.empathic_voice.chat.connect_with_callbacks(
                options=options,
                on_open=lambda: print("🎤 Hume AI 연결됨"),
                on_message=on_message,
                on_close=lambda: print("🔇 Hume AI 연결 종료"),
                on_error=lambda err: print(f"❌ Hume AI 오류: {err}")
            ) as socket:
                # 텍스트 전송하여 음성 생성 요청
                await socket.send_text_input(text)
                
                # 응답 대기 (타임아웃 설정)
                await asyncio.sleep(5)  # 기본 대기 시간
                
        except Exception as e:
            print(f"❌ Hume TTS 오류: {e}")
            return b""
        
        return b"".join(audio_chunks)
    
    async def generate_speech_simple(
        self, 
        text: str,
        output_file: Optional[str] = None
    ) -> Optional[str]:
        """
        간단한 TTS 생성 (REST API 사용)
        
        Hume AI의 TTS REST API를 사용하여 텍스트를 음성으로 변환
        
        Args:
            text: 변환할 텍스트
            output_file: 저장할 파일 경로 (선택)
            
        Returns:
            저장된 파일 경로 또는 None
        """
        import aiohttp
        
        if not self.api_key:
            print("❌ HUME_API_KEY가 필요합니다.")
            return None
        
        print(f"🔊 [Hume TTS] 음성 생성 중... (텍스트 길이: {len(text)})")
        
        # Hume AI TTS REST API 엔드포인트
        url = "https://api.hume.ai/v0/evi/tts"
        
        headers = {
            "X-Hume-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "voice": {
                "name": "ITO"  # Hume 기본 음성
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        
                        if output_file:
                            with open(output_file, "wb") as f:
                                f.write(audio_data)
                            print(f"💾 [Hume TTS] 저장 완료: {output_file}")
                            return output_file
                        else:
                            # 임시 파일로 저장
                            temp_file = "hume_tts_output.mp3"
                            with open(temp_file, "wb") as f:
                                f.write(audio_data)
                            return temp_file
                    else:
                        error_text = await response.text()
                        print(f"❌ Hume TTS API 오류 ({response.status}): {error_text}")
                        return None
                        
        except Exception as e:
            print(f"❌ Hume TTS 오류: {e}")
            return None


class HumeInterviewerVoice:
    """
    AI 면접관 음성 서비스
    
    Hume AI를 사용하여 면접관의 자연스럽고 전문적인 음성을 생성
    """
    
    def __init__(self):
        self.tts_service = HumeTTSService()
        self.voice_config = HumeVoiceConfig()
        self._is_speaking = False
        
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    async def speak(
        self, 
        text: str, 
        emotion: str = "neutral",
        output_file: Optional[str] = None
    ) -> Optional[str]:
        """
        면접관이 말하기
        
        Args:
            text: 말할 내용
            emotion: 감정 (neutral, friendly, serious, encouraging)
            output_file: 저장할 파일 경로
            
        Returns:
            오디오 파일 경로
        """
        self._is_speaking = True
        
        try:
            # 감정에 따른 텍스트 전처리 (Hume가 자동으로 감정을 인식하지만, 힌트 제공)
            processed_text = self._add_emotion_context(text, emotion)
            
            result = await self.tts_service.generate_speech_simple(
                processed_text,
                output_file
            )
            
            return result
            
        finally:
            self._is_speaking = False
    
    def _add_emotion_context(self, text: str, emotion: str) -> str:
        """감정 컨텍스트 추가 (Hume AI가 더 잘 이해하도록)"""
        # Hume AI는 텍스트의 컨텍스트를 이해하므로 그대로 반환
        # 필요시 SSML 또는 특수 마커 추가 가능
        return text
    
    async def speak_question(self, question: str) -> Optional[str]:
        """면접 질문 음성 생성"""
        return await self.speak(question, emotion="professional")
    
    async def speak_feedback(self, feedback: str, is_positive: bool = True) -> Optional[str]:
        """피드백 음성 생성"""
        emotion = "encouraging" if is_positive else "serious"
        return await self.speak(feedback, emotion=emotion)
    
    async def speak_greeting(self) -> Optional[str]:
        """인사말 음성 생성"""
        greeting = "안녕하세요. 오늘 면접을 진행하게 된 AI 면접관입니다. 편하게 임해주시면 됩니다."
        return await self.speak(greeting, emotion="friendly")
    
    async def speak_closing(self) -> Optional[str]:
        """종료 인사 음성 생성"""
        closing = "수고하셨습니다. 오늘 면접은 여기서 마치겠습니다. 좋은 결과 있으시길 바랍니다."
        return await self.speak(closing, emotion="friendly")


# ========== FastAPI 엔드포인트 통합 ==========

def create_tts_router():
    """FastAPI 라우터 생성"""
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import FileResponse, StreamingResponse
    from pydantic import BaseModel
    
    router = APIRouter(prefix="/tts", tags=["TTS"])
    interviewer_voice = HumeInterviewerVoice()
    
    class TTSRequest(BaseModel):
        text: str
        emotion: str = "neutral"
    
    @router.post("/speak")
    async def speak(request: TTSRequest):
        """텍스트를 음성으로 변환"""
        output_file = f"tts_output_{hash(request.text) % 10000}.mp3"
        result = await interviewer_voice.speak(
            request.text, 
            request.emotion,
            output_file
        )
        
        if result:
            return FileResponse(
                result,
                media_type="audio/mpeg",
                filename="speech.mp3"
            )
        else:
            raise HTTPException(status_code=500, detail="TTS 생성 실패")
    
    @router.post("/question")
    async def speak_question(request: TTSRequest):
        """면접 질문 음성 생성"""
        result = await interviewer_voice.speak_question(request.text)
        
        if result:
            return FileResponse(result, media_type="audio/mpeg")
        else:
            raise HTTPException(status_code=500, detail="TTS 생성 실패")
    
    @router.get("/greeting")
    async def greeting():
        """인사말 음성"""
        result = await interviewer_voice.speak_greeting()
        
        if result:
            return FileResponse(result, media_type="audio/mpeg")
        else:
            raise HTTPException(status_code=500, detail="TTS 생성 실패")
    
    @router.get("/status")
    async def status():
        """TTS 서비스 상태 확인"""
        return {
            "service": "Hume AI TTS",
            "api_key_configured": bool(HUME_API_KEY),
            "config_id_configured": bool(HUME_CONFIG_ID),
            "is_speaking": interviewer_voice.is_speaking
        }
    
    return router


# ========== 테스트 함수 ==========

async def test_hume_tts():
    """Hume TTS 테스트"""
    print("=" * 50)
    print("Hume AI TTS 테스트")
    print("=" * 50)
    
    if not HUME_API_KEY:
        print("❌ HUME_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 다음을 추가하세요:")
        print("   HUME_API_KEY=your_api_key_here")
        return
    
    interviewer = HumeInterviewerVoice()
    
    # 테스트 질문
    test_text = "자기소개를 해주시겠습니까?"
    print(f"\n테스트 텍스트: {test_text}")
    
    result = await interviewer.speak_question(test_text)
    
    if result:
        print(f"✅ 음성 파일 생성 완료: {result}")
    else:
        print("❌ 음성 생성 실패")


if __name__ == "__main__":
    asyncio.run(test_hume_tts())
