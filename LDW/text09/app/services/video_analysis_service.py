import logging
import os
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# 비디오 분석을 위한 선택적 의존성 확인
VIDEO_ANALYSIS_AVAILABLE = False
try:
    import tensorflow as tf
    import tensorflow_hub as hub
    from deepface import DeepFace
    VIDEO_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"비디오 분석 의존성 누락: {e}. 비디오 분석 기능이 비활성화됩니다.")

class VideoAnalysisService:
    def __init__(self):
        self.movenet_model = None
        self.DeepFace = None
        
        if VIDEO_ANALYSIS_AVAILABLE:
            try:
                # 1. MoveNet Thunder 로드 (자세 분석)
                logger.info("MoveNet Thunder 모델 로딩 중...")
                self.movenet = hub.load("https://tfhub.dev/google/movenet/singlepose/thunder/4")
                self.movenet_model = self.movenet.signatures['serving_default']
                logger.info("MoveNet Thunder 로드 완료.")
                
                # DeepFace 로드
                self.DeepFace = DeepFace
            except Exception as e:
                logger.error(f"비디오 분석 모델 로드 실패: {e}")
                self.movenet_model = None

        # 2. Dlib (얼굴 및 시선) - 제거됨
        self.detector = None
        self.predictor = None


    def process_frame(self, image_bytes: bytes):
        """
        단일 이미지 프레임(bytes)을 처리하고 분석 결과를 반환합니다.
        """
        try:
            # 이미지 디코딩
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return {"error": "이미지 디코딩 실패"}

            results = {
                "face_mesh": None, # 호환성을 위해 키 유지
                "hands": None,     # MoveNet은 손목/팔꿈치 키포인트는 있지만 전용 손 분석은 아님
                "pose": None,
                "emotion": None,
                "gaze": None
            }

            # --- 1. Dlib 얼굴 및 시선 분석 ---
            # Dlib 기능은 제거되었습니다. 호환성을 위해 키만 유지합니다.
            results["face_mesh"] = None 
            results["gaze"] = None

            
            # --- 2. MoveNet 자세 분석 ---
            # MoveNet은 [1, height, width, 3] 형태의 int32 텐서를 기대합니다.
            if self.movenet_model:
                input_image = tf.expand_dims(frame, axis=0)
                input_image = tf.cast(tf.image.resize_with_pad(input_image, 256, 256), dtype=tf.int32)
                
                # 추론 실행
                outputs = self.movenet_model(input_image)
                keypoints = outputs['output_0'].numpy()[0][0] # [17, 3] (y, x, score)
                
                # 신뢰도가 높은 키포인트 확인 (예: > 0.3)
                if np.max(keypoints[:, 2]) > 0.3:
                    results["pose"] = "detected"
                    results["pose_data"] = keypoints.tolist()

            # --- 3. DeepFace 감정 분석 ---
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
                    pass

            return results

        except Exception as e:
            logger.error(f"프레임 처리 중 오류 발생: {e}")
            return {"error": str(e)}

    def analyze_video_file(self, file_path: str):
        """
        단일 비디오 파일을 프레임별로 분석합니다 (N 프레임마다 샘플링).
        로직을 위한 집계된 통계를 반환합니다.
        """
        if not os.path.exists(file_path):
            logger.error(f"비디오 파일을 찾을 수 없음: {file_path}")
            return None

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            logger.error(f"비디오 파일을 열 수 없음: {file_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0: fps = 30 # 폴백

        frame_interval = int(fps) # 초당 1프레임 분석
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
                # 기존 process_frame 메서드를 위해 프레임을 bytes로 인코딩
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                result = self.process_frame(frame_bytes)
                
                if result:
                    analysis_stats["analyzed_frames"] += 1
                    
                    # 감정 수집
                    if result.get("emotion"):
                        analysis_stats["emotions"].append(result["emotion"])
                    
                    # 자세 로직 (신뢰도가 높으면 감지됨으로 처리)
                    if result.get("pose") == "detected":
                        pass
                    
                    # "bad_posture" 로직이 있는 경우
                    if result.get("pose") == "bad_posture":
                         analysis_stats["posture_issues"] += 1

            current_frame += 1
        
        analysis_stats["total_frames"] = current_frame
        cap.release()
        return analysis_stats

    def process_session_videos(self, session_name: str, upload_dir: str):
        """
        upload_dir에서 -{session_name}.webm으로 끝나는 모든 비디오 파일을 찾아 분석합니다.
        """
        logger.info(f"세션명 {session_name}으로 {upload_dir}에서 비디오 검색 중")
        
        aggregated_results = {
            "processed_files": 0,
            "total_emotions": [],
            "posture_issues_total": 0,
            "files": []
        }

        if not os.path.exists(upload_dir):
            logger.error(f"업로드 디렉토리가 존재하지 않음: {upload_dir}")
            return aggregated_results

        from concurrent.futures import ThreadPoolExecutor

        video_files = []
        for filename in os.listdir(upload_dir):
            if filename.endswith(f"-{session_name}.webm"):
                video_files.append(os.path.join(upload_dir, filename))

        if not video_files:
            logger.info(f"분석할 비디오 파일이 없습니다 (세션: {session_name})")
            return aggregated_results

        logger.info(f"총 {len(video_files)}개의 비디오 파일 병렬 분석 시작...")

        # 비디오 파일 분석을 병렬로 수행하여 성능을 강화합니다.
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.analyze_video_file, fp): os.path.basename(fp) for fp in video_files}
            
            for future in futures:
                filename = futures[future]
                try:
                    stats = future.result()
                    if stats:
                        aggregated_results["processed_files"] += 1
                        aggregated_results["total_emotions"].extend(stats["emotions"])
                        aggregated_results["posture_issues_total"] += stats["posture_issues"]
                        aggregated_results["files"].append(filename)
                except Exception as e:
                    logger.error(f"비디오 파일 {filename} 분석 중 오류 발생: {e}")

        return aggregated_results

video_analysis_service = VideoAnalysisService()
