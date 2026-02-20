import os
import sys

# Import app.config to trigger the path injection
try:
    from app.config import ffmpeg_path
    print(f"[Check] app.config loaded successfully.")
except ImportError:
    print(f"[Error] Could not import app.config. Make sure you are running this from C:\\big20\\big20_AI_Interview_simulation\\LDW\\text09")
    sys.exit(1)

print(f"[Check] Checking PATH environment variable...")
path_env = os.environ.get("PATH", "")

if r"C:\ffmpeg\bin" in path_env:
    print(f"[Success] C:\\ffmpeg\\bin is present in PATH.")
else:
    print(f"[Failure] C:\\ffmpeg\\bin is NOT in PATH.")

print(f"[Check] Testing pydub/librosa dependency check (simulated)...")
import shutil
ffmpeg_exe = shutil.which("ffmpeg")
if ffmpeg_exe:
    print(f"[Success] ffmpeg executable found at: {ffmpeg_exe}")
else:
    print(f"[Failure] ffmpeg executable NOT found by shutil.which().")

print("\nVerification Complete.")
