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

    @patch('app.services.stt_service.calculate_average_rms')
    @patch('app.services.stt_service.check_vad_activity')
    @patch('app.services.stt_service.transcribe_with_gemini')
    @patch('app.services.stt_service.transcribe_with_whisper')
    @patch('app.services.stt_service.os.path.exists')
    @patch('app.services.stt_service.os.path.getsize')
    @patch('app.services.stt_service.preprocess_audio')
    @patch('app.services.stt_service.analyze_audio_features')
    def test_transcribe_audio_high_similarity(self, mock_analyze, mock_preprocess, mock_getsize, mock_exists, mock_whisper, mock_gemini, mock_vad, mock_rms):
        # Setup
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_rms.return_value = 0.1 # High enough to pass
        mock_vad.return_value = 0.5 # High enough to pass
        mock_preprocess.return_value = ("dummy_proc.wav", None, None)
        mock_analyze.return_value = {"pitch_jitter": 0.1}
        
        # Scenario: Both STTs return almost identical text (>= 95%)
        mock_gemini.return_value = "안녕하세요 저는 지원자입니다."
        mock_whisper.return_value = "안녕하세요 저는 지원자입니다" # Period diff
        
        # Expected: Gemini result selected
        result_dict = transcribe_audio("dummy.webm")
        
        # Check dict format
        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict["text"], "안녕하세요 저는 지원자입니다.")
        
    @patch('app.services.stt_service.calculate_average_rms')
    @patch('app.services.stt_service.check_vad_activity')
    @patch('app.services.stt_service.transcribe_with_gemini')
    @patch('app.services.stt_service.transcribe_with_whisper')
    @patch('app.services.stt_service.os.path.exists')
    @patch('app.services.stt_service.os.path.getsize')
    @patch('app.services.stt_service.preprocess_audio')
    @patch('app.services.stt_service.analyze_audio_features')
    def test_transcribe_audio_low_similarity(self, mock_analyze, mock_preprocess, mock_getsize, mock_exists, mock_whisper, mock_gemini, mock_vad, mock_rms):
        # Setup
        mock_exists.return_value = True
        mock_getsize.return_value = 1000
        mock_rms.return_value = 0.1
        mock_vad.return_value = 0.5
        mock_preprocess.return_value = ("dummy_proc.wav", None, None)
        mock_analyze.return_value = {"pitch_jitter": 0.1}
        
        # Scenario: Low similarity
        mock_gemini.return_value = "이상한 환각 결과입니다."
        mock_whisper.return_value = "안녕하세요 저는 지원자입니다."
        
        # Expected: Whisper result selected (Fallback)
        result_dict = transcribe_audio("dummy.webm")
        
        self.assertEqual(result_dict["text"], "안녕하세요 저는 지원자입니다.")

if __name__ == '__main__':
    unittest.main()
