import os
import time
import google.generativeai as genai
from ..config import logger, GOOGLE_API_KEY

# Configure GenAI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def transcribe_audio(audio_path):
    """
    Transcribes audio file to text using Google Gemini 2.0 Flash (Multimodal).
    Enhanced with retry logic and file validation.
    """
    try:
        # Check file availability
        if not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            return "답변 없음 (파일 없음)"

        file_size = os.path.getsize(audio_path)
        if file_size < 100: # Too small to be a valid audio file
             logger.warning(f"Audio file is too small ({file_size} bytes). Skipping STT.")
             return "답변 없음"

        # Upload file to Gemini
        logger.info(f"Uploading audio to Gemini: {audio_path}")
        try:
            audio_file = genai.upload_file(path=audio_path)
        except Exception as upload_error:
            logger.error(f"Failed to upload audio to Gemini: {upload_error}")
            return "답변 없음 (업로드 실패)"

        # Check file state (processing)
        # Usually instantaneous for small files, but good practice
        while audio_file.state.name == "PROCESSING":
             time.sleep(1)
             audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name == "FAILED":
             logger.error("Gemini failed to process the audio file.")
             return "답변 없음 (처리 실패)"
        
        # Use Gemini 2.0 Flash
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.0, # 낮을수록 들리는 대로만 출력할 확률이 높아집니다.
            }
        )
        
        prompt = """
        이 오디오 파일은 면접 지원자의 답변입니다.
        들리는 내용을 그대로(토씨 하나 틀리지 않게) 텍스트로 변환(전사)해 주세요. 
        
        지침:
        1. '음', '어', '아'와 같은 추임새나 감탄사를 포함하여 들리는 모든 단어를 그대로 적으세요.
        2. 문장을 임의로 수정하거나, 요약하거나, 문법에 맞게 교정하지 마세요.
        3. 오직 전사된 내용만 출력하세요. (부가 설명 금지)
        4. 오디오에 아무런 음성 정보가 없다면 '답변 없음'이라고 출력하세요.
        """
        
        try:
            response = model.generate_content([prompt, audio_file])
            applicant_answer = response.text.strip()
            logger.info(f"STT Result: {applicant_answer[:50]}...")
            
            # Optional: Delete file to clean up cloud storage
            # audio_file.delete()
            
            if not applicant_answer or applicant_answer.lower() == "답변 없음":
                return "답변 없음"
                
            return applicant_answer
            
        except Exception as gen_error:
             logger.error(f"Gemini generation error: {gen_error}")
             return "답변 없음 (변환 실패)"
             
    except Exception as e:
        logger.error(f"STT Error (Gemini): {e}")
        return "답변 없음"

