# 오디오 파일을 받아 텍스트로 변환(STT)


import os
import httpx
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def transcribe_audio(audio_bytes: bytes, mimetype: str = "audio/webm") -> str:
    """
    Deepgram Nova-2 모델을 사용하여 오디오를 텍스트로 변환합니다.
    """
    if not DEEPGRAM_API_KEY:
        raise ValueError("DEEPGRAM_API_KEY가 설정되지 않았습니다.")

    url = "https://api.deepgram.com/v1/listen"
    
    # Nova-2 모델 설정 (한국어 지원, 스마트 포맷팅 적용)
    # filler_words=true: '음', '어' 같은 추임새도 인식 (면접 분석용)
    params = {
        "model": "nova-2",
        "language": "ko",
        "smart_format": "true",
        "filler_words": "true" 
    }

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": mimetype
    }

    # 타임아웃을 30초(또는 그 이상)로 늘려줍니다.
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, params=params, headers=headers, content=audio_bytes)
        
    if response.status_code != 200:
        raise Exception(f"Deepgram STT Error: {response.text}")

    data = response.json()
    
    # 변환된 텍스트 추출
    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript
    except (KeyError, IndexError):
        return ""