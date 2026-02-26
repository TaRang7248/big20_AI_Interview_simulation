import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI()

AUDIO_DIR = os.path.join(os.getcwd(), "generated_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

async def generate_audio(text: str, output_file: str = "response.mp3") -> str:
    out_path = os.path.join(AUDIO_DIR, output_file)

    print(f"🔊 [TTS 시작] 오디오 생성 중... (텍스트 길이: {len(text)})")

    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )

        response.stream_to_file(out_path)

        print(f"💾 [TTS 저장 완료] 경로: {out_path}")
        return out_path

    except Exception as e:
        print(f"❌ [TTS 오류 발생]: {e}")
        return None