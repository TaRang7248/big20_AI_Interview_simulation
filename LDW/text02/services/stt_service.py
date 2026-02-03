import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class STTService:
    def __init__(self):
        self.client = OpenAI()

    async def transcribe_audio(self, audio_file_path):
        """
        Transcribes audio from a file path using OpenAI Whisper.
        """
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        with open(audio_file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko"
            )
        return transcript.text

    async def transcribe_from_blob(self, audio_data: bytes, filename: str = "temp_audio.wav"):
        """
        Transcribes audio from raw bytes (blob).
        """
        temp_path = os.path.join("static", filename)
        os.makedirs("static", exist_ok=True)
        
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        try:
            text = await self.transcribe_audio(temp_path)
            return text
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
