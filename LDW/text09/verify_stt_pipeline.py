import numpy as np
import soundfile as sf
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.stt_service import transcribe_audio, analyze_audio_features

def create_dummy_audio(filename="test_audio.wav", duration=3.0, sr=22050):
    t = np.linspace(0, duration, int(sr * duration))
    # Create a simple sine wave (440Hz)
    y = 0.5 * np.sin(2 * np.pi * 440 * t)
    # Add some noise
    noise = np.random.normal(0, 0.01, y.shape)
    y = y + noise
    sf.write(filename, y, sr)
    print(f"Created dummy audio: {filename}")
    return filename

def test_pipeline():
    audio_path = create_dummy_audio()
    
    print("--- Testing transcribe_audio ---")
    try:
        # 1. Test Analysis directly first (to isolate from API keys)
        import librosa
        y, sr = librosa.load(audio_path)
        analysis = analyze_audio_features(audio_path, y, sr)
        print("Analysis Result:", analysis)
        
        # 2. Test Full Pipeline (might fail if no API keys, but should run)
        # We expect it to handle missing keys gracefully
        result = transcribe_audio(audio_path)
        print("\nFull Pipeline Result Keys:", result.keys())
        print("Text:", result.get("text"))
        print("Analysis in Full Result:", result.get("analysis"))
        
        if "analysis" in result and "pitch_jitter" in result["analysis"]:
            print("\nSUCCESS: Analysis pipeline integration verified.")
        else:
            print("\nFAILURE: Analysis data missing.")
            
    except Exception as e:
        print(f"\nERROR during verification: {e}")
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists("test_audio_processed.wav"):
            os.remove("test_audio_processed.wav")

if __name__ == "__main__":
    test_pipeline()
