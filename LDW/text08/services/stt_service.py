from openai import AsyncOpenAI
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def transcribe_audio(file_path: str):
    """
    Transcribe audio file using Whisper.
    """
    try:
        with open(file_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko" # Force Korean as requested
            )
        return transcript.text
    except Exception as e:
        print(f"STT Error: {e}")
        return ""
