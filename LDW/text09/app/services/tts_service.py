import os
import uuid
import edge_tts
from ..config import TTS_FOLDER, logger

async def generate_tts_audio(text, voice="fr-FR-RemyMultilingualNeural"):
    """
    Microsoft Edge TTS를 사용하여 음성을 합성하고 파일로 저장합니다.
    이후 Wav2Lip 비디오 생성을 시도하며, 실패 시 오디오 URL만 반환합니다.

    Args:
        text: 합성할 텍스트
        voice: TTS 음성 모델명

    Returns:
        성공 시 미디어 정보 딕셔너리 {"url": str, "type": "video"|"audio"}, 실패 시 None
    """
    logger.info(f"[TTS] 요청: '{text[:20]}...' / 음성: {voice}")
    try:
        # TTS 오디오 파일 생성
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(TTS_FOLDER, filename)
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)
        
        # 파일 크기 확인
        filesize = os.path.getsize(filepath)
        logger.info(f"[TTS] 생성 완료: {filepath} (크기: {filesize} bytes)")

        # TTS 완료 후 Wav2Lip 립싱크 비디오 생성 시도
        from .video_gen_service import generate_wav2lip_video
        video_url = await generate_wav2lip_video(filepath)
        
        if video_url:
            # 비디오 생성 성공: 비디오 URL과 타입 반환
            logger.info(f"[TTS] 립싱크 비디오 생성 성공: {video_url}")
            return {"url": video_url, "type": "video"}
        else:
            # 비디오 생성 실패: 오디오만 반환 (프론트엔드에서 오디오 전용 재생)
            logger.warning("[TTS] 비디오 생성 실패. 오디오만 반환합니다.")
            return {"url": f"/uploads/tts_audio/{filename}", "type": "audio"}
    except Exception as e:
        logger.error(f"[TTS] 음성 합성 중 오류 발생: {e}")
        return None
