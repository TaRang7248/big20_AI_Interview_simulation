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
import torch
import whisper
import speech_recognition as sr_lib
from openai import OpenAI
from parselmouth.praat import call
from ..config import logger, OPENAI_API_KEY, BASE_DIR

# ---------------------------------------------------------
# 1. 오디오 전처리 (노이즈 제거 및 정규화)
# ---------------------------------------------------------
def preprocess_audio(input_path):
    """
    오디오 파일의 전처리를 수행합니다.
    - 오디오 품질(RMS)이 이미 충분히 높다면 전처리를 최소화합니다.
    - 정규화를 통해 일관된 음량을 유지합니다.
    """
    try:
        # 오디오 로드 (샘플링 레이트 보존)
        try:
            y, sr = librosa.load(input_path, sr=None)
        except Exception as load_err:
            logger.warning(f"Librosa 로드 실패: {load_err}. soundfile 직접 읽기 시도 중...")
            try:
                data, samplerate = sf.read(input_path)
                y = data.T if data.ndim > 1 else data
                sr = samplerate
            except Exception as sf_err:
                logger.error(f"Soundfile 읽기도 실패: {sf_err}")
                raise load_err

        # RMS 계산하여 품질 확인
        rms = np.sqrt(np.mean(y**2))
        logger.info(f"원본 오디오 RMS: {rms:.5f}")

        # 정규화 및 최소 전처리 로직
        if rms > 0.05:
            logger.info("오디오 품질이 양호하므로 전처리를 최소화합니다.")
            y_norm = librosa.util.normalize(y) * 0.9
        else:
            # 품질이 낮을 경우 적절한 수준으로 증폭 및 정규화
            y_norm = librosa.util.normalize(y) * 0.707

        # 처리된 파일 저장 (WAV 형식)
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_processed.wav"
        
        sf.write(output_path, y_norm, sr)
        
        logger.info(f"오디오 전처리 완료: {output_path}")
        return output_path, y_norm, sr
    except Exception as e:
        logger.error(f"전처리 치명적 오류: {e}")
        return input_path, None, None

# ---------------------------------------------------------
# 2. 오디오 분석 (Librosa & Parselmouth)
# ---------------------------------------------------------
def analyze_audio_features(audio_path, y, sr):
    """
    오디오 분석 항목:
    - 무음 지속 시간
    - RMS 에너지 (신뢰도/볼륨 안정성)
    - 피치/F0 (Jitter, Shimmer 사용)
    - 발화 속도 (추정 음절 / 시간)
    """
    analysis_result = {
        "silence_duration": 0.0,
        "rms_mean": 0.0,
        "rms_std": 0.0,
        "pitch_jitter": 0.0,
        "pitch_shimmer": 0.0,
        "speech_rate": 0.0,
        "confidence_score": 0.0, 
        "is_nervous": False
    }

    try:
        if y is None:
            try:
                y, sr = librosa.load(audio_path, sr=None)
            except Exception as load_err:
                logger.warning(f"오디오 분석 건너뜀 (오디오를 로드할 수 없음): {load_err}")
                return analysis_result 
        
        duration = librosa.get_duration(y=y, sr=sr)
        
        # 무음 측정
        non_silent_intervals = librosa.effects.split(y, top_db=30)
        non_silent_duration = sum(end - start for start, end in non_silent_intervals) / sr
        silence_duration = duration - non_silent_duration
        analysis_result["silence_duration"] = round(silence_duration, 2)

        # RMS 에너지
        rms_vals = librosa.feature.rms(y=y)[0]
        analysis_result["rms_mean"] = float(np.mean(rms_vals))
        analysis_result["rms_std"] = float(np.std(rms_vals))

        # Jitter & Shimmer (Parselmouth)
        sound = parselmouth.Sound(audio_path)
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        analysis_result["pitch_jitter"] = round(jitter * 100, 4) if jitter == jitter else 0.0
        
        shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        analysis_result["pitch_shimmer"] = round(shimmer * 100, 4) if shimmer == shimmer else 0.0

        # 긴장도 판단
        nervous_score = 0
        if analysis_result["pitch_jitter"] > 1.5: nervous_score += 1
        if analysis_result["pitch_shimmer"] > 4.0: nervous_score += 1
        if duration > 0 and analysis_result["silence_duration"] / duration > 0.4: nervous_score += 1
        
        analysis_result["is_nervous"] = nervous_score >= 1
        confidence = 80 - (analysis_result["silence_duration"] * 2) - (analysis_result["pitch_jitter"] * 5)
        analysis_result["confidence_score"] = round(max(0, min(100, confidence)), 1)
        
    except Exception as e:
        logger.error(f"오디오 분석 오류: {e}")
    
    return analysis_result

