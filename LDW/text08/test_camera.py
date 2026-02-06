
import cv2
import time

def test_camera():
    print("Testing camera connection...")
    
    # Try indices 0 to 3
    for index in range(4):
        print(f"Attrubuting index {index}...")
        cap = cv2.VideoCapture(index)
        
        if cap is None or not cap.isOpened():
            print(f"Warning: unable to open video source: {index}")
            continue
            
        print(f"Success: Video source {index} opened.")
        
        ret, frame = cap.read()
        if ret:
            print(f"Success: Frame captured from source {index}. Resolution: {frame.shape[1]}x{frame.shape[0]}")
            # Optional: Save a frame to prove it works
            # cv2.imwrite(f"camera_test_{index}.png", frame)
        else:
            print(f"Error: Could not read frame from source {index}")
            
        cap.release()
        return  # Found a working camera

    print("Error: No working camera found on indices 0-3.")

if __name__ == "__main__":
    test_camera()
