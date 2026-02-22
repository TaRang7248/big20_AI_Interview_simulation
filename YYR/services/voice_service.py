"""
YYR/services/voice_service.py

목표:
- 브라우저(프론트)에서 업로드된 오디오(audio/webm 등)를 STT로 텍스트 변환
- 기본 공급자: Google Cloud Speech-to-Text
- (옵션) Deepgram도 남겨두되, 기본 흐름에서는 사용하지 않음

사전조건:
- PowerShell에서 GOOGLE_APPLICATION_CREDENTIALS 환경변수 설정 완료
- pip install google-cloud-speech 완료
"""

import os
import asyncio
from typing import Optional

import httpx
from dotenv import load_dotenv
from google.cloud import speech

load_dotenv()

# (옵션) Deepgram 키가 있으면 사용할 수 있지만, 기본은 Google
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


# =========================
# Public API
# =========================
async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
    """
    오디오 바이트를 텍스트로 변환해서 반환.
    기본: Google Cloud STT
    """
    text = await _transcribe_with_google_cloud(audio_bytes, mimetype)
    return (text or "").strip()


def handle_web_speech_transcript(transcript: str) -> str:
    """
    (참고) Web Speech는 브라우저에서만 가능.
    프론트가 텍스트를 만들어 보내는 경우를 대비한 자리.
    """
    return (transcript or "").strip()


# =========================
# Google Cloud STT
# =========================
def _guess_google_encoding(mimetype: str) -> speech.RecognitionConfig.AudioEncoding:
    mt = (mimetype or "").lower()

    # 브라우저 MediaRecorder 기본은 보통 webm/opus
    if "webm" in mt:
        return speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
    if "ogg" in mt or "opus" in mt:
        return speech.RecognitionConfig.AudioEncoding.OGG_OPUS
    if "wav" in mt or "wave" in mt:
        return speech.RecognitionConfig.AudioEncoding.LINEAR16

    # 모르면 일단 webm opus로 시도
    return speech.RecognitionConfig.AudioEncoding.WEBM_OPUS


def _guess_sample_rate(encoding: speech.RecognitionConfig.AudioEncoding) -> int:
    # Opus 계열은 48kHz가 일반적
    if encoding in (
        speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    ):
        return 48000
    # WAV/LINEAR16은 16k로 가정 (환경에 따라 다를 수 있음)
    return 16000


def _sync_google_stt(audio_bytes: bytes, mimetype: str) -> str:
    """
    google-cloud-speech SDK는 동기라서 동기 함수로 구현 후,
    async wrapper에서 to_thread로 호출한다.
    """
    client = speech.SpeechClient()

    encoding = _guess_google_encoding(mimetype)
    sample_rate_hertz = _guess_sample_rate(encoding)

    config = speech.RecognitionConfig(
        encoding=encoding,
        sample_rate_hertz=sample_rate_hertz,
        language_code="ko-KR",
        enable_automatic_punctuation=True,
        # 필요하면 옵션 추가 가능:
        # model="latest_long",
    )

    audio = speech.RecognitionAudio(content=audio_bytes)
    response = client.recognize(config=config, audio=audio)

    if not response.results:
        return ""

    # 모든 결과를 합쳐서 반환 (짧은 발화도 누락 덜함)
    parts = []
    for r in response.results:
        if r.alternatives:
            parts.append(r.alternatives[0].transcript)

    return " ".join([p for p in parts if p]).strip()


async def _transcribe_with_google_cloud(audio_bytes: bytes, mimetype: str) -> str:
    try:
        return await asyncio.to_thread(_sync_google_stt, audio_bytes, mimetype)
    except Exception as e:
        # mimetype이 찍히면 디버깅이 쉬움
        raise Exception(f"Google STT Error (mimetype={mimetype}): {e}")


