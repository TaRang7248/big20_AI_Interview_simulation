import logging
import numpy as np
import librosa
import webrtcvad
import soundfile as sf
import os

logger = logging.getLogger(__name__)

def calculate_average_rms(audio_path):
    """
    오디오 파일의 평균 RMS(Root Mean Square) 에너지를 계산합니다.
    반환값:
        float: 평균 RMS 값.
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)
        rms = librosa.feature.rms(y=y)[0]
        avg_rms = float(np.mean(rms))
        logger.info(f"오디오 RMS: {avg_rms}")
        return avg_rms
    except Exception as e:
        logger.error(f"{audio_path}의 RMS 계산 중 오류 발생: {e}")
        return 0.0

def check_vad_activity(audio_path, aggressiveness=3):
    """
    WebRTC VAD를 사용하여 음성 활동을 확인합니다.
    반환값:
        float: 전체 프레임 대비 음성 프레임의 비율 (0.0 ~ 1.0).
    """
    try:
        # WebRTC VAD는 16-bit PCM, 모노, 특정 샘플 레이트(8k, 16k, 32k, 48k)가 필요합니다.
        # 호환성을 위해 16000Hz로 리샘플링합니다.
        target_sr = 16000
        
        # 오디오 로드 및 리샘플링
        y, sr = librosa.load(audio_path, sr=target_sr, mono=True)
        
        # 16-bit PCM으로 변환
        # librosa는 [-1, 1] 사이의 float32로 로드하므로, int16으로 변환합니다.
        pcm_data = (y * 32767).astype(np.int16)
        
        vad = webrtcvad.Vad(aggressiveness)
        
        # WebRTC VAD는 10, 20, 30ms의 프레임 길이를 지원합니다.
        frame_duration_ms = 30
        frame_len = int(target_sr * frame_duration_ms / 1000)
        
        num_speech_frames = 0
        total_frames = 0
        
        # 프레임 단위로 반복
        for i in range(0, len(pcm_data) - frame_len, frame_len):
            frame = pcm_data[i:i+frame_len]
            # numpy 배열을 bytes로 변환
            frame_bytes = frame.tobytes()
            
            if vad.is_speech(frame_bytes, target_sr):
                num_speech_frames += 1
            total_frames += 1
            
        if total_frames == 0:
            return 0.0
            
        speech_ratio = num_speech_frames / total_frames
        logger.info(f"VAD 음성 비율: {speech_ratio:.2f} (민감도: {aggressiveness})")
        return speech_ratio
        
    except Exception as e:
        logger.error(f"{audio_path}에 대한 WebRTC VAD 실행 중 오류 발생: {e}")
        # 오류 발생 시(예: 오디오가 너무 짧음), RMS 체크를 통과했다면 기본적으로 통과하도록 0.0 반환 로직 유지
        return 0.0
