import os
import uuid
from ..config import TTS_FOLDER, logger

async def generate_tts_audio(text, voice="fr-FR-RemyMultilingualNeural"):
    """
    Microsoft Edge TTS를 사용하여 음성을 합성하고 파일로 저장합니다.
    이후 Wav2Lip 비디오 생성을 시도하며, 실패 시 오디오 URL만 반환합니다.

    반환값:
        성공 시 {"url": str, "type": "video"|"audio"} 딕셔너리
        실패 시 None
    """
    # 요청된 텍스트와 음성 정보를 로그에 기록합니다.
    logger.info(f"[TTS] 요청: '{text[:20]}...' / 음성: {voice}")

    try:
        # TTS 오디오를 저장할 고유한 파일명을 생성합니다.
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(TTS_FOLDER, filename)

        # gTTS 라이브러리를 사용하여 음성 합성을 수행합니다.
        # edge-tts의 403 오류를 회피하기 위해 기본 구글 TTS를 사용합니다.
        from gtts import gTTS
        tts = gTTS(text=text, lang='ko')
        # 비동기가 아니므로 동기 저장
        tts.save(filepath)

        # 생성된 파일의 크기를 확인하여 정상 생성 여부를 체크합니다.
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            logger.error(f"[TTS] 파일 생성 실패 또는 크기가 0입니다: {filepath}")
            return None
            
        filesize = os.path.getsize(filepath)
        logger.info(f"[TTS] 생성 완료: {filepath} (크기: {filesize} bytes)")

        # TTS 완료 후 Wav2Lip을 이용해 면접관 얼굴 영상(립싱크) 생성을 시도합니다.
        from .video_gen_service import generate_wav2lip_video
        video_url = await generate_wav2lip_video(filepath)

        if video_url:
            logger.info(f"[TTS] 립싱크 비디오 생성 성공: {video_url}")
            return {"url": video_url, "type": "video"}
        else:
            # 비디오 생성에 실패하더라도 음성 파일은 생성되었으므로 오디오만 반환하여 진행을 유지합니다.
            logger.warning("[TTS] 비디오 생성 실패. 오디오만 반환합니다.")
            return {"url": f"/uploads/tts_audio/{filename}", "type": "audio"}

    except Exception as e:
        # TTS 과정 중 발생하는 모든 예외를 로그에 남기고 에러를 방지합니다.
        logger.error(f"[TTS] 음성 합성 중 시스템 오류 발생: {e}")
        return None