# =========================
# (Optional) Deepgram STT
# =========================
async def transcribe_audio_deepgram(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
    """
    필요 시 Deepgram으로 STT하고 싶을 때만 호출.
    기본 로직에서는 사용하지 않음.
    """
    return (await _transcribe_with_deepgram(audio_bytes, mimetype)).strip()


async def _transcribe_with_deepgram(audio_bytes: bytes, mimetype: str) -> str:
    if not DEEPGRAM_API_KEY:
        raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

    url = "https://api.deepgram.com/v1/listen"
    params = {
        "model": "nova-2",
        "language": "ko",
        "smart_format": "true",
        "filler_words": "true",
    }
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": mimetype,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, headers=headers, content=audio_bytes)

    if response.status_code != 200:
        raise Exception(f"Deepgram STT Error: {response.text}")

    data = response.json()
    try:
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError):
        return ""

# 네번째
# # 오디오 파일을 받아 텍스트로 변환(STT)

# import os
# import httpx
# from dotenv import load_dotenv

# # =========================
# # 환경 변수 로드
# # =========================
# load_dotenv()

# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


# # ==========================================================
# # [STT 공용 진입점]
# # - Deepgram / Google Cloud STT: (audio_bytes -> transcript)
# # - Google Web Speech: (브라우저에서 transcript 생성 후 백엔드로 전달)
# # ==========================================================
# async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
#     """
#     👉 아래 return 줄 중
#        '주석이 없는 단 하나'만 실제로 실행됨
#     """

#     # =========================
#     # 1️⃣ Deepgram STT 사용 (audio_bytes -> text)
#     # =========================
#     return await _transcribe_with_deepgram(audio_bytes, mimetype)

#     # =========================
#     # 2️⃣ Google Cloud STT 사용 (audio_bytes -> text)
#     # =========================
#     # return await _transcribe_with_google_cloud(audio_bytes, mimetype)

#     # =========================
#     # 3️⃣ Google Web Speech 사용 (주의)
#     # =========================
#     # ❌ 백엔드에서 Web Speech로 STT 불가능
#     # ✅ Web Speech는 프론트(브라우저)에서 텍스트를 만든 뒤,
#     #    백엔드로 "텍스트"만 전달해야 함
#     #
#     # 따라서 여기서는 "audio_bytes를 텍스트로" 변환할 수 없음.
#     # 대신 아래의 별도 함수 handle_web_speech_transcript()를 사용.


# # ==========================================================
# # [3️⃣ Google Web Speech 대비용 - 텍스트 수신 함수]
# # ==========================================================
# def handle_web_speech_transcript(transcript: str) -> str:
#     """
#     Google Web Speech API는 브라우저에서 STT를 수행하고
#     결과 transcript(문자열)를 백엔드로 보냄.

#     이 함수는:
#     - 프론트가 보낸 transcript를 "그대로" 받아
#     - 이후 저장/평가 로직에 동일하게 태울 수 있도록
#       형식을 통일하는 자리

#     지금은 단순히 문자열을 반환하지만,
#     필요하면 여기서 전처리(공백 정리 등)를 할 수 있음.
#     """
#     return transcript or ""


# # ==========================================================
# # [1️⃣ Deepgram 전용 STT 구현]
# # ==========================================================
# async def _transcribe_with_deepgram(audio_bytes: bytes, mimetype: str) -> str:

#     # =========================
#     # Deepgram API Key 확인
#     # =========================
#     if not DEEPGRAM_API_KEY:
#         raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

#     # =========================
#     # Deepgram STT 엔드포인트
#     # =========================
#     url = "https://api.deepgram.com/v1/listen"

#     # =========================
#     # Deepgram 모델 선택 (주석 스위치)
#     # =========================
#     params = {
#         # "model": "nova",       # 기본 모델
#         "model": "nova-2",       # 정확도 개선 모델 (현재 사용)
#         # "model": "base",       # 레거시 모델
#         # "model": "enhanced",   # 레거시 고급 모델

#         "language": "ko",
#         "smart_format": "true",
#         "filler_words": "true"
#     }

#     # =========================
#     # Deepgram 인증 헤더
#     # =========================
#     headers = {
#         "Authorization": f"Token {DEEPGRAM_API_KEY}",
#         "Content-Type": mimetype
#     }

#     # =========================
#     # Deepgram 서버에 음성 전송
#     # =========================
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             url,
#             params=params,
#             headers=headers,
#             content=audio_bytes
#         )

