import cv2
import numpy as np

import tensorflow as tf
import tensorflow_hub as hub
import logging
import os

logger = logging.getLogger(__name__)

class VideoAnalysisService:
    def __init__(self):
        # 1. Load MoveNet Thunder (Pose)
        logger.info("Loading MoveNet Thunder model...")
        self.movenet = hub.load("https://tfhub.dev/google/movenet/singlepose/thunder/4")
        self.movenet_model = self.movenet.signatures['serving_default']
        logger.info("MoveNet Thunder loaded.")

        # 2. Load Dlib (Face & Gaze) - REMOVED
        # Dlib has been removed as per user request.
        self.detector = None
        self.predictor = None


        # DeepFace (Emotion) - Retaining existing logic if compatible, or removing if strictly replacing only MP
        # User asked to replace MediaPipe with MoveNet+Dlib. 
        # DeepFace is separate from MediaPipe, so keeping it for emotion analysis as per original file structure might be good, 
        # unless user explicitly said "ONLY use MoveNet and Dlib". 
        # The prompt says "MediaPipe (Google)를 제거하고 대신에 MoveNet Thunder... Dlib로...". 
        # DeepFace was used for emotion. I'll keep it as a fallback or auxiliary if needed, 
        # or better, purely use the requested ones to keep it clean as per "change to... check entire code".
        # However, the original code had DeepFace. I will keep it for Emotion to maintain feature parity unless told otherwise,
        # moving the import inside to avoid unused import if I decide to drop it.
        # Actually, let's keep DeepFace for Emotion as it was separate from MediaPipe in the original code.
        from deepface import DeepFace
        self.DeepFace = DeepFace

    def process_frame(self, image_bytes: bytes):
        """
        Process a single image frame (bytes) and return analysis results.
        """
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return {"error": "Failed to decode image"}

            # Resize for consistent processing if needed, but MoveNet handles its own resizing.
            # Dlib works on original or grayscale.
            
            results = {
                "face_mesh": None, # Kept key for compatibility, will populate with Dlib info
                "hands": None,     # MoveNet doesn't do hands specifically like MP Hands, but has wrist/elbow keypoints
                "pose": None,
                "emotion": None,
                "gaze": None
            }

            # --- 1. Dlib Face & Gaze Analysis ---
            # Dlib functionality has been removed.
            # Keeping keys for compatibility.
            results["face_mesh"] = None 
            results["gaze"] = None

            
            # --- 2. MoveNet Pose Analysis ---
            # MoveNet expects int32 tensor of shape [1, height, width, 3]
            input_image = tf.expand_dims(frame, axis=0)
            input_image = tf.cast(tf.image.resize_with_pad(input_image, 256, 256), dtype=tf.int32)
            
            # Run inference
            outputs = self.movenet_model(input_image)
            keypoints = outputs['output_0'].numpy()[0][0] # [17, 3] (y, x, score)
            
            # Check for high confidence keypoints (e.g., > 0.3)
            # 17 keypoints: nose, left eye, right eye, left ear, right ear, left shoulder, right shoulder, ...
            # We can check shoulders/nose for basic pose detection
            if np.max(keypoints[:, 2]) > 0.3:
                results["pose"] = "detected"
                results["pose_data"] = keypoints.tolist() # Optional: send raw data

            # --- 3. DeepFace Emotion (Existing) ---
            try:
                emotions = self.DeepFace.analyze(
                    img_path=frame, 
                    actions=['emotion'], 
                    enforce_detection=False,
                    detector_backend='opencv',
                    silent=True
                )
                if emotions and isinstance(emotions, list):
                    results["emotion"] = emotions[0]['dominant_emotion']
                elif emotions and isinstance(emotions, dict):
                    results["emotion"] = emotions['dominant_emotion']
            except Exception as e:
                # logger.error(f"DeepFace processing error: {e}")
                pass

            return results

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return {"error": str(e)}



video_analysis_service = VideoAnalysisService()
