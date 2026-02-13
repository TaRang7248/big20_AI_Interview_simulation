import os
from ..config import logger
from .llm_service import client  # Reuse OpenAI client

def transcribe_audio(audio_path):
    """
    Transcribes audio file to text using OpenAI Whisper API.
    """
    applicant_answer = ""
    try:
        # Check file size before sending to Whisper
        if not os.path.exists(audio_path):
            return "답변 없음 (파일 없음)"

        file_size = os.path.getsize(audio_path)
        if file_size < 100: # Too small to be a valid audio file
             return "답변 없음"

        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko",
                prompt="이것은 면접 지원자의 답변입니다. 절대로 추측하지 마세요. ai 개인적인 생각을 넣지 마세요. 오직 지원자의 명확한 답변 내용만 텍스트로 변환해 주세요."
            )
        applicant_answer = transcript.text.strip()
        
        # Check if answer is too short
        if len(applicant_answer) < 2:
            logger.info(f"Filtered Short Noise or Empty: {applicant_answer}")
            return "답변 없음"
            
        return applicant_answer

    except Exception as stt_e:
        logger.error(f"STT Error: {stt_e}")
        return "답변 없음"
