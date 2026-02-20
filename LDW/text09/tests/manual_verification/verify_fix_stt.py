
import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock configurations/dependencies to avoid loading actual models
with patch('app.services.stt_service.genai') as mock_genai, \
     patch('app.services.stt_service.OpenAI') as mock_openai, \
     patch('app.services.stt_service.librosa') as mock_librosa:

    # Setup Logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Import service after mocking
    from app.services.stt_service import transcribe_audio

    print("--- Testing transcribe_audio with failed preprocessing (None returns) ---")

    # Mock preprocess_audio to simulate failure
    with patch('app.services.stt_service.preprocess_audio') as mock_preprocess:
        mock_preprocess.return_value = ("test_audio.wav", None, None) # Simulate failure
        
        # Mock other calls to avoid actual file I/O
        with patch('app.services.stt_service.os.path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Mock transcribe_with_gemini/whisper
            with patch('app.services.stt_service.transcribe_with_gemini') as mock_gemini_stt, \
                 patch('app.services.stt_service.transcribe_with_whisper') as mock_whisper_stt:
                
                mock_gemini_stt.return_value = "테스트 답변입니다."
                mock_whisper_stt.return_value = "테스트 답변입니다." # Simple case
                
                # Mock analyze_audio_features to NOT crash on None
                # We need to ensure analyze_audio_features is called. 
                # Our actual implementation of analyze_audio_features handles None by trying to reload
                # So we should validly mock librosa.load to fail or succeed?
                # Let's mock analyze_audio_features directly to focus on transcribe_audio's duration logic
                
                with patch('app.services.stt_service.analyze_audio_features') as mock_analyze:
                     mock_analyze.return_value = {"silence_duration": 0}

                     # Mock librosa.get_duration in stt_service scope (if not handled by 'path' arg logic)
                     # In our fix, we use path=... if y is None.
                     # mock_librosa.get_duration is already mocked via outer patch
                     mock_librosa.get_duration.return_value = 5.0 

                     try:
                         result = transcribe_audio("test_audio.wav")
                         print("Successfully executed transcribe_audio.")
                         print(f"Result Text: {result['text']}")
                         print(f"Speech Rate: {result['analysis'].get('speech_rate')}")
                         print("Test PASSED: No crash occurred.")
                     except Exception as e:
                         print(f"Test FAILED with Exception: {e}")
                         import traceback
                         traceback.print_exc()

