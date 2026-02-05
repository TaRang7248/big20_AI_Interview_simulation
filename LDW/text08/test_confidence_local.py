import sys
import os
import cv2
import numpy as np

# Add parent directory to path to import services
sys.path.append(os.getcwd())

from services.confidence_service import ConfidenceService

def test_confidence_initialization():
    print("Testing ConfidenceService initialization...")
    try:
        service = ConfidenceService()
        print("✅ ConfidenceService initialized successfully.")
        return service
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return None

def test_frame_processing(service):
    print("Testing frame processing with black image...")
    try:
        # Create a black image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        success, encoded_img = cv2.imencode('.jpg', img)
        if not success:
            print("❌ Failed to encode dummy image.")
            return

        image_bytes = encoded_img.tobytes()
        
        # Process the frame
        service.process_frame(image_bytes)
        print("✅ Processed dummy frame successfully (no face expected).")
        
        # Check score (should be 0 or handle division by zero gracefully)
        score = service.get_confidence_score()
        print(f"✅ Initial score (no faces): {score}")
        
    except Exception as e:
        print(f"❌ Frame processing failed: {e}")

if __name__ == "__main__":
    service = test_confidence_initialization()
    if service:
        test_frame_processing(service)
