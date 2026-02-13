import os
import uuid
import edge_tts
from ..config import TTS_FOLDER, logger

async def generate_tts_audio(text, voice="ko-KR-HyunsuMultilingualNeural"):
    """
    Generates TTS audio using Microsoft Edge TTS and saves it to a file.
    Returns the relative path to the audio file.
    """
    logger.info(f"TTS Request: '{text[:20]}...' using voice: {voice}")
    try:
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(TTS_FOLDER, filename)
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)
        
        # Check file size
        filesize = os.path.getsize(filepath)
        logger.info(f"TTS Generated: {filepath} (Size: {filesize} bytes)")

        return f"/uploads/tts_audio/{filename}"
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}")
        return None
