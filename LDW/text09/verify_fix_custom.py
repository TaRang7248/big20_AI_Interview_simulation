
import os
import sys
import logging
import numpy as np
import soundfile as sf
# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_dummy_wav(filename):
    sr = 22050
    t = np.linspace(0, 1, int(sr * 1), endpoint=False)
    x = 0.5 * np.sin(2 * np.pi * 440 * t)
    
    # Write WAV
    sf.write(filename, x, sr)
    return filename

def test_webm_handling():
    print("--- Testing WebM Handling and Fix ---")
    
    # 1. Create a dummy WAV file
    wav_path = "test_input.wav"
    create_dummy_wav(wav_path)
    
    # 2. Rename to .webm (It's a fake webm, but librosa/sf might try to read it)
    #    Real webm creation requires ffmpeg, which might not be in the path for this script environment easily.
    #    But we want to test if 'preprocess_audio' handles the *output* filename correctly.
    
    #    The critical fix was:
    #    sf.write(output_path, y_norm, sr)  <-- failing if output_path ended in .webm
    
    #    So we simulate that by calling preprocess_audio with a file named .webm
    webm_path = "test_input.webm"
    if os.path.exists(webm_path): os.remove(webm_path)
    if os.path.exists(wav_path):
        os.rename(wav_path, webm_path)
    
    try:
        from app.services.stt_service import preprocess_audio
        
        print(f"Testing preprocess_audio with {webm_path}...")
        
        # This might fail to load if librosa doesn't like WAV header in .webm file, 
        # but if it LOADS (because librosa sniffs headers), 
        # then we verify if it SAVES correctly as .wav (the fix).
        
        processed_path, y, sr = preprocess_audio(webm_path)
        
        print(f"Result Path: {processed_path}")
        
        if processed_path.endswith(".wav"):
            print("[SUCCESS] Output file extension is .wav")
        else:
            print(f"[FAIL] Output file extension is not .wav: {processed_path}")
            
        if os.path.exists(processed_path):
            print("[SUCCESS] Processed file created.")
        else:
            print("[FAIL] Processed file NOT created.")

    except Exception as e:
        print(f"[FAIL] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(wav_path): os.remove(wav_path)
        if os.path.exists(webm_path): os.remove(webm_path)
        # Processed file cleanup
        expected_out = "test_input_processed.wav"
        if os.path.exists(expected_out): os.remove(expected_out)

if __name__ == "__main__":
    test_webm_handling()
