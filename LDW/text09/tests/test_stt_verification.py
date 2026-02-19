import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# App proper import path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.stt_service import transcribe_audio, calculate_levenshtein_similarity

class TestSTTCrossVerification(unittest.TestCase):
    
    def test_levenshtein_similarity(self):
        text1 = "안녕하세요 반갑습니다"
        text2 = "안녕하세요 반갑습니다"
        self.assertAlmostEqual(calculate_levenshtein_similarity(text1, text2), 1.0)

        text3 = "안녕하세요 반갑습니"
        # Similarity should be high but not 1.0
        self.assertTrue(0.8 < calculate_levenshtein_similarity(text1, text3) < 1.0)
        
        text4 = "완전히 다른 문장입니다"
        self.assertTrue(calculate_levenshtein_similarity(text1, text4) < 0.5)

    @patch('app.services.stt_service.transcribe_with_gemini')
    @patch('app.services.stt_service.transcribe_with_whisper')
    @patch('app.services.stt_service.os.path.exists')
    @patch('app.services.stt_service.os.path.getsize')
    def test_transcribe_audio_high_similarity(self, mock_getsize, mock_exists, mock_whisper, mock_gemini):
        # Setup
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        
        # Scenario: Both STTs return almost identical text (>= 95%)
        # "안녕하세요" vs "안녕하세요." (Punctuations might affect slightly, Levenshtein handles it)
        mock_gemini.return_value = "안녕하세요 저는 지원자입니다."
        mock_whisper.return_value = "안녕하세요 저는 지원자입니다" # Period diff
        
        # Expected: Gemini result selected
        result = transcribe_audio("dummy.webm")
        
        self.assertEqual(result, "안녕하세요 저는 지원자입니다.")
        
    @patch('app.services.stt_service.transcribe_with_gemini')
    @patch('app.services.stt_service.transcribe_with_whisper')
    @patch('app.services.stt_service.os.path.exists')
    @patch('app.services.stt_service.os.path.getsize')
    def test_transcribe_audio_low_similarity(self, mock_getsize, mock_exists, mock_whisper, mock_gemini):
        # Setup
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        
        # Scenario: Low similarity
        mock_gemini.return_value = "이상한 환각 결과입니다."
        mock_whisper.return_value = "안녕하세요 저는 지원자입니다."
        
        # Expected: Whisper result selected (Fallback)
        result = transcribe_audio("dummy.webm")
        
        self.assertEqual(result, "안녕하세요 저는 지원자입니다.")

if __name__ == '__main__':
    unittest.main()
