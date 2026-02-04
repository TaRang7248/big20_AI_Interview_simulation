import os
import wave
import pyaudio
import threading
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class STTService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.is_recording = False
        self.frames = []
        self.p = pyaudio.PyAudio()
        self.stream = None

    def start_recording(self):
        if self.is_recording:
            return
        
        self.is_recording = True
        self.frames = []
        
        # Audio configuration
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000 # Whisper works well with 16k

        self.stream = self.p.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)

        def record():
            while self.is_recording:
                data = self.stream.read(CHUNK)
                self.frames.append(data)

        self.thread = threading.Thread(target=record)
        self.thread.start()

    def stop_recording(self, filename="recording.wav"):
        if not self.is_recording:
            return None

        self.is_recording = False
        self.thread.join()

        self.stream.stop_stream()
        self.stream.close()

        # Save as WAV
        filepath = os.path.join("static", filename)
        os.makedirs("static", exist_ok=True)
        
        wf = wave.open(filepath, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        return filepath

    async def transcribe(self, filepath: str):
        """Transcribes audio file using OpenAI Whisper."""
        try:
            with open(filepath, "rb") as audio_file:
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
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

    async def transcribe_from_blob(self, audio_data: bytes, filename: str = "temp_audio.wav"):
        """Transcribes audio data provided as bytes (backward compatibility)."""
        temp_path = os.path.join("static", filename)
        os.makedirs("static", exist_ok=True)
        
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        return await self.transcribe(temp_path)
