
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from app.services.video_analysis_service import video_analysis_service

# Setup dummy environment paths
TEST_DIR = os.path.join(os.getcwd(), "test_uploads", "audio")
os.makedirs(TEST_DIR, exist_ok=True)

SESSION_NAME = "test-session-1"
FILENAME = f"2026-02-19-12-00-00-{SESSION_NAME}.webm"
FILE_PATH = os.path.join(TEST_DIR, FILENAME)

def create_dummy_video(path):
    print(f"Creating dummy video at {path}...")
    height, width = 480, 640
    fps = 10
    duration_sec = 2
    
    fourcc = cv2.VideoWriter_fourcc(*'vp80') # webm compatible codec often used
    # If vp80 fails, try mp4v and .mp4 for testing, but user asked for webm
    # OpenCV writing webm might depend on backend. Let's try.
    
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print("Error: Could not open video writer. Trying .mp4 for test purposes (logic is same)")
        path = path.replace(".webm", ".mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    
    for _ in range(fps * duration_sec):
        # Create a frame with a "face" (just a circle)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 100, (255, 255, 255), -1) 
        out.write(frame)
        
    out.release()
    print(f"Created {path}")
    return path

def test_analysis():
    print("Starting analysis test...")
    real_path = create_dummy_video(FILE_PATH)
    
    # Run analysis
    results = video_analysis_service.process_session_videos(SESSION_NAME, TEST_DIR)
    
    print("\n[Analysis Results]")
    print(results)
    
    if results["processed_files"] > 0:
        print("SUCCESS: Processed video files.")
    else:
        print("FAILURE: Did not process any files.")

    # Cleanup
    try:
        os.remove(real_path)
    except:
        pass

if __name__ == "__main__":
    test_analysis()
