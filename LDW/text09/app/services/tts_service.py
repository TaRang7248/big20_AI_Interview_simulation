import os
import uuid
import edge_tts
from ..config import TTS_FOLDER, logger

async def generate_tts_audio(text, voice="fr-FR-RemyMultilingualNeural"):
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

        # TTS 완료 후 Wav2Lip 비디오 생성을 비동기로 실행
        # (Wav2Lip은 이제 async 함수이므로 직접 await 합니다.)
        from .video_gen_service import generate_wav2lip_video
        video_url = await generate_wav2lip_video(filepath)
        
        if video_url:
            return video_url
        else:
            logger.warning("비디오 생성 실패. 오디오만 반환")
            return f"/uploads/tts_audio/{filename}"
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}")
        return None
