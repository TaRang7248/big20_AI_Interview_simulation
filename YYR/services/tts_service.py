import os
from typing import Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI()

# ✅ 실행 위치(os.getcwd())가 아니라, 이 파일 위치 기준으로 고정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # YYR/
AUDIO_DIR = os.path.join(BASE_DIR, "generated_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

async def generate_audio(text: str, output_file: str = "response.mp3") -> Optional[str]:
    """
    AI 텍스트를 mp3로 저장하고,
    프론트에서 재생 가능한 URL path('/generated_audio/...')를 반환한다.
    """
    if not text or not text.strip():
        print("❌ [TTS] 입력 텍스트가 비어있음")
        return None

    filename = output_file  # e.g. "response_123.mp3"
    out_path = os.path.join(AUDIO_DIR, filename)

    print(f"🔊 [TTS 시작] 오디오 생성 중... (텍스트 길이: {len(text)})")
    print(f"📁 [TTS 저장 경로] {out_path}")

    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )

        # OpenAI SDK는 동기 방식으로 파일 저장 제공(stream_to_file)
        response.stream_to_file(out_path)

        print(f"💾 [TTS 저장 완료] 파일명: {filename}")
        # ✅ StaticFiles mount: /generated_audio
        return f"/generated_audio/{filename}"

    except Exception as e:
        print(f"❌ [TTS 오류 발생]: {e}")
        return None