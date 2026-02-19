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




    def analyze_video_file(self, file_path: str):
        """
        Analyzes a single video file frame by frame (sampling every N frames).
        Returns aggregated stats for logic.
        """
        if not os.path.exists(file_path):
            logger.error(f"Video file not found: {file_path}")
            return None

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file: {file_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0: fps = 30 # fallback

        frame_interval = int(fps) # Analyze 1 frame per second
        current_frame = 0
        
        analysis_stats = {
            "total_frames": 0,
            "analyzed_frames": 0,
            "emotions": [],
            "posture_issues": 0,
            "pose_confidence_scores": []
        }

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if current_frame % frame_interval == 0:
                # Encode frame to bytes for existing process_frame method
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                result = self.process_frame(frame_bytes)
                
                if result:
                    analysis_stats["analyzed_frames"] += 1
                    
                    # Collect Emotion
                    if result.get("emotion"):
                        analysis_stats["emotions"].append(result["emotion"])
                    
                    # Collect Pose Logic
                    # process_frame returns "pose": "detected" if confident
                    if result.get("pose") == "detected":
                        # Here we could accept more detailed logic if process_frame returned it.
                        # For now, let's assume if pose is NOT detected or low confidence, it might be an issue?
                        # Or if we had logic for "slouching"
                        pass
                    
                    # If we had "bad_posture" logic in process_frame:
                    if result.get("pose") == "bad_posture":
                         analysis_stats["posture_issues"] += 1

            current_frame += 1
        
        analysis_stats["total_frames"] = current_frame
        cap.release()
        return analysis_stats

    def process_session_videos(self, session_name: str, upload_dir: str):
        """
        Finds all .webm files in upload_dir that end with -{session_name}.webm
        and analyzes them.
        """
        logger.info(f"Searching for videos with session_name: {session_name} in {upload_dir}")
        
        aggregated_results = {
            "processed_files": 0,
            "total_emotions": [],
            "posture_issues_total": 0,
            "files": []
        }

        if not os.path.exists(upload_dir):
            logger.error(f"Upload directory does not exist: {upload_dir}")
            return aggregated_results

        for filename in os.listdir(upload_dir):
            # Check if file ends with -{session_name}.webm
            # Example: 2026-02-19-15-32-12-면접-1.webm
            if filename.endswith(f"-{session_name}.webm"):
                file_path = os.path.join(upload_dir, filename)
                logger.info(f"Analyzing video file: {filename}")
                
                stats = self.analyze_video_file(file_path)
                if stats:
                    aggregated_results["processed_files"] += 1
                    aggregated_results["total_emotions"].extend(stats["emotions"])
                    aggregated_results["posture_issues_total"] += stats["posture_issues"]
                    aggregated_results["files"].append(filename)

        return aggregated_results

video_analysis_service = VideoAnalysisService()
