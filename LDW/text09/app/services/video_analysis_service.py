import logging
import os
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Optional dependencies for Video Analysis
VIDEO_ANALYSIS_AVAILABLE = False
try:
    import tensorflow as tf
    import tensorflow_hub as hub
    from deepface import DeepFace
    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Video Analysis dependencies missing: {e}. Video analysis features will be disabled.")

class VideoAnalysisService:
    def __init__(self):
        self.movenet_model = None
        self.DeepFace = None
        
        if VIDEO_ANALYSIS_AVAILABLE:
            try:
                # 1. Load MoveNet Thunder (Pose)
                logger.info("Loading MoveNet Thunder model...")
                self.movenet = hub.load("https://tfhub.dev/google/movenet/singlepose/thunder/4")
                self.movenet_model = self.movenet.signatures['serving_default']
                logger.info("MoveNet Thunder loaded.")
                
                # DeepFace
                self.DeepFace = DeepFace
            except Exception as e:
                logger.error(f"Failed to load Video Analysis models: {e}")
                self.movenet_model = None

        # 2. Load Dlib (Face & Gaze) - REMOVED
        self.detector = None
        self.predictor = None


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
            if self.movenet_model:
                input_image = tf.expand_dims(frame, axis=0)
                input_image = tf.cast(tf.image.resize_with_pad(input_image, 256, 256), dtype=tf.int32)
                
                # Run inference
                outputs = self.movenet_model(input_image)
                keypoints = outputs['output_0'].numpy()[0][0] # [17, 3] (y, x, score)
                
                # Check for high confidence keypoints (e.g., > 0.3)
                if np.max(keypoints[:, 2]) > 0.3:
                    results["pose"] = "detected"
                    results["pose_data"] = keypoints.tolist()

            # --- 3. DeepFace Emotion (Existing) ---
            if self.DeepFace:
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
