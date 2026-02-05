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

class STTService:
    def __init__(self):
        pass

    async def transcribe(self, file_path: str):
        return await transcribe_audio(file_path)

    def start_recording(self):
        print("Warning: Server-side recording is not supported in this environment.")

    def stop_recording(self):
        print("Warning: Server-side recording is not supported in this environment.")
        return None
