import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import edge_tts
import os

async def list_voices():
    """Available voices printing"""
    voices = await edge_tts.list_voices()
    print(f"Total voices: {len(voices)}")
    
    korean_voices = [v for v in voices if "ko-KR" in v["ShortName"]]
    print("\n[Korean Voices Available]")
    for v in korean_voices:
        print(f"- {v['ShortName']} ({v['Gender']})")
        
    return korean_voices

async def generate_audio(text, voice, output_file):
    """Generate audio file"""
    print(f"\nGenerating audio with voice: {voice}...")
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"✅ Success! File saved: {output_file} ({size} bytes)")
            return True
        else:
            print(f"❌ Failed! File not found: {output_file}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    print("--- Edge TTS Verification Info ---")
    
    # 1. Check Voices
    korean_voices = await list_voices()
    
    target_voice = "ko-KR-HyunsuMultilingualNeural"
    is_target_available = any(v['ShortName'] == target_voice for v in korean_voices)
    
    if is_target_available:
        print(f"\n✅ Target voice '{target_voice}' is AVAILABLE.")
    else:
        print(f"\n⚠️ Target voice '{target_voice}' is NOT found in the list. It might still work if supported remotely, but check spelling.")
        # Some voices might be hidden or require specific locales, but usually list_voices covers them.

    # 2. Test Generation Comparison
    test_text = "안녕하세요. 이것은 AI 면접 시뮬레이션 음성 테스트입니다."
    
    file_target = "test_hyunsu.mp3"
    file_compare = "test_sunhi.mp3"
    
    # Try generating with target voice
    await generate_audio(test_text, target_voice, file_target)
    
    # Try generating with another voice (e.g. SunHi) for comparison
    compare_voice = "ko-KR-SunHiNeural"
    if not any(v['ShortName'] == compare_voice for v in korean_voices) and len(korean_voices) > 0:
        compare_voice = korean_voices[0]['ShortName'] # Fallback to first available if SunHi not found
        if compare_voice == target_voice and len(korean_voices) > 1:
            compare_voice = korean_voices[1]['ShortName']
            
    await generate_audio(test_text, compare_voice, file_compare)
    
    # 3. Compare Files
    if os.path.exists(file_target) and os.path.exists(file_compare):
        size1 = os.path.getsize(file_target)
        size2 = os.path.getsize(file_compare)
        
        print(f"\n[Comparison]")
        print(f"Target ({target_voice}): {size1} bytes")
        print(f"Other ({compare_voice}): {size2} bytes")
        
        if size1 != size2:
            print("✅ Files are different sizes. This suggests different voices were effectively used.")
        else:
            print("⚠️ Files are identical sizes. This is suspicious if voices are different, but could happen with short text.")

if __name__ == "__main__":
    asyncio.run(main())
