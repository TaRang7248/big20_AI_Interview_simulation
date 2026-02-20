import shutil
import sys
import importlib.util
import os

def check_command(command):
    path = shutil.which(command)
    if path:
        print(f"[OK] '{command}' is installed at: {path}")
        return True
    else:
        print(f"[WARNING] '{command}' NOT found in PATH.")
        return False

def check_library(lib_name):
    spec = importlib.util.find_spec(lib_name)
    if spec:
        print(f"[OK] Python library '{lib_name}' is installed.")
        return True
    else:
        print(f"[ERROR] Python library '{lib_name}' NOT found.")
        return False

def main():
    print("--- Environment Check ---")
    
    # Check System Tools
    ffmpeg_ok = check_command("ffmpeg")
    ffprobe_ok = check_command("ffprobe")
    
    if not (ffmpeg_ok and ffprobe_ok):
        print("\n[CRITICAL WARNING] FFmpeg is missing or not in PATH.")
        print("Required for: librosa, pydub, and audio processing.")
        print("Without FFmpeg, audio analysis (jitter, shimmer) and conversion will FAIL inside specific libraries.")
        print("Solution: Install FFmpeg and add to system PATH.")
    
    # Check Python Libraries
    libs = ["librosa", "numpy", "soundfile", "pydub", "fastapi", "uvicorn", "google.generativeai"]
    all_libs_ok = True
    for lib in libs:
        if not check_library(lib):
            all_libs_ok = False
            
    if all_libs_ok:
        print("\n[OK] All required Python libraries are installed.")
    else:
        print("\n[ERROR] Some Python libraries are missing. Run: pip install -r requirements.txt")

    # Check API Keys (Basic check)
    from dotenv import load_dotenv
    load_dotenv()
    
    if os.getenv("GOOGLE_API_KEY"):
        print("[OK] GOOGLE_API_KEY is set.")
    else:
        print("[WARNING] GOOGLE_API_KEY is NOT set in .env")

if __name__ == "__main__":
    main()
