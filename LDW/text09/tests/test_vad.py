import os
import sys
# Add parent directory to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import soundfile as sf
import librosa
from app.services.vad_service import calculate_average_rms, check_vad_activity

def create_silent_audio(filename, duration=1.0, sr=16000):
    y = np.zeros(int(duration * sr))
    sf.write(filename, y, sr)
    return filename

def create_noise_audio(filename, duration=1.0, sr=16000, amplitude=0.001):
    y = np.random.uniform(-amplitude, amplitude, int(duration * sr))
    sf.write(filename, y, sr)
    return filename

def create_loud_audio(filename, duration=1.0, sr=16000, amplitude=0.5):
    # Create a sine wave to simulate "loud" sound (though VAD might not see it as speech, RMS will be high)
    t = np.linspace(0, duration, int(duration * sr))
    y = amplitude * np.sin(2 * np.pi * 440 * t) # 440Hz sine wave
    sf.write(filename, y, sr)
    return filename

def test_vad_service():
    print("Testing VAD Service...")
    
    # 1. Test Silence
    silent_file = "test_silence.wav"
    create_silent_audio(silent_file)
    rms = calculate_average_rms(silent_file)
    vad = check_vad_activity(silent_file)
    print(f"[Silence] RMS: {rms:.5f} (Expected ~0.0), VAD: {vad:.2f} (Expected 0.0)")
    
    if rms < 0.001 and vad == 0.0:
        print("✅ Silence Test Passed")
    else:
        print("❌ Silence Test Failed")
        
    # 2. Test Low Noise
    noise_file = "test_noise.wav"
    create_noise_audio(noise_file, amplitude=0.001)
    rms_noise = calculate_average_rms(noise_file)
    vad_noise = check_vad_activity(noise_file)
    print(f"[Noise] RMS: {rms_noise:.5f} (Expected Low), VAD: {vad_noise:.2f} (Expected Low)")
    
    if rms_noise < 0.002: # Threshold in stt_service is 0.002
        print("✅ Low Noise Test Passed (RMS below threshold)")
    else:
        print("⚠️ Low Noise Test RMS high? Check amplitude.")

    # 3. Test Loud Audio (Sine Wave)
    loud_file = "test_loud.wav"
    create_loud_audio(loud_file, amplitude=0.5)
    rms_loud = calculate_average_rms(loud_file)
    print(f"[Loud] RMS: {rms_loud:.5f} (Expected High)")
    
    if rms_loud > 0.1:
        print("✅ Loud Audio RMS Test Passed")
    else:
        print("❌ Loud Audio RMS Test Failed")

    # Cleanup
    if os.path.exists(silent_file): os.remove(silent_file)
    if os.path.exists(noise_file): os.remove(noise_file)
    if os.path.exists(loud_file): os.remove(loud_file)

if __name__ == "__main__":
    test_vad_service()
