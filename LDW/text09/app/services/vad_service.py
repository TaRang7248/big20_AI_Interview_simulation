import logging
import numpy as np
import librosa
import webrtcvad
import soundfile as sf
import os

logger = logging.getLogger(__name__)

def calculate_average_rms(audio_path):
    """
    Calculates the average RMS (Root Mean Square) energy of an audio file.
    Returns:
        float: Average RMS value.
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)
        rms = librosa.feature.rms(y=y)[0]
        avg_rms = float(np.mean(rms))
        logger.info(f"Audio RMS: {avg_rms}")
        return avg_rms
    except Exception as e:
        logger.error(f"Error calculating RMS for {audio_path}: {e}")
        return 0.0

def check_vad_activity(audio_path, aggressiveness=3):
    """
    Checks for voice activity using WebRTC VAD.
    Returns:
        float: Ratio of speech frames to total frames (0.0 to 1.0).
    """
    try:
        # WebRTC VAD requires 16-bit PCM, mono, and specific sample rates (8k, 16k, 32k, 48k)
        # We will resample to 16000Hz for compatibility
        target_sr = 16000
        
        # Load audio and resample
        y, sr = librosa.load(audio_path, sr=target_sr, mono=True)
        
        # Convert to 16-bit PCM
        # librosa loads as float32 in [-1, 1], convert to int16
        pcm_data = (y * 32767).astype(np.int16)
        
        vad = webrtcvad.Vad(aggressiveness)
        
        # WebRTC VAD supports frame durations of 10, 20, or 30ms
        frame_duration_ms = 30
        frame_len = int(target_sr * frame_duration_ms / 1000)
        
        num_speech_frames = 0
        total_frames = 0
        
        # Iterate over frames
        for i in range(0, len(pcm_data) - frame_len, frame_len):
            frame = pcm_data[i:i+frame_len]
            # Convert numpy array to bytes
            frame_bytes = frame.tobytes()
            
            if vad.is_speech(frame_bytes, target_sr):
                num_speech_frames += 1
            total_frames += 1
            
        if total_frames == 0:
            return 0.0
            
        speech_ratio = num_speech_frames / total_frames
        logger.info(f"VAD Speech Ratio: {speech_ratio:.2f} (Aggressiveness: {aggressiveness})")
        return speech_ratio
        
    except Exception as e:
        logger.error(f"Error executing WebRTC VAD for {audio_path}: {e}")
        # In case of error (e.g. too short audio), default to passing if RMS check passed
        return 0.0
