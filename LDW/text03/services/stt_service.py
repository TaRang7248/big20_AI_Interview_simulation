import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class STTService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)

    async def transcribe_from_blob(self, audio_data: bytes, filename: str = "temp_audio.wav"):
        """Transcribes audio data provided as bytes using OpenAI Whisper."""
        temp_path = os.path.join("static", filename)
        os.makedirs("static", exist_ok=True)
        
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        try:
            with open(temp_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    language="ko"
                )
            return transcript.text
        except Exception as e:
            print(f"STT Error: {e}")
            return ""
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
