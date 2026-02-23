import time
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.services.llm_service import generate_content_with_retry
from google.api_core.exceptions import ResourceExhausted

class TestTimeoutFix(unittest.TestCase):
    @patch('app.services.llm_service.genai.GenerativeModel')
    def test_generate_content_timeout_args(self, mock_model_cls):
        # Setup mock
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model
        
        # Call function
        try:
            generate_content_with_retry(mock_model, "test prompt")
        except:
            pass # We don't care about return, just args
            
        # Verify call args include socket_options/timeout
        # Note: We passed request_options={'timeout': 30}
        args, kwargs = mock_model.generate_content.call_args
        
        print(f"Call Kwargs: {kwargs}")
        
        self.assertIn('request_options', kwargs)
        self.assertEqual(kwargs['request_options']['timeout'], 30)
        print("✅ Timeout argument verification passed.")

if __name__ == '__main__':
    unittest.main()