#     # =========================
#     # Deepgram 응답 확인
#     # =========================
#     if response.status_code != 200:
#         raise Exception(f"Deepgram STT Error: {response.text}")

#     # =========================
#     # Deepgram 응답 파싱
#     # =========================
#     data = response.json()
#     try:
#         return data["results"]["channels"][0]["alternatives"][0]["transcript"]
#     except (KeyError, IndexError):
#         return ""


# # ==========================================================
# # [2️⃣ Google Cloud STT 전용 자리]
# # ==========================================================
# async def _transcribe_with_google_cloud(audio_bytes: bytes, mimetype: str) -> str:
#     """
#     Google Cloud Speech-to-Text 전용 구현 영역
#     - 인증: 서비스 계정 (GOOGLE_APPLICATION_CREDENTIALS 등)
#     - 호출 방식: Google SDK 사용 (Deepgram처럼 httpx.post로 끝나지 않음)
#     """
#     raise NotImplementedError("Google Cloud STT 미구현")


# 세번째
# import os
# import httpx
# from dotenv import load_dotenv

# # =========================
# # 환경 변수 로드
# # =========================
# load_dotenv()

# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
# # Google Cloud STT는 보통
# # GOOGLE_APPLICATION_CREDENTIALS 환경변수를 사용함
# # (서비스 계정 JSON 경로)
# # → 여기서는 아직 실제 코드 없음


# # ==========================================================
# # [공용 진입점 함수]
# # 이 함수는 "어떤 STT를 쓰든" 항상 이 이름으로 호출됨
# # ==========================================================
# async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
#     """
#     STT provider switch area.

#     👉 아래 return 줄 중
#        '주석이 없는 단 하나'만 실제로 실행됨

#     - Deepgram 사용 시: _transcribe_with_deepgram()
#     - Google Cloud STT 사용 시: _transcribe_with_google_cloud()
#     """

#     # =========================
#     # 1️⃣ Deepgram STT 사용
#     # =========================
#     return await _transcribe_with_deepgram(audio_bytes, mimetype)

#     # =========================
#     # 2️⃣ Google Cloud STT 사용
#     # (지금은 미구현 상태)
#     # =========================
#     # return await _transcribe_with_google_cloud(audio_bytes, mimetype)


# # ==========================================================
# # [Deepgram 전용 STT 함수]
# # 👉 여기 안의 코드는 Deepgram에서만 사용 가능
# # ==========================================================
# async def _transcribe_with_deepgram(audio_bytes: bytes, mimetype: str) -> str:
#     """
#     Deepgram STT implementation.

#     - Deepgram REST API 사용
#     - nova-2 모델 사용
#     - 한국어 + 스마트 포맷팅 + filler words 활성화
#     """

#     # Deepgram API Key 확인
#     if not DEEPGRAM_API_KEY:
#         raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

#     # Deepgram STT 엔드포인트
#     url = "https://api.deepgram.com/v1/listen"

#     # =========================
#     # Deepgram 모델 설정
#     # =========================
#     params = {
#         # Deepgram STT 모델 선택
#         # (주석을 바꿔서 Deepgram 내부 모델 비교 가능)
#         # "model": "nova",      # 기본 모델
#         "model": "nova-2",      # 정확도 개선 모델 (현재 사용)
#         # "model": "base",      # 레거시 모델
#         # "model": "enhanced",  # 레거시 고급 모델

#         "language": "ko",
#         "smart_format": "true",

#         # '음', '어' 같은 추임새도 인식
#         # 면접 답변 분석용
#         "filler_words": "true"
#     }

#     # Deepgram 인증 헤더
#     headers = {
#         "Authorization": f"Token {DEEPGRAM_API_KEY}",
#         "Content-Type": mimetype
#     }

#     # =========================
#     # Deepgram 서버에 음성 전송
#     # =========================
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             url,
#             params=params,
#             headers=headers,
#             content=audio_bytes
#         )

#     # 응답 오류 처리
#     if response.status_code != 200:
#         raise Exception(f"Deepgram STT Error: {response.text}")

