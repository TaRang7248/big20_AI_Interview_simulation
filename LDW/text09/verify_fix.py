import os
import sys
import logging
import warnings
import numpy as np
import soundfile as sf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock valid audio file creation
def create_dummy_audio(filename="test_audio.wav", duration=2, sr=22050):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    x = 0.5 * np.sin(2 * np.pi * 440 * t) # 440Hz sine wave
    sf.write(filename, x, sr)
    return filename

def test_pipeline():
    print("--- Starting Pipeline Verification ---")
    
    # 1. Create Dummy Audio
    if not os.path.exists("test_uploads"):
        os.makedirs("test_uploads")
    
    audio_path = os.path.join("test_uploads", "verify_audio.wav")
    create_dummy_audio(audio_path)
    print(f"[OK] Created dummy audio: {audio_path}")

    try:
        from app.services.stt_service import transcribe_audio, preprocess_audio, analyze_audio_features
        
        # 2. Test Preprocessing
        print("Testing preprocess_audio...")
        processed_path, y, sr = preprocess_audio(audio_path)
        print(f"Preprocess Result: Path={processed_path}, Y_shape={y.shape if y is not None else 'None'}, SR={sr}")
        
        # 3. Test Analysis
        print("Testing analyze_audio_features...")
        analysis = analyze_audio_features(processed_path, y, sr)
        print("Analysis Result:", analysis)
        
        # 4. Test Full Pipeline (Mocking API calls would be ideal, but for now we test if it crashes)
        # Note: This might make API calls if keys are present.
        print("Testing transcribe_audio (Full Pipeline)...")
        result = transcribe_audio(audio_path)
        print("Full Pipeline Result Keys:", result.keys())
        
        print("\n[SUCCESS] Pipeline finished without crashing.")
        
    except ImportError as e:
        print(f"\n[ERROR] Import failed: {e}")
        print("Make sure you are running this from the project root.")
    except Exception as e:
        print(f"\n[FAIL] Pipeline crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline()
