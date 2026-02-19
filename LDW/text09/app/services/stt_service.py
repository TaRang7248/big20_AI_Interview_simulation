import os
import time
import Levenshtein
from openai import OpenAI
import google.generativeai as genai
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

def calculate_levenshtein_similarity(text1, text2):
    """
    Calculates the Levenshtein similarity ratio between two texts.
    Returns a float between 0.0 and 1.0 (1.0 means identical).
    """
    if not text1 or not text2:
        return 0.0
    
    return Levenshtein.ratio(text1, text2)

def transcribe_with_gemini(audio_path):
    """
    Transcribes audio using Google Gemini 2.0 Flash.
    """
    try:
        # Upload file to Gemini
        logger.info(f"Uploading audio to Gemini: {audio_path}")
        audio_file = genai.upload_file(path=audio_path)

        # Check file state
        while audio_file.state.name == "PROCESSING":
             time.sleep(0.5)
             audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name == "FAILED":
             logger.error("Gemini failed to process the audio file.")
             return None
        
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.0}
        )
        
        prompt = """
        이 오디오 파일은 면접 지원자의 답변입니다.
        들리는 내용을 그대로(토씨 하나 틀리지 않게) 텍스트로 변환(전사)해 주세요. 
        오직 전사된 내용만 출력하세요. (부가 설명 금지, 음성 없으면 '답변 없음' 출력)
        """
        
        response = model.generate_content([prompt, audio_file])
        result = response.text.strip()
        logger.info(f"[Gemini STT]: {result[:50]}...")
        return result
             
    except Exception as e:
        logger.error(f"Gemini STT Error: {e}")
        return None

def transcribe_with_whisper(audio_path):
    """
    Transcribes audio using OpenAI Whisper API.
    """
    if not openai_client:
        return None
        
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko"
            )
        result = transcript.text.strip()
        logger.info(f"[Whisper STT]: {result[:50]}...")
        return result
    except Exception as e:
        logger.error(f"Whisper STT Error: {e}")
        return None

def transcribe_audio(audio_path):
    """
    Main STT function with cross-verification.
    1. Try Gemini STT.
    2. Try Whisper STT.
    3. Calculate Levenshtein similarity.
    4. If similarity >= 95%, use Gemini. Else use Whisper (fallback).
    """
    if not os.path.exists(audio_path):
        return "답변 없음 (파일 없음)"
        
    file_size = os.path.getsize(audio_path)
    if file_size < 100:
         return "답변 없음"

    # Execute STT in parallel or sequence (Sequence for now to keep it simple)
    gemini_result = transcribe_with_gemini(audio_path)
    whisper_result = transcribe_with_whisper(audio_path)
    
    # Case 1: Both failed
    if not gemini_result and not whisper_result:
        return "답변 없음 (변환 실패)"

    # Case 2: Only Gemini succeeded
    if gemini_result and not whisper_result:
        logger.info("Using Gemini result (Whisper failed or not configured).")
        return gemini_result
    
    # Case 3: Only Whisper succeeded
    if not gemini_result and whisper_result:
        logger.info("Using Whisper result (Gemini failed).")
        return whisper_result

    # Case 4: Both succeeded - Cross Verification
    similarity = calculate_levenshtein_similarity(gemini_result, whisper_result)
    similarity_percent = similarity * 100
    
    logger.info(f"STT Cross Verification: Similarity = {similarity_percent:.2f}%")
    
    if similarity_percent >= 95.0:
        logger.info("Similiarity >= 95%. Selecting Gemini result.")
        final_result = gemini_result
    else:
        logger.info("Similiarity < 95%. Selecting Whisper result (more reliable for audio).")
        final_result = whisper_result
        
    if not final_result or final_result.lower() == "답변 없음":
        return "답변 없음"
        
    return final_result