# ---------------------------------------------------------
# 3. STT 함수 (Google Web Speech & Whisper)
# ---------------------------------------------------------
def transcribe_with_google_web_speech(audio_path):
    """
    Google Web Speech API를 사용하여 음성 전사를 수행합니다.
    (SpeechRecognition 라이브러리 사용)
    """
    try:
        recognizer = sr_lib.Recognizer()
        with sr_lib.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
        
        logger.info(f"Google Web Speech 전사 시작: {audio_path}")
        text = recognizer.recognize_google(audio_data, language="ko-KR")
        return text.strip()
    except sr_lib.UnknownValueError:
        logger.info("Google Web Speech: 음성을 인식할 수 없음")
        return None
    except sr_lib.RequestError as e:
        logger.error(f"Google Web Speech: 서비스 요청 오류; {e}")
        return None
    except Exception as e:
        logger.error(f"Google Web Speech 오류: {e}")
        return None

# OpenAI Whisper 모델 캐시
_WHISPER_MODEL_CACHE = None

def get_whisper_model():
    global _WHISPER_MODEL_CACHE
    if _WHISPER_MODEL_CACHE is None:
        model_name = "large-v3-turbo"
        logger.info(f"Whisper 로컬 모델({model_name}) 로딩 중...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _WHISPER_MODEL_CACHE = whisper.load_model(model_name, device=device)
        logger.info(f"Whisper 로컬 모델({model_name}) 로드 완료.")
    return _WHISPER_MODEL_CACHE

def transcribe_with_whisper(audio_path):
    """
    로컬 OpenAI Whisper 모델을 사용하여 음성 전사를 수행합니다.
    """
    try:
        model = get_whisper_model()
        logger.info(f"Whisper 로컬 모델 전사 시작: {audio_path}")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        result = model.transcribe(
            audio_path, 
            language="ko", 
            temperature=0.0,
            initial_prompt="이것은 한국어 면접 답변입니다. 간투사(어, 음)를 포함하여 있는 그대로 전사하세요.",
            fp16=(device == "cuda")
        )
        text = result["text"].strip()
        
        # 환각 필터
        hallucinations = ["시청해주셔서", "MBC 뉴스", "한글 자막", "Subtitles", "감사합니다"]
        if len(text) < 15 and any(h in text for h in hallucinations):
            return None
                
        return text
    except Exception as e:
        logger.error(f"Whisper 로컬 STT 오류: {e}")
        return None

def calculate_levenshtein_similarity(text1, text2):
    return Levenshtein.ratio(text1, text2)

def select_best_transcript(google_text, whisper_text):
    """
    Google Web Speech와 Whisper 결과 중 최적의 결과를 선택합니다.
    """
    if not google_text and not whisper_text:
        return "답변 없음"
    if not google_text:
        return whisper_text
    if not whisper_text:
        return google_text

    g = google_text.strip()
    w = whisper_text.strip()

    if g == "답변 없음" and w != "답변 없음": return w
    if w == "답변 없음" and g != "답변 없음": return g

    # 더 풍부한 정보(긴 문장) 또는 간투사 보존 여부로 판단
    if len(g) >= len(w) + 10: return g
    if len(w) >= len(g) + 10: return w

    # 기본적으로 Whisper가 로컬에서 더 세밀한 전사를 하는 경향이 있으므로 유사도가 높으면 Whisper 우선 고려 가능
    # 여기서는 단순 길이 및 존재 여부로 유지
    return w if len(w) >= len(g) else g

# ---------------------------------------------------------
# 4. 메인 파이프라인
# ---------------------------------------------------------
def transcribe_audio(original_audio_path):
    """
    메인 STT 파이프라인
    """
    if not os.path.exists(original_audio_path):
        return {"text": "파일 없음", "analysis": {}}

    try:
        y_orig, sr_orig = librosa.load(original_audio_path, sr=None)
        rms_total = np.sqrt(np.mean(y_orig**2))
        if rms_total < 0.001:
            return {"text": "답변 없음", "analysis": {"rms_mean": rms_total}}
    except Exception as e:
        logger.error(f"신호 확인 오류: {e}")

    # VAD 체크
    from .vad_service import check_vad_activity
    vad_ratio = check_vad_activity(original_audio_path)
    if vad_ratio < 0.01:
        return {"text": "답변 없음", "analysis": {"vad_ratio": vad_ratio}}

    # 1. 전처리
    processed_path, y, sr = preprocess_audio(original_audio_path)
    
    # 2. 특징 분석
    analysis = analyze_audio_features(processed_path, y, sr)
    
    # 3. STT 병렬 실행
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_google = executor.submit(transcribe_with_google_web_speech, processed_path)
        future_whisper = executor.submit(transcribe_with_whisper, processed_path)
        
        google_res = future_google.result()
        whisper_res = future_whisper.result()
        
    final_text = select_best_transcript(google_res, whisper_res)
    
    # 4. 속도 계산
    syllable_count = len(final_text.replace(" ", ""))
    duration = librosa.get_duration(y=y, sr=sr) if y is not None else 0
    speech_rate = round(syllable_count / duration, 2) if duration > 0 else 0
    analysis["speech_rate"] = speech_rate
    
    if speech_rate < 2.5: analysis["speed_feedback"] = "느림"
    elif speech_rate > 5.5: analysis["speed_feedback"] = "빠름"
    else: analysis["speed_feedback"] = "적절"

    return {
        "text": final_text,
        "analysis": analysis,
        "debug_info": {
            "google_web_speech": google_res,
            "whisper": whisper_res
        }
    }
