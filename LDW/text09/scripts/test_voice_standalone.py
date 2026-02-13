import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import edge_tts
import os

VOICE = "ko-KR-HyunsuMultilingualNeural"
OUTPUT_FILE = "test_hyunsu.mp3"

async def main():
    print(f"Testing voice: {VOICE}")
    try:
        communicate = edge_tts.Communicate("안녕하세요, 이것은 마이크로소프트 엣지 TTS 테스트 음성입니다.", VOICE)
        await communicate.save(OUTPUT_FILE)
        print(f"✅ Success: File saved to {OUTPUT_FILE}")
        print(f"File size: {os.path.getsize(OUTPUT_FILE)} bytes")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Windows specific event loop policy fix if needed, but usually default works for simple script
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Main Error: {e}")
