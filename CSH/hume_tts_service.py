"""
Hume AI TTS 서비스
- Hume AI의 EVI(Empathic Voice Interface)를 사용한 감정적 TTS 구현
- 면접관의 음성을 자연스럽고 감정적으로 생성
"""

# 외부 라이브러리 및 시스템 도구
import asyncio  # 비동기 통신(실시간 대화)을 위한 필수 도구
import base64  # 음성 데이터(바이너리)를 텍스트 형태로 변환하여 전송하기 위함
import os  # 컴퓨터의 파일 경로, 환경 변수 등에 접근 (API 키 읽기용)
from dataclasses import dataclass  # 간단한 데이터 보관용 클래스를 만들기 위함

# 오디오 처리 관련 도구
# 타입 힌트와 데이터 구조 (가독성 향상)
from typing import Callable, Optional  # 코드의 안정성을 위해 타입을 명시

import httpx  # Hume AI 서비스 토큰 인증용

# 환경 변수 관리
from dotenv import load_dotenv  # .env 파일에서 API Key를 불러오는 도구

load_dotenv()  # 프로젝트 폴더 안에 있는 .env 파일을 찾아 그 안에 적힌 설정값들을 컴퓨터의 환경 변수로 등록해주는 함수

# Hume AI API 키 설정
HUME_API_KEY = os.getenv("HUME_API_KEY")
HUME_SECRET_KEY = os.getenv("HUME_SECRET_KEY")  # 토큰 인증용 Secret Key
HUME_CONFIG_ID = os.getenv("HUME_CONFIG_ID")  # EVI 설정 ID (선택사항)

# 토큰 캐싱용 전역 변수
_cached_access_token: Optional[str] = None  # 토큰을 저장할 임시 보관함
_token_expires_at: float = 0  # 토큰 만료 시간


async def get_hume_access_token() -> Optional[str]:
    """
    Hume AI OAuth2 토큰 인증

    API_KEY와 SECRET_KEY를 사용하여 액세스 토큰을 획득합니다.
    토큰은 캐싱되어 재사용됩니다.

    Returns:
        액세스 토큰 또는 None (인증 실패 시)
    """
    global _cached_access_token, _token_expires_at
    import time

    # 캐시된 토큰이 유효한지 확인 (만료 5분 전에 갱신)
    if _cached_access_token and time.time() < _token_expires_at - 300:
        return _cached_access_token

    if not HUME_API_KEY or not HUME_SECRET_KEY:
        print("⚠️ HUME_API_KEY 또는 HUME_SECRET_KEY가 설정되지 않았습니다.")
        return None

    try:
        # '키:비밀번호' 형태의 문자열을 컴퓨터가 통신하기 좋은 64진법(Base64) 암호로 변환
        auth = f"{HUME_API_KEY}:{HUME_SECRET_KEY}"
        encoded_auth = base64.b64encode(auth.encode()).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url="https://api.hume.ai/oauth2-cc/token",
                headers={"Authorization": f"Basic {encoded_auth}"},
                data={"grant_type": "client_credentials"},
            )

            if resp.status_code == 200:
                token_data = resp.json()
                _cached_access_token = token_data.get("access_token")
                # 토큰 만료 시간 설정 (기본 1시간, expires_in이 있으면 사용)
                expires_in = token_data.get("expires_in", 3600)
                _token_expires_at = time.time() + expires_in
                print("✅ Hume AI 토큰 인증 성공")
                return _cached_access_token
            else:
                print(f"❌ Hume AI 토큰 인증 실패: {resp.status_code} - {resp.text}")
                return None

    except Exception as e:
        print(f"❌ Hume AI 토큰 인증 오류: {e}")
        return None


@dataclass  # 데이터 클래스 사용
class HumeVoiceConfig:
    """Hume AI 음성 설정

    Octave 2 (version="2") 사용 시 한국어 포함 11개 언어 지원.
    ITO는 Hume AI Voice Library의 기본 음성으로,
    Octave 1/2 모두 호환됩니다.
    """

    voice_name: str = "ITO"  # Hume 기본 음성 (Octave 1/2 호환)
    language: str = "ko"  # 한국어 지원 (Octave 2 필수)
    speaking_rate: float = 1.0
    emotion_style: str = "professional"  # professional, friendly, empathetic


