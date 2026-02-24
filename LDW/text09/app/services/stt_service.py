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
from .vad_service import calculate_average_rms, check_vad_activity

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

# OpenAI 설정
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. Whisper STT를 건너뜁니다.")

# ---------------------------------------------------------
# 1. 오디오 전처리 (노이즈 제거 및 정규화)
# ---------------------------------------------------------
def preprocess_audio(input_path):
    """
    오디오 파일에 노이즈 제거 및 정규화를 적용합니다.
    처리된 오디오 파일의 경로를 반환합니다.
    """
    try:
        # 오디오 로드
        # 참고: ffmpeg이 설치되어 있지 않으면 librosa.load가 실패할 수 있음(특히 webm)
        # 샘플링 레이트 보존을 위해 sr=None 명시
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

        # 1. 노이즈 제거
        # prop_decrease=0.8은 80% 노이즈 제거를 의미 (공격적이지만 음성은 보존)
        try:
            y_reduced = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.8)
        except Exception as nr_err:
            logger.warning(f"노이즈 제거 실패: {nr_err}. 원본 오디오를 사용합니다.")
            y_reduced = y
        
        # 2. 정규화
        # -3dB로 정규화
        max_val = np.max(np.abs(y_reduced))
        if max_val > 0:
            y_norm = y_reduced / max_val * 0.707  # 0.707은 약 -3dB
        else:
            y_norm = y_reduced
            
        # 처리된 파일 저장
        # 변경: .webm과의 soundfile 포맷 오류를 피하기 위해 .wav 사용
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_processed.wav"
        
        # 명시적으로 포맷/서브타입 지정 (WAV는 보통 안전한 기본값)
        sf.write(output_path, y_norm, sr)
        
        logger.info(f"오디오 전처리 완료: {output_path}")
        return output_path, y_norm, sr
    except Exception as e:
        logger.error(f"전처리 치명적 오류: {e}")
        logger.error(f"실패한 파일: {input_path}")
        # 파일 존재 여부 및 크기 확인
        if os.path.exists(input_path):
             size = os.path.getsize(input_path)
             logger.error(f"파일 존재함. 크기: {size} 바이트")
        else:
             logger.error("파일이 존재하지 않습니다.")
             
        # 분석이 우아하게 처리할 수 있도록 원본 경로와 None 반환
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

        [강력한 규칙 - 절대 엄수]
        1. 들리는 내용을 있는 그대로 적으세요. 문법 교정, 문장 다듬기, 요약, 재해석을 '절대' 하지 마세요.
        2. "어...", "음...", "그..."와 같은 간투사도 소리가 들린다면 그대로 적어야 합니다.
        3. 만약 사람의 목소리가 전혀 들리지 않거나 침묵, 백색소음만 있다면, 절대로 내용을 지어내지 말고 오직 "답변 없음" 이라고만 핵심 단어를 출력하세요.
        4. 오디오에 없는 내용을 절대로 추측하거나 생성하지 마세요. (Hallucination 방지)
        5. 모든 소리를 완전히 똑같이 인식하여 텍스트로 변환하세요.
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
    if not openai_client: return None
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko",
                temperature=0.0,
                prompt="이것은 한국어 면접 답변입니다. 간투사(어, 음)를 포함하여 들리는 모든 소리를 단 한 글자도 변형하지 말고 있는 그대로 똑같이 전사하세요. 목소리가 없다면 절대로 내용을 지어내지 마세요.",
                timeout=30
            )
        text = transcript.text.strip()
        
        # Whisper 환각(Hallucination) 필터
        hallucinations = [
            "이것은 한국어 면접 답변입니다",
            "사람의 목소리가 없다면 지어내지 마세요",
            "들리는 내용대로 똑같이 적어주세요",
            "MBC 뉴스",
            "시청해주셔서 감사합니다",
            "구독과 좋아요",
            "9시 뉴스"
        ]
        
        for h in hallucinations:
            if h in text:
                logger.info(f"Whisper 환각 감지됨: {text}")
                return None # 무음으로 처리
                
        return text
    except Exception as e:
        logger.error(f"Whisper STT 오류: {e}")
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
    
    # 2. LLM 판단 (원본 보존성 중심)
    try:
        # 모델 인스턴스 재사용
        judge_model = get_gemini_model("gemini-2.0-flash")
        judge_prompt = f"""
        다음은 동일한 오디오에 대한 두 가지 STT 결과입니다.
        면접 상황에서 지원자가 말한 '원본 소리'를 가장 누락 없이, 그리고 변형 없이 그대로 옮긴 것처럼 보이는 결과를 선택하세요.
        문법적인 올바름보다 '들리는 소리의 충실함'이 더 중요합니다.
        
        [결과 1]
        {gemini_text}
        
        [결과 2]
        {whisper_text}
        
        반환 형식: "1" 또는 "2"만 출력하세요. (설명 불필요)
        """
        response = judge_model.generate_content(judge_prompt)
        choice = response.text.strip()
        logger.info(f"LLM 판단 결과: {choice}")
        
        if "1" in choice: return gemini_text
        else: return whisper_text
        
    except Exception:
        # 오류 발생 시 더 긴 결과 반환
        if not gemini_text: return whisper_text
        if not whisper_text: return gemini_text
        
        return gemini_text if len(gemini_text) > len(whisper_text) else whisper_text

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

    # 0. RMS 및 VAD 체크 (사전 필터링)
    rms_mean = calculate_average_rms(original_audio_path)
    if rms_mean < 0.002: # RMS 임계값
        logger.info(f"RMS가 너무 낮음 ({rms_mean:.5f}). 무음으로 처리합니다.")
        return {
            "text": "답변 없음",
            "analysis": {"rms_mean": rms_mean},
            "debug_info": {"skipped_due_to_rms": True}
        }
        
    vad_ratio = check_vad_activity(original_audio_path)
    if vad_ratio < 0.05: # 발화 비율 < 5%
        logger.info(f"VAD 발화 비율이 너무 낮음 ({vad_ratio:.2f}). 무음으로 처리합니다.")
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
