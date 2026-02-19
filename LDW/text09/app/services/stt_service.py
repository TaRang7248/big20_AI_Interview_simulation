import os
import google.generativeai as genai
from ..config import logger, GOOGLE_API_KEY

# Configure GenAI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def transcribe_audio(audio_path):
    """
    Transcribes audio file to text using Google Gemini 2.0 Flash (Multimodal).
    """
    try:
        # Check file availability
        if not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            return "답변 없음 (파일 없음)"

        file_size = os.path.getsize(audio_path)
        if file_size < 100: # Too small to be a valid audio file
             return "답변 없음"

        # Upload file to Gemini
        # Note: Gemini 1.5/2.0 Flash supports audio inputs directly via File API
        logger.info(f"Uploading audio to Gemini: {audio_path}")
        audio_file = genai.upload_file(path=audio_path)
        
        # Use Gemini 2.0 Flash
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = "이 오디오 파일은 면접 지원자의 답변입니다. 오직 지원자의 명확한 답변 내용만 텍스트로 변환(전사)해주세요. 다른 부가적인 설명이나 감탄사 등은 제외하세요."
        
        response = model.generate_content([prompt, audio_file])
        
        applicant_answer = response.text.strip()
        logger.info(f"STT Result: {applicant_answer[:50]}...")
        
        # Cleanup: It's good practice to delete the file from Gemini cloud if not needed, 
        # but for this simulation, we might rely on auto-expiration or handling it later.
        # audio_file.delete() # Optional: delete immediately if desired
        
        return applicant_answer

    except Exception as e:
        logger.error(f"STT Error (Gemini): {e}")
        return "답변 없음"

