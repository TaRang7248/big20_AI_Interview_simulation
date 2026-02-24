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
from openai import OpenAI
import google.generativeai as genai
from parselmouth.praat import call
from ..config import logger, GOOGLE_API_KEY, OPENAI_API_KEY, BASE_DIR
# from .vad_service import calculate_average_rms, check_vad_activity
# vad_service를 직접 사용하지 않고 내부 로직으로 통합하거나 수정된 방식을 사용합니다.


# Gemini 모델 인스턴스 재사용을 위한 전역 변수
_STT_MODEL_CACHE = {}

def get_gemini_model(model_name="gemini-2.0-flash"):
    """
    Gemini 모델 인스턴스를 반환합니다. 이미 생성된 인스턴스가 있으면 재사용합니다.
    """
    if model_name not in _STT_MODEL_CACHE:
        logger.info(f"STT용 새로운 {model_name} 모델 인스턴스를 생성합니다.")
        _STT_MODEL_CACHE[model_name] = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": 0.0}
        )
    return _STT_MODEL_CACHE[model_name]

# GenAI 설정
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# OpenAI API 설정 (필요시 사용, 현재는 로컬 Whisper 우선)
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 로컬 Whisper 모델 캐시
_WHISPER_MODEL_CACHE = None

def get_whisper_model():
    """
    OpenAI Whisper (V3 Turbo) 모델을 로드하거나 캐시된 인스턴스를 반환합니다.
    """
    global _WHISPER_MODEL_CACHE
    if _WHISPER_MODEL_CACHE is None:
        model_name = "large-v3-turbo"
        logger.info(f"Whisper 로컬 모델({model_name}) 로딩 중... (최초 실행 시 시간이 걸릴 수 있습니다)")
        
        # GPU 사용 가능 여부 확인
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Whisper 실행 장치: {device}")
        
        # 모델 로드
        _WHISPER_MODEL_CACHE = whisper.load_model(model_name, device=device)
        logger.info(f"Whisper 로컬 모델({model_name}) 로드 완료.")
    
    return _WHISPER_MODEL_CACHE

