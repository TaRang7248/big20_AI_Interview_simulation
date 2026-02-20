import os
import time
import json
import logging
import numpy as np
import librosa
import soundfile as sf
import noisereduce as nr
import parselmouth
import Levenshtein
from openai import OpenAI
import google.generativeai as genai
from parselmouth.praat import call
from ..config import logger, GOOGLE_API_KEY, OPENAI_API_KEY

# Configure GenAI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Configure OpenAI
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY is not set. Whisper STT will be skipped.")

# ---------------------------------------------------------
# 1. Audio Preprocessing (Noise Reduction & Normalization)
# ---------------------------------------------------------
def preprocess_audio(input_path):
    """
    Applies noise reduction and normalization to the audio file.
    Returns the path to the processed audio file.
    """
    try:
        # Load audio
        # NOTE: librosa.load might fail if ffmpeg is not installed, especially for webm
        y, sr = librosa.load(input_path, sr=None)
        
        # 1. Noise Reduction
        # Prop_decrease=0.8 means 80% noise reduction (aggressive but preserves speech)
        y_reduced = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.8)
        
        # 2. Normalization
        # Normalize to -3dB
        max_val = np.max(np.abs(y_reduced))
        if max_val > 0:
            y_norm = y_reduced / max_val * 0.707  # 0.707 is approx -3dB
        else:
            y_norm = y_reduced
            
        # Save processed file
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_processed{ext}"
        sf.write(output_path, y_norm, sr)
        
        logger.info(f"Audio preprocessed: {output_path}")
        return output_path, y_norm, sr
    except Exception as e:
        return output_path, y_norm, sr
    except Exception as e:
        logger.error(f"Preprocessing Critical Error: {e}")
        logger.error(f"Failed file: {input_path}")
        # Check if file exists and size
        if os.path.exists(input_path):
             size = os.path.getsize(input_path)
             logger.error(f"File exists. Size: {size} bytes")
        else:
             logger.error("File does not exist.")
             
        # Return original path and None for y/sr so analysis can handle it gracefully
        return input_path, None, None

# ---------------------------------------------------------
# 2. Audio Analysis (Librosa & Parselmouth)
# ---------------------------------------------------------
def analyze_audio_features(audio_path, y, sr):
    """
    Analyzes audio for:
    - Silence Duration
    - RMS Energy (Confidence/Volume stability)
    - Pitch/F0 (Jitter, Shimmer using Parselmouth)
    - Speech Rate (Estimated syllables / time)
    """
    analysis_result = {
        "silence_duration": 0.0,
        "rms_mean": 0.0,
        "rms_std": 0.0,
        "pitch_jitter": 0.0,
        "pitch_shimmer": 0.0,
        "speech_rate": 0.0,
        "confidence_score": 0.0, # Computed metric
        "is_nervous": False
    }

    try:
        if y is None:
            # Reload if not passed (e.g. preprocessing failed)
            try:
                y, sr = librosa.load(audio_path, sr=None)
            except Exception as load_err:
                 logger.warning(f"Audio analysis skipped (could not load audio): {load_err}")
                 return analysis_result # Return empty analysis safely
        
        duration = librosa.get_duration(y=y, sr=sr)
        
        # --- 1. Silence Measurement ---
        # intervals where audio is below a threshold (e.g., top_db=20)
        # Note: Split returns non-silent intervals
        non_silent_intervals = librosa.effects.split(y, top_db=30)
        non_silent_duration = sum(end - start for start, end in non_silent_intervals) / sr
        silence_duration = duration - non_silent_duration
        analysis_result["silence_duration"] = round(silence_duration, 2)

        # --- 2. RMS Energy (Volume/Confidence) ---
        rms = librosa.feature.rms(y=y)[0]
        analysis_result["rms_mean"] = float(np.mean(rms))
        analysis_result["rms_std"] = float(np.std(rms)) # High std dev = unstable volume

        # --- 3. Jitter & Shimmer (Parselmouth) ---
        sound = parselmouth.Sound(audio_path)
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        
        # Jitter (local)
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        analysis_result["pitch_jitter"] = round(jitter * 100, 4) if jitter != jitter else 0.0 # Handle NaN
        
        # Shimmer (local)
        shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        analysis_result["pitch_shimmer"] = round(shimmer * 100, 4) if shimmer != shimmer else 0.0

        # --- 4. Logic for Confidence/Nervousness ---
        # Heuristic: High Jitter (>1.04%) or High Shimmer (>3.81%) often indicates pathology or extreme nervousness
        # For normal speech, lower is better.
        # Unstable volume (High RMS std/mean ratio) can also indicate nervousness.
        
        nervous_score = 0
        if analysis_result["pitch_jitter"] > 1.5: nervous_score += 1
        if analysis_result["pitch_shimmer"] > 4.0: nervous_score += 1
        if analysis_result["silence_duration"] / duration > 0.4: nervous_score += 1 # Too much silence
        
        analysis_result["is_nervous"] = nervous_score >= 1
        
        # Simplified confidence score (0-100)
        # Base 80, penalize for silence and jitter
        confidence = 80 - (analysis_result["silence_duration"] * 2) - (analysis_result["pitch_jitter"] * 5)
        analysis_result["confidence_score"] = round(max(0, min(100, confidence)), 1)
        
    except Exception as e:
        logger.error(f"Audio Analysis Error: {e}")
    
    return analysis_result

