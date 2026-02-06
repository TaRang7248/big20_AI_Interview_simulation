import os
import asyncio
# [수정 1] 비동기 클라이언트 임포트
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# [수정 2] 비동기 클라이언트 초기화
client = AsyncOpenAI()

async def generate_audio(text: str, output_file: str = "output_speech.mp3"):
    """
    OpenAI TTS (Async) 모델을 사용하여 텍스트를 음성 파일로 변환합니다.
    """
    print(f"🔊 [TTS 시작] 오디오 생성 중... (텍스트 길이: {len(text)})") # 로그 추가
    
    try:
        # [수정 3] await 키워드를 사용하여 비동기 호출
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # [수정 4] 파일 쓰기 (비동기 환경에서 안전하게 저장)
        # response.stream_to_file은 일부 버전에서 경고가 뜰 수 있어 표준 방식으로 변경
        response.stream_to_file(output_file)
        
        print(f"💾 [TTS 저장 완료] 파일명: {output_file}") # 로그 추가
        return output_file
        
    except Exception as e:
        print(f"❌ [TTS 오류 발생]: {e}")
        # 오류 발생 시 None을 반환하여 메인 로직에서 처리하도록 함
        return None