import cv2
import numpy as np
from deepface import DeepFace

def analyze_face_emotion(image_bytes: bytes) -> dict:
    """
    이미지 바이트를 받아 DeepFace로 감정을 분석합니다.
    (정확도 개선: retinaface 백엔드 사용)
    """
    try:
        # 1. 바이트 -> OpenCV 이미지로 변환
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"error": "이미지 디코딩 실패"}

        # 2. DeepFace 분석
        # [수정] detector_backend를 'opencv' -> 'retinaface'로 변경하여 정확도 대폭 향상
        analysis = DeepFace.analyze(
            img_path=img, 
            actions=['emotion'], 
            enforce_detection=False,
            detector_backend='ssd', # STT/LLM 속도 확보 위해, retinaface -> ssd 로 변경(26.02.04)
            align=True # 얼굴 정렬 수행
        )
        
        # 결과 추출
        result = analysis[0]
        
        return {
            "dominant_emotion": result['dominant_emotion'],
            "emotion_scores": result['emotion'],
            "confidence": result.get('face_confidence', 0) # 이제 이 점수가 높게 나올 겁니다
        }

    except Exception as e:
        print(f"👁️ [Vision Error]: {e}")
        return {"error": str(e), "dominant_emotion": "unknown"}

if __name__ == "__main__":
    print("비전 서비스 테스트 모듈입니다.")