class HumeTTSService:
    """
    Hume AI EVI를 사용한 TTS(Text-To-Speech) 서비스

    특징:
    - 감정 인식 기반 자연스러운 음성 생성
    - 한국어 지원 (EVI 4-mini)
    - 실시간 스트리밍 가능
    """

    def __init__(self, api_key: Optional[str] = None, config_id: Optional[str] = None):
        self.api_key = api_key or HUME_API_KEY
        self.config_id = config_id or HUME_CONFIG_ID
        self._client = None
        # 서버에서 실시간으로 쏟아지는 목소리 데이터(오디오 조각들)를 차례대로 담아두는 '대기 줄'
        # 소리가 끊기지 않게 큐(Queue)에 쌓아두고 하나씩 꺼내서 들려주는 역할을 한다
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
        self, text: str, on_audio_chunk: Optional[Callable[[bytes], None]] = None
    ) -> bytes:
        """
        텍스트를 음성으로 변환 (스트리밍)

        Args:
            text: 변환할 텍스트
            on_audio_chunk: 오디오 청크가 도착할 때마다 호출되는 콜백

        Returns:
            전체 오디오 데이터 (bytes)
        """
        client = await self._get_client()  # Hume AI 서버와 대화할 Client 객체 얻기
        audio_chunks = []  # 서버에서 보내주는 짧은 소리 조각들(청크)을 하나씩 차곡차곡 모아둘 빈 리스트

        try:
            # Hume AI 전용 통신 도구들을 가져옵니다.
            from hume import Stream
            from hume.empathic_voice.chat.socket_client import ChatConnectOptions
            from hume.empathic_voice.chat.types import SubscribeEvent

            stream = Stream.new()  # 데이터를 담아서 흘려보낼 새로운 '파이프라인'을 하나 만든다. 이 파이프를 통해 음성 조각들을 차례대로 내보낸다.

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

            options = (
                ChatConnectOptions(config_id=self.config_id)
                if self.config_id
                else ChatConnectOptions()
            )

            async with client.empathic_voice.chat.connect_with_callbacks(
                options=options,
                on_open=lambda: print("🎤 Hume AI 연결됨"),
                on_message=on_message,
                on_close=lambda: print("🔇 Hume AI 연결 종료"),
                on_error=lambda err: print(f"❌ Hume AI 오류: {err}"),
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
        self, text: str, output_file: Optional[str] = None
    ) -> Optional[str]:
        """
        간단한 TTS 생성 (REST API 사용)

        Hume AI의 Octave TTS REST API를 사용하여 텍스트를 음성으로 변환합니다.
        인증은 X-Hume-Api-Key 헤더 방식만 지원됩니다.
        (OAuth2 Bearer 토큰은 TTS 엔드포인트에서 403 에러를 반환하므로 사용하지 않습니다)

        Args:
            text: 변환할 텍스트
            output_file: 저장할 파일 경로 (선택)

        Returns:
            저장된 파일 경로 또는 None
        """
        import json as _json  # JSON 응답 파싱용

        import aiohttp  # 비동기(Async) 방식으로 HTTP 통신(웹 요청)을 처리해주는 라이브러리

        print(f"🔊 [Hume TTS] 음성 생성 중... (텍스트 길이: {len(text)})")

        # ========== Hume Octave TTS REST API 엔드포인트 ==========
        # ⚠️ 주의: /v0/evi/tts 는 EVI(음성 대화) 전용이며 TTS와는 별도 서비스임
        # Octave TTS는 /v0/tts (non-streaming JSON) 또는 /v0/tts/file (파일 다운로드) 사용
        url = "https://api.hume.ai/v0/tts"

        # ========== 인증 헤더 구성 ==========
        # Hume TTS는 X-Hume-Api-Key 헤더 인증만 지원함
        # OAuth2 Bearer 토큰을 보내면 403 Forbidden ("Credentials were invalid for this resource")
        if not self.api_key:
            print("❌ HUME_API_KEY가 필요합니다. .env 파일에 추가해주세요.")
            return None

        headers = {
            "X-Hume-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        # ========== 전송 데이터(Payload) 구성 — Octave utterances 형식 ==========
        # Hume Octave TTS API는 'utterances' 배열 형식을 사용
        # 각 utterance에는 text, voice(name + provider), description(선택) 등이 포함됨
        #
        # ⚠️ 중요: "version": "2" (Octave 2) 필수!
        # - Octave 1 (기본값): 영어, 스페인어만 지원 → 한국어 텍스트를 영어 발음으로 읽어버림
        # - Octave 2: 한국어 포함 11개 언어 지원 (English, Japanese, Korean, Spanish,
        #   French, Portuguese, Italian, German, Russian, Hindi, Arabic)
        # - Octave 1 음성(ITO 등)은 Octave 2에서도 호환 사용 가능
        voice_name = (
            self.voice_config.voice_name if hasattr(self, "voice_config") else "ITO"
        )
        payload = {
            "version": "2",  # ★ Octave 2 사용 — 한국어 TTS 지원 필수 설정
            "utterances": [
                {
                    "text": text,
                    "voice": {
                        "name": voice_name,  # Hume 기본 음성 (ITO)
                        "provider": "HUME_AI",  # 필수: 음성 제공자 명시
                    },
                }
            ],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        # ========== 응답 파싱 — Octave TTS JSON 응답 형식 ==========
                        # /v0/tts 엔드포인트는 JSON으로 응답하며, 구조는 다음과 같음:
                        # {
                        #   "request_id": "...",
                        #   "generations": [
                        #     {
                        #       "generation_id": "...",
                        #       "duration": 1.23,
                        #       "file_size": 12345,
                        #       "encoding": "mp3",
                        #       "audio": "<base64 인코딩된 전체 오디오>",
                        #       "snippets": [...]
                        #     }
                        #   ]
                        # }
                        resp_text = await response.text()
                        resp_data = _json.loads(resp_text)

                        # generations 배열에서 첫 번째 생성 결과의 오디오 추출
                        generations = resp_data.get("generations", [])
                        if not generations:
                            print("❌ [Hume TTS] 응답에 generations 데이터가 없습니다.")
                            return None

                        # generation 최상위의 'audio' 필드에서 base64 오디오 직접 추출
                        # (snippets는 list of list 구조라 audio 필드가 없음)
                        audio_b64 = generations[0].get("audio", "")
                        if not audio_b64:
                            print("❌ [Hume TTS] 오디오 데이터를 추출할 수 없습니다.")
                            return None

                        audio_data = base64.b64decode(audio_b64)

                        # 파일로 저장
                        save_path = output_file or "hume_tts_output.mp3"
                        with open(save_path, "wb") as f:
                            f.write(audio_data)

                        print(
                            f"💾 [Hume TTS] 저장 완료: {save_path} ({len(audio_data)} bytes)"
                        )
                        return save_path
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
        # TTS 서비스에 음성 설정 공유 (음성 이름 등)
        self.tts_service.voice_config = self.voice_config
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def speak(
        self, text: str, emotion: str = "neutral", output_file: Optional[str] = None
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
                processed_text, output_file
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

    async def speak_feedback(
        self, feedback: str, is_positive: bool = True
    ) -> Optional[str]:
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
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/tts", tags=["TTS"])
    interviewer_voice = HumeInterviewerVoice()

    class TTSRequest(BaseModel):
        text: str
        emotion: str = "neutral"

    @router.post("/speak")
    async def speak(request: TTSRequest):
        """텍스트를 음성으로 변환"""
        output_file = f"tts_output_{hash(request.text) % 10000}.mp3"
        result = await interviewer_voice.speak(
            request.text, request.emotion, output_file
        )

        if result:
            return FileResponse(result, media_type="audio/mpeg", filename="speech.mp3")
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

    # 서비스가 정상적으로 작동하고 있는지, 설정은 제대로 되어 있는지 확인하는 상태 점검용 엔드포인트
    @router.get("/status")
    async def status():
        """찰 TTS 서비스 상태 확인"""
        return {
            "service": "Hume AI Octave TTS",
            "api_key_configured": bool(HUME_API_KEY),
            "config_id_configured": bool(HUME_CONFIG_ID),
            "is_speaking": interviewer_voice.is_speaking,
            "auth_method": "X-Hume-Api-Key",
            "endpoint": "/v0/tts",
        }

    @router.get("/test-token")
    async def test_token():
        """OAuth2 토큰 인증 테스트"""
        if not HUME_API_KEY or not HUME_SECRET_KEY:
            raise HTTPException(
                status_code=400,
                detail="HUME_API_KEY와 HUME_SECRET_KEY가 모두 필요합니다.",
            )

        token = await get_hume_access_token()
        if token:
            return {
                "success": True,
                "message": "토큰 인증 성공",
                "token_preview": f"{token[:20]}..." if len(token) > 20 else token,
            }
        else:
            raise HTTPException(status_code=500, detail="토큰 인증 실패")

    # ── Celery TTS 비동기 결과 조회 엔드포인트 ──
    # generate_tts_task.delay()로 제출된 TTS 태스크의 결과를 조회합니다.
    # 프론트엔드에서 tts_task_id로 폴링하여 고품질 Hume TTS 오디오를 가져올 수 있습니다.
    @router.get("/result/{task_id}")
    async def get_tts_result(task_id: str):
        """
        Celery TTS 태스크 결과 조회

        - PENDING: 태스크가 아직 처리 대기 중
        - STARTED: 태스크 처리 시작됨
        - SUCCESS: 완료 → audio_url 반환
        - FAILURE: 생성 실패
        """
        try:
            from celery.result import AsyncResult
            from celery_app import celery_app as _celery_app

            result = AsyncResult(task_id, app=_celery_app)
            state = result.state  # PENDING, STARTED, SUCCESS, FAILURE

            if state == "SUCCESS":
                # generate_tts_task 반환: {"audio_url": ..., "text_length": ..., ...}
                task_result = result.result
                audio_url = (
                    task_result.get("audio_url")
                    if isinstance(task_result, dict)
                    else None
                )
                if audio_url:
                    return {
                        "status": "completed",
                        "audio_url": audio_url,
                        "task_id": task_id,
                    }
                else:
                    return {
                        "status": "completed",
                        "audio_url": None,
                        "detail": "TTS 생성 완료했으나 오디오 파일 없음",
                        "task_id": task_id,
                    }
            elif state == "FAILURE":
                return {
                    "status": "failed",
                    "detail": str(result.info) if result.info else "TTS 생성 실패",
                    "task_id": task_id,
                }
            elif state == "STARTED":
                return {
                    "status": "processing",
                    "detail": "TTS 생성 처리 중",
                    "task_id": task_id,
                }
            else:
                # PENDING 또는 기타
                return {
                    "status": "pending",
                    "detail": "태스크 대기 중",
                    "task_id": task_id,
                }
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Celery가 사용 불가능합니다. Celery worker가 실행 중인지 확인하세요.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"태스크 조회 오류: {str(e)}",
            )

    # ── Celery TTS 프리페칭 엔드포인트 ──
    # 여러 텍스트에 대한 TTS를 한번에 백그라운드 생성 요청합니다.
    class PrefetchRequest(BaseModel):
        session_id: str
        texts: list[str]

    @router.post("/prefetch")
    async def prefetch_tts(request: PrefetchRequest):
        """
        여러 텍스트에 대한 TTS 프리페칭 (Celery 비동기)

        세션 생성 시 인사말, 종료 인사 등 고정 문구를 미리 생성합니다.
        """
        try:
            from celery_tasks import prefetch_tts_task

            task = prefetch_tts_task.delay(request.session_id, request.texts)
            return {
                "status": "submitted",
                "task_id": task.id,
                "text_count": len(request.texts),
                "session_id": request.session_id,
            }
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Celery가 사용 불가능합니다.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"프리페칭 태스크 제출 오류: {str(e)}",
            )

    return router