# ---------------------------------------------------------
# 3. STT Functions
# ---------------------------------------------------------
def transcribe_with_gemini(audio_path):
    try:
        if not GOOGLE_API_KEY: return None
        
        logger.info(f"Uploading audio to Gemini: {audio_path}")
        audio_file = genai.upload_file(path=audio_path)
        
        while audio_file.state.name == "PROCESSING":
             time.sleep(0.5)
             audio_file = genai.get_file(audio_file.name)
        
        if audio_file.state.name == "FAILED":
             return None
        
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.0}
        )
        
        prompt = """
        이 오디오 파일은 면접 지원자의 답변입니다. 
        들리는 내용을 '그대로' 전사해 주세요.
        특히 '음...', '어...', '그...' 같은 비언어적 표현이나 추임새도 삭제하지 말고 들리는 대로 모두 적어주세요.
        문법 교정이나 요약을 하지 마세요.
        오직 전사 텍스트만 출력하세요.
        """
        response = model.generate_content([prompt, audio_file])
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini STT Error: {e}")
        return None

def transcribe_with_whisper(audio_path):
    if not openai_client: return None
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko",
                temperature=0.0,
                prompt="이것은 한국어 면접 답변입니다. '음', '어' 같은 추임새를 그대로 포함해서 전사해주세요."
            )
        return transcript.text.strip()
    except Exception as e:
        logger.error(f"Whisper STT Error: {e}")
        return None

def select_best_transcript(gemini_text, whisper_text, audio_context_prompt=""):
    """
    Smart selection logic.
    """
    if not gemini_text and not whisper_text: return "답변 없음"
    if not gemini_text: return whisper_text
    if not whisper_text: return gemini_text
    
    # 1. Similarity Check
    similarity = Levenshtein.ratio(gemini_text, whisper_text)
    logger.info(f"STT Similarity: {similarity:.2f}")
    
    if similarity >= 0.95:
        # If very similar, pick the longer one (usually preserves more details)
        return gemini_text if len(gemini_text) >= len(whisper_text) else whisper_text
    
    # 2. LLM Judge (Contextual Naturalness)
    try:
        judge_model = genai.GenerativeModel("gemini-2.0-flash")
        judge_prompt = f"""
        다음은 동일한 오디오에 대한 두 가지 STT(음성 인식) 결과입니다.
        면접 답변 상황을 고려했을 때, 문맥상 더 자연스럽고 정확해 보이는 쪽을 선택해주세요.
        
        [결과 1]
        {gemini_text}
        
        [결과 2]
        {whisper_text}
        
        반환 형식: "1" 또는 "2"만 출력하세요. (설명 불필요)
        """
        response = judge_model.generate_content(judge_prompt)
        choice = response.text.strip()
        logger.info(f"LLM Judge Choice: {choice}")
        
        if "1" in choice: return gemini_text
        else: return whisper_text
        
    except Exception:
        # Fallback to longer one
        return gemini_text if len(gemini_text) > len(whisper_text) else whisper_text

# ---------------------------------------------------------
# 4. Main Function
# ---------------------------------------------------------
def transcribe_audio(original_audio_path):
    """
    Main pipeline:
    1. Preprocess (De-noise, Normalize)
    2. Analyze (Parselmouth, Librosa)
    3. STT (Gemini + Whisper + Selection)
    4. Speech Rate Calculation
    5. Return comprehensive result dict
    """
    if not os.path.exists(original_audio_path):
        return {"text": "파일 없음", "analysis": {}}

    # 1. Preprocess
    processed_path, y, sr = preprocess_audio(original_audio_path)
    
    # 2. Analyze Features
    analysis = analyze_audio_features(processed_path, y, sr)
    
    # 3. STT
    gemini_res = transcribe_with_gemini(processed_path)
    whisper_res = transcribe_with_whisper(processed_path)
    final_text = select_best_transcript(gemini_res, whisper_res)
    
    # 4. Speech Rate Calculation
    # Syllables per second (Korean)
    # Estimate syllables by character count (rough but effective for Korean)
    # Exclude spaces for syllable count
    syllable_count = len(final_text.replace(" ", ""))
    
    try:
        if y is None or sr is None:
             # Try determining duration from file if y is not available
             duration = librosa.get_duration(path=processed_path)
        else:
             duration = librosa.get_duration(y=y, sr=sr)
    except Exception as e:
        logger.warning(f"Could not calculate duration: {e}")
        duration = 0

    speech_rate = 0
    if duration > 0:
        speech_rate = round(syllable_count / duration, 2)
    
    analysis["speech_rate"] = speech_rate
    
    # Add speech rate feedback
    if speech_rate < 2.5: analysis["speed_feedback"] = "느림"
    elif speech_rate > 5.5: analysis["speed_feedback"] = "빠름"
    else: analysis["speed_feedback"] = "적절"

    logger.info(f"Start STT Pipeline Complete. Text len: {len(final_text)}")
    
    return {
        "text": final_text,
        "analysis": analysis,
        "debug_info": {
            "gemini": gemini_res,
            "whisper": whisper_res,
            "similarity_used": True
        }
    }