#     # =========================
#     # Deepgram 응답 파싱
#     # =========================
#     data = response.json()

#     try:
#         # Deepgram 고유 응답 구조
#         return data["results"]["channels"][0]["alternatives"][0]["transcript"]
#     except (KeyError, IndexError):
#         return ""


# # ==========================================================
# # [Google Cloud STT 전용 함수]
# # 👉 Deepgram 코드와 절대 섞이지 않음
# # ==========================================================
# async def _transcribe_with_google_cloud(audio_bytes: bytes, mimetype: str) -> str:
#     """
#     Google Cloud Speech-to-Text implementation.

#     ⚠️ 현재는 자리만 잡아둔 상태
#     ⚠️ 실제 SDK 코드가 들어가야 동작함
#     """

#     raise NotImplementedError(
#         "Google Cloud STT 코드는 아직 구현되지 않았습니다."
#     )


# # 두번째

# import os
# import httpx
# from dotenv import load_dotenv

# load_dotenv()

# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# # Google Cloud는 보통 아래 둘 중 하나로 인증함:
# # 1) 환경변수에 서비스계정 JSON 경로 지정:
# #    set GOOGLE_APPLICATION_CREDENTIALS="C:\path\sa.json"
# # 2) 또는 런타임에 JSON 로드(여기서는 생략)

# async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
#     """
#     Switch STT provider by commenting/uncommenting one line below.
#     """

#     # 1) Deepgram (현재)
#     return await _transcribe_with_deepgram(audio_bytes, mimetype)

#     # 2) Google Cloud STT (시험용)
#     # return await _transcribe_with_google_cloud(audio_bytes, mimetype)


# async def _transcribe_with_deepgram(audio_bytes: bytes, mimetype: str) -> str:
#     if not DEEPGRAM_API_KEY:
#         raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

#     url = "https://api.deepgram.com/v1/listen"
#     params = {
#         "model": "nova-2",
#         "language": "ko",
#         "smart_format": "true",
#         "filler_words": "true"
#     }
#     headers = {
#         "Authorization": f"Token {DEEPGRAM_API_KEY}",
#         "Content-Type": mimetype
#     }

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(url, params=params, headers=headers, content=audio_bytes)

#     if response.status_code != 200:
#         raise Exception(f"Deepgram STT Error: {response.text}")

#     data = response.json()
#     try:
#         return data["results"]["channels"][0]["alternatives"][0]["transcript"]
#     except (KeyError, IndexError):
#         return ""


# async def _transcribe_with_google_cloud(audio_bytes: bytes, mimetype: str) -> str:
#     """
#     NOTE:
#     - This is a placeholder for Google Cloud STT.
#     - Implementation differs (SDK call, audio encoding config needed).
#     """
#     raise NotImplementedError("Google Cloud STT 연결 코드를 여기에 추가해야 합니다.")





# 첫번째
# import os
# import httpx
# from dotenv import load_dotenv

# # 환경 변수 로드
# load_dotenv()

# DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
#     """
#     Deepgram Nova-2 모델을 사용하여 오디오를 텍스트로 변환합니다.
#     """
#     if not DEEPGRAM_API_KEY:
#         raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

#     url = "https://api.deepgram.com/v1/listen"
    
#     # Nova-2 모델 설정 (한국어 지원, 스마트 포맷팅 적용)
#     # filler_words=true: '음', '어' 같은 추임새도 인식 (면접 분석용)
#     params = {
#         "model": "nova-2",
#         "language": "ko",
#         "smart_format": "true",
#         "filler_words": "true" 
#     }

#     headers = {
#         "Authorization": f"Token {DEEPGRAM_API_KEY}",
#         "Content-Type": mimetype
#     }

#     # 타임아웃을 30초(또는 그 이상)로 늘려줍니다.
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(url, params=params, headers=headers, content=audio_bytes)
        
#     if response.status_code != 200:
#         raise Exception(f"Deepgram STT Error: {response.text}")

#     data = response.json()
    
#     # 변환된 텍스트 추출
#     try:
#         transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
#         return transcript
#     except (KeyError, IndexError):
#         return ""