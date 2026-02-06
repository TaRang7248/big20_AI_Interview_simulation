import cv2
import numpy as np
import os

class VideoService:
    def __init__(self):
        # Load Haar Cascades for face detection
        # Note: cv2.data.haarcascades returns the directory path to cascades
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    def analyze_video(self, video_path: str):
        """
        Analyzes a video file for Confidence and Attitude.
        Returns a dictionary with scores (0-100).
        """
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return {"confidence": 50, "attitude": 50, "avg_video_score": 50}

        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print("Error opening video stream or file")
            return {"confidence": 50, "attitude": 50, "avg_video_score": 50}

        total_frames = 0
        face_detected_frames = 0
        prev_gray = None
        movement_scores = []

        # Process every Nth frame to save time
        frame_skip = 5 
        current_frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            current_frame_idx += 1
            if current_frame_idx % frame_skip != 0:
                continue

            total_frames += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Confidence: Face Detection
            # If candidate faces the camera, face is detected.
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) > 0:
                face_detected_frames += 1
            
            # 2. Attitude: Movement Analysis (Optical Flowish)
            # Check difference between current and previous frame to detect excessive movement or stillness
            if prev_gray is not None:
                # Resize for speed
                small_gray = cv2.resize(gray, (200, 200))
                small_prev = cv2.resize(prev_gray, (200, 200))
                
                score, _ =  cv2.mean(cv2.absdiff(small_gray, small_prev))
                movement_scores.append(score)
            
            prev_gray = gray

        cap.release()

        if total_frames == 0:
             return {"confidence": 50, "attitude": 50, "avg_video_score": 50}

        # --- Scoring Logic ---

        # Confidence: Percentage of frames with face detected
        # Ideally 100% face time = 100 score. 
        # But allow some margin.
        confidence_ratio = face_detected_frames / total_frames
        confidence_score = min(100, int(confidence_ratio * 120)) # Boost a bit so 80% detection -> 96 score

        # Attitude: Movement Stability
        # We want "stable but alive". 
        # Too low movement (< 2.0) = Frozen/Stiff? Or just good connection? Let's say Stiff.
        # Too high movement (> 20.0) = Distracted/Fidgeting.
        # Ideal range: 2.0 ~ 15.0
        
        avg_movement = np.mean(movement_scores) if movement_scores else 0
        
        attitude_score = 80 # Default start
        if avg_movement < 2.0:
            attitude_score = 70 # Too stiff
        elif 2.0 <= avg_movement <= 15.0:
            attitude_score = 90 + min(10, (15.0 - avg_movement)) # Good stability
        else:
            attitude_score = max(50, 100 - (avg_movement - 15.0) * 2) # Penalize high movement

        attitude_score = int(attitude_score)

        avg_video_score = (confidence_score + attitude_score) / 2

        print(f"[Video Analysis] Path: {video_path}")
        print(f"  - Total Frames (Analyzed): {total_frames}")
        print(f"  - Face Detected: {face_detected_frames} ({confidence_ratio:.2%}) -> Confidence: {confidence_score}")
        print(f"  - Avg Movement: {avg_movement:.2f} -> Attitude: {attitude_score}")

        return {
            "confidence": confidence_score,
            "attitude": attitude_score,
            "avg_video_score": avg_video_score
        }
