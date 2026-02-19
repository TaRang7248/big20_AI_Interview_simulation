
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.stt_service import transcribe_audio
from app.config import GOOGLE_API_KEY, AUDIO_FOLDER

def test_stt():
    print("Testing STT with Gemini...")
    if not GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not found.")
        return

    # Use a dummy audio file or check if one exists in AUDIO_FOLDER
    # For this test, we might need a real file. 
    # Let's check if there are any files in AUDIO_FOLDER, if not warn user.
    
    audio_files = [f for f in os.listdir(AUDIO_FOLDER) if f.endswith('.webm') or f.endswith('.wav') or f.endswith('.mp3')]
    
    if not audio_files:
        print(f"No audio files found in {AUDIO_FOLDER}. Please place a test file there.")
        # Create a dummy file for syntax check if possible, but STT needs real audio.
        return

    test_file = os.path.join(AUDIO_FOLDER, audio_files[0])
    print(f"Using test file: {test_file}")
    
    try:
        result = transcribe_audio(test_file)
        print("\n--- STT Result ---")
        print(result)
        print("------------------")
    except Exception as e:
        print(f"STT Failed: {e}")

if __name__ == "__main__":
    test_stt()
