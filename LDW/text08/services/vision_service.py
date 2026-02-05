import cv2
import numpy as np
from deepface import DeepFace
import tempfile
import os

class VisionService:
    def __init__(self):
        # 모델 로드 (첫 실행 시 다운로드 될 수 있음)
        pass

    async def analyze_frame(self, image_data: bytes):
        try:
            # 바이트 데이터를 numpy array로 변환
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {"error": "Image decode failed"}

            # DeepFace 분석
            # actions=['emotion'] only for efficiency
            # enforce_detection=False allows analysis even if face is not perfectly clear
            analysis = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
            
            if isinstance(analysis, list):
                result = analysis[0]
            else:
                result = analysis

            return {
                "dominant_emotion": result['dominant_emotion'],
                "emotion_scores": result['emotion']
            }
        except Exception as e:
            print(f"Vision Analysis Error: {e}")
            return {"dominant_emotion": "neutral", "error": str(e)}
