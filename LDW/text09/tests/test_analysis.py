import sys
import os
import cv2
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.video_analysis_service import video_analysis_service

def create_dummy_image():
    # Create a 640x480 black image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw a circle (faceish)
    cv2.circle(img, (320, 240), 100, (255, 255, 255), -1)
    return img

def test_analysis():
    print("Testing VideoAnalysisService...")
    
    img = create_dummy_image()
    success, encoded_img = cv2.imencode('.jpg', img)
    if not success:
        print("Failed to encode dummy image.")
        return

    img_bytes = encoded_img.tobytes()
    
    try:
        results = video_analysis_service.process_frame(img_bytes)
        print("Analysis Result:")
        print(results)
        
        if "error" in results:
            print("Test Failed with error.")
        else:
            print("Test Passed: Result keys present.")
            # Check expected keys
            expected_keys = ["face_mesh", "pose", "gaze", "emotion"]
            missing = [k for k in expected_keys if k not in results]
            if missing:
                print(f"Missing keys: {missing}")
            else:
                print("All expected keys found.")
                
    except Exception as e:
        print(f"Test Crashed: {e}")

if __name__ == "__main__":
    test_analysis()
