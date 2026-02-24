import sys
import numpy as np

print(f"Numpy version: {np.__version__}")
print(f"Numpy dtype size: {np.dtype(np.int64).itemsize * 8} bits (object size: {np.dtype.__basicsize__})")

libraries = [
    "scipy", "pandas", "matplotlib", "sklearn", "tensorflow", "torch", 
    "cv2", "librosa", "pyannote.audio", "fastapi", "uvicorn", "pydantic"
]

for lib in libraries:
    try:
        print(f"Attempting to import {lib}...", end=" ", flush=True)
        __import__(lib)
        print("SUCCESS")
    except Exception as e:
        print(f"FAILED: {e}")
    except SystemExit:
        print("FAILED: SystemExit")
    except:
        print("FAILED: Unexpected error")
