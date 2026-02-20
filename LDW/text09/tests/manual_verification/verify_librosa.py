
import librosa
import numpy as np

try:
    print("Testing librosa.get_duration(y=None, sr=None)")
    duration = librosa.get_duration(y=None, sr=None)
    print(f"Duration: {duration}")
except Exception as e:
    print(f"Caught expected error: {e}")