# ---------------------------------------------------------
# 1. 오디오 전처리 (노이즈 제거 및 정규화)
# ---------------------------------------------------------
def preprocess_audio(input_path):
    """
    오디오 파일의 전처리를 수행합니다.
    - 노이즈 제거(noisereduce)는 원본 손상을 방지하기 위해 삭제되었습니다.
    - 오디오 품질(RMS)이 이미 충분히 높다면 전처리를 최소화합니다.
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
        # RMS가 충분히 크면(0.05 이상) 원본의 품질이 좋다고 판단하여 정규화만 수행
        if rms > 0.05:
            logger.info("오디오 품질이 양호하므로 전처리를 최소화합니다.")
            y_norm = librosa.util.normalize(y) * 0.9
        else:
            # 품질이 낮을 경우 적절한 수준으로 증폭 및 정규화
            y_norm = librosa.util.normalize(y) * 0.707

        # 처리된 파일 저장 (WAV 형식 권장)
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
        "confidence_score": 0.0, # 계산된 지표
        "is_nervous": False
    }

    try:
        if y is None:
            # 전달되지 않은 경우 다시 로드 (예: 전처리 실패 시)
            try:
                y, sr = librosa.load(audio_path, sr=None)
            except Exception as load_err:
                 logger.warning(f"오디오 분석 건너뜀 (오디오를 로드할 수 없음): {load_err}")
                 return analysis_result # 빈 분석 결과 안전하게 반환
        
        duration = librosa.get_duration(y=y, sr=sr)
        
        # --- 1. 무음 측정 ---
        # 임계값(예: top_db=30) 미만인 구간
        # 참고: split은 무음이 아닌 구간을 반환함
        non_silent_intervals = librosa.effects.split(y, top_db=30)
        non_silent_duration = sum(end - start for start, end in non_silent_intervals) / sr
        silence_duration = duration - non_silent_duration
        analysis_result["silence_duration"] = round(silence_duration, 2)

        # --- 2. RMS 에너지 (볼륨/신뢰도) ---
        rms = librosa.feature.rms(y=y)[0]
        analysis_result["rms_mean"] = float(np.mean(rms))
        analysis_result["rms_std"] = float(np.std(rms)) # 높은 표준 편차 = 불안정한 볼륨

        # --- 3. Jitter & Shimmer (Parselmouth) ---
        sound = parselmouth.Sound(audio_path)
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        
        # Jitter (local)
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        analysis_result["pitch_jitter"] = round(jitter * 100, 4) if jitter != jitter else 0.0 # NaN 처리
        
        # Shimmer (local)
        shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        analysis_result["pitch_shimmer"] = round(shimmer * 100, 4) if shimmer != shimmer else 0.0

        # --- 4. 신뢰도/긴장도 로직 ---
        # 휴리스틱: 높은 Jitter (>1.5%) 또는 높은 Shimmer (>4.0%)는 극심한 긴장을 나타낼 수 있음.
        # 일반적인 대화에서는 낮을수록 좋음.
        # 불안정한 볼륨(높은 RMS 표준편차/평균 비율)도 긴장을 나타낼 수 있음.
        
        nervous_score = 0
        if analysis_result["pitch_jitter"] > 1.5: nervous_score += 1
        if analysis_result["pitch_shimmer"] > 4.0: nervous_score += 1
        if duration > 0 and analysis_result["silence_duration"] / duration > 0.4: nervous_score += 1 # 무음이 너무 많음
        
        analysis_result["is_nervous"] = nervous_score >= 1
        
        # 단순화된 신뢰도 점수 (0-100)
        # 기본 80점에서 무음과 Jitter에 따라 감점
        confidence = 80 - (analysis_result["silence_duration"] * 2) - (analysis_result["pitch_jitter"] * 5)
        analysis_result["confidence_score"] = round(max(0, min(100, confidence)), 1)
        
    except Exception as e:
        logger.error(f"오디오 분석 오류: {e}")
    
    return analysis_result

# ---------------------------------------------------------
# 3. STT 함수
# ---------------------------------------------------------
def transcribe_with_gemini(audio_path):
    try:
        if not GOOGLE_API_KEY: return None
        
        logger.info(f"Gemini에 오디오 업로드 중: {audio_path}")
        audio_file = genai.upload_file(path=audio_path)
        
        while audio_file.state.name == "PROCESSING":
             time.sleep(0.5)
             audio_file = genai.get_file(audio_file.name)
        
        if audio_file.state.name == "FAILED":
             return None
        
        # 모델 인스턴스 재사용
        model = get_gemini_model("gemini-2.0-flash")
        
        prompt = """
        [역할: 최고 성능의 한국어 음성 전사 전문가]
        이 오디오 파일은 면접 지원자의 답변입니다. 
        당신의 임무는 들리는 '모든 소리'를 단 한 글자도 빠짐없이, 그리고 단 한 글자도 변형하지 않고 '완벽하게 똑같이' 전사하는 것입니다.

        [절대 규칙]
        - 문맥에 맞게 문장을 완성하지 마세요.
        - 지원자가 말을 더듬으면 '어... 그게...'와 같이 들리는 그대로 적으세요.
        - 비문(틀린 문장)이라도 절대로 교정하지 마세요.
        - 사람의 목소리가 전혀 들리지 않거나 침묵, 백색소음만 있다면 "답변 없음" 이라고만 출력하세요.
        - 오디오에 없는 내용을 절대로 추측하거나 생성하지 마세요.
        """
        response = model.generate_content(
            [prompt, audio_file],
            request_options={"timeout": 30}
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini STT 오류: {e}")
        return None

def transcribe_with_whisper(audio_path):
    """
    로컬 OpenAI Whisper (V3 Turbo) 모델을 사용하여 음성 전사를 수행합니다.
    """
    try:
        model = get_whisper_model()
        
        logger.info(f"Whisper 로컬 모델 전사 시작: {audio_path}")
        # fp16=False는 CPU 환경에서의 경고 방지용
        device = "cuda" if torch.cuda.is_available() else "cpu"
        result = model.transcribe(
            audio_path, 
            language="ko", 
            temperature=0.0,
            initial_prompt="이것은 한국어 면접 답변입니다. 간투사(어, 음)를 포함하여 들리는 모든 소리를 단 한 글자도 변형하지 말고 있는 그대로 똑같이 전사하세요. 목소리가 없다면 절대로 내용을 지어내지 마세요.",
            fp16=(device == "cuda")
        )
        
        text = result["text"].strip()
        
        # Whisper 환각(Hallucination) 필터 강화
        hallucinations = ["시청해주셔서", "MBC 뉴스", "한글 자막", "Subtitles", "감사합니다", "9시 뉴스", "오늘 영상 여기까지입니다", "구독과 좋아요"]
        if len(text) < 15 and any(h in text for h in hallucinations):
            logger.info(f"Whisper 환각 감지 및 필터링: {text}")
            return None # 환각 가능성 높음
                
        return text
    except Exception as e:
        logger.error(f"Whisper 로컬 STT 오류: {e}")
        return None

def calculate_levenshtein_similarity(text1, text2):
    """
    두 텍스트 간의 Levenshtein 유사도를 계산합니다. (0.0 ~ 1.0)
    """
    return Levenshtein.ratio(text1, text2)

def select_best_transcript(gemini_text, whisper_text, audio_context_prompt=""):
    """
    스마트 선택 로직: Gemini와 Whisper 결과 중 최적의 전사 결과를 선택합니다.
    자연스러움보다 '원본과의 동일성'과 '상세함'을 우선시합니다.
    """
    if not gemini_text and not whisper_text: return "답변 없음"
    if not gemini_text: return whisper_text
    if not whisper_text: return gemini_text
    
    # 1. 유사도 체크
    similarity = calculate_levenshtein_similarity(gemini_text, whisper_text)
    logger.info(f"STT 유사도: {similarity:.2f}")
    
    if similarity >= 0.95:
        # 매우 유사한 경우, 더 긴 결과(보통 더 많은 세부 사항 보존)를 선택
        return gemini_text if len(gemini_text) >= len(whisper_text) else whisper_text
    
    # [변경 사항] 유사도가 0.95 미만인 경우, LLM 판단을 거치지 않고 바로 Whisper 결과를 사용합니다.
    # Whisper가 일반적으로 간투사 인식 및 안정성 면에서 뛰어난 성능을 보이기 때문입니다.
    logger.info("STT 유사도가 낮아 Whisper 결과를 우선 선택합니다.")
    return whisper_text

# ---------------------------------------------------------
# 4. 메인 함수
# ---------------------------------------------------------
def transcribe_audio(original_audio_path):
    """
    메인 파이프라인:
    1. 전처리 (노이즈 제거, 정규화)
    2. 특징 분석 (Parselmouth, Librosa)
    3. STT (Gemini + Whisper + 선택)
    4. 발화 속도 계산
    5. 종합 결과 딕셔너리 반환
    """
    if not os.path.exists(original_audio_path):
        return {"text": "파일 없음", "analysis": {}}

    # 0. RMS 체크 (사전 필터링) - 임계값 하향 조정 및 전체 구간 신호 탐색
    try:
        y_orig, sr_orig = librosa.load(original_audio_path, sr=None)
        # 전체 구간에서 RMS 계산
        rms_total = np.sqrt(np.mean(y_orig**2))
        
        # RMS 임계값을 0.001로 하향 조정 (작은 소리도 허용)
        if rms_total < 0.001:
            logger.info(f"전체 오디오 신호가 너무 약함 ({rms_total:.5f}). 무음 처리합니다.")
            return {
                "text": "답변 없음",
                "analysis": {"rms_mean": rms_total},
                "debug_info": {"skipped_due_to_low_signal": True}
            }
    except Exception as e:
        logger.error(f"초기 신호 확인 중 오류: {e}")

    # VAD 체크 (전체적인 발화 존재 여부 확인)
    from .vad_service import check_vad_activity
    vad_ratio = check_vad_activity(original_audio_path)
    if vad_ratio < 0.01: # 발화 비율 임계값도 더 낮춤
        logger.info(f"VAD 발화 비율이 매우 낮음 ({vad_ratio:.2f}). 무음 처리합니다.")
        return {
            "text": "답변 없음",
            "analysis": {"vad_ratio": vad_ratio},
            "debug_info": {"skipped_due_to_vad": True}
        }

    # 1. 전처리
    processed_path, y, sr = preprocess_audio(original_audio_path)
    
    # 2. 특징 분석
    analysis = analyze_audio_features(processed_path, y, sr)
    
    # VAD 방어 로직
    duration = librosa.get_duration(y=y, sr=sr) if y is not None else 0
    # 전체 오디오 길이 중 침묵 비중이 95% 이상이면 STT 생략
    if duration > 0 and (analysis.get("silence_duration", 0) / duration > 0.95):
        logger.info("오디오의 대부분이 침묵입니다. STT를 건너뛰고 '답변 없음' 처리합니다.")
        return {
            "text": "답변 없음",
            "analysis": analysis,
            "debug_info": {"skipped_due_to_silence": True}
        }

    # 3. STT (Gemini + Whisper 병렬 실행)
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        logger.info("Gemini 및 Whisper STT 병렬 실행 시작...")
        future_gemini = executor.submit(transcribe_with_gemini, processed_path)
        future_whisper = executor.submit(transcribe_with_whisper, processed_path)
        
        gemini_res = future_gemini.result()
        whisper_res = future_whisper.result()
        
    final_text = select_best_transcript(gemini_res, whisper_res)
    
    # 4. 발화 속도 계산
    # 초당 음절 수 (한국어)
    # 공백을 제외한 글자 수로 음절 수 추정
    syllable_count = len(final_text.replace(" ", ""))
    
    try:
        if y is None or sr is None:
             # y가 없는 경우 파일에서 직접 길이 측정 시도
             duration = librosa.get_duration(path=processed_path)
        else:
             duration = librosa.get_duration(y=y, sr=sr)
    except Exception as e:
        logger.warning(f"길이 계산 불가: {e}")
        duration = 0

    speech_rate = 0
    if duration > 0:
        speech_rate = round(syllable_count / duration, 2)
    
    analysis["speech_rate"] = speech_rate
    
    # 발화 속도 피드백 추가
    if speech_rate < 2.5: analysis["speed_feedback"] = "느림"
    elif speech_rate > 5.5: analysis["speed_feedback"] = "빠름"
    else: analysis["speed_feedback"] = "적절"

    logger.info(f"STT 파이프라인 완료. 텍스트 길이: {len(final_text)}")
    
    return {
        "text": final_text,
        "analysis": analysis,
        "debug_info": {
            "gemini": gemini_res,
            "whisper": whisper_res,
            "similarity_used": True
        }
    }
