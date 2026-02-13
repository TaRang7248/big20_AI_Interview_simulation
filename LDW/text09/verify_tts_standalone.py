
import asyncio
import edge_tts
import os

CACHE_DIR = "uploads/tts_audio"
OUTPUT_FILE = os.path.join(CACHE_DIR, "verify_tts_output.mp3")
TEXT = "안녕하세요, 이것은 Microsoft Edge TTS 테스트 음성입니다. 목소리가 잘 들리시나요?"
VOICE = "ko-KR-HyunsuMultilingualNeural"

async def verify_tts():
    print(f"Checking for output directory: {CACHE_DIR}")
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        print(f"Created directory: {CACHE_DIR}")
    
    print(f"Generating TTS audio for text: '{TEXT}'")
    print(f"Using voice: {VOICE}")
    
    try:
        communicate = edge_tts.Communicate(TEXT, VOICE)
        await communicate.save(OUTPUT_FILE)
        
        if os.path.exists(OUTPUT_FILE):
             file_size = os.path.getsize(OUTPUT_FILE)
             print(f"✅ Success! Audio file generated at: {OUTPUT_FILE}")
             print(f"File size: {file_size} bytes")
             if file_size > 0:
                 print("Verification PASSED: File is not empty.")
             else:
                 print("Verification FAILED: File is empty.")
        else:
             print("Verification FAILED: File was not created.")
             
    except Exception as e:
        print(f"❌ Error during TTS generation: {e}")

if __name__ == "__main__":
    asyncio.run(verify_tts())
