import cv2
import numpy as np
import mediapipe as mp
import time

class ConfidenceService:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 분석 상태 저장
        self.total_frames = 0
        self.gaze_center_frames = 0
        self.stable_head_frames = 0
        self.smile_frames = 0
        
        # 캘리브레이션용 (초기 자세 기준)
        self.initial_pose = None
        
        self.start_time = None

    def _calculate_gaze(self, landmarks):
        """
        간단한 시선 추적: 홍채(Iris)의 위치가 눈의 중심에 있는지 확인
        Left Eye Iris: 468-472
        Right Eye Iris: 473-477
        """
        # 실제 정교한 시선 추적은 복잡하므로, 여기서는 머리 방향 + 눈의 개폐 정도로 약식 구현하거나
        # MediaPipe의 Iris landmarks를 활용할 수 있습니다.
        # 여기서는 "정면을 보고 있는가"를 머리 회전각(Pose)으로 주로 판단하고, 
        # 눈 깜박임 등을 보조 지표로 쓸 수 있습니다.
        # 이번 버전에서는 Head Pose를 메인으로 사용합니다.
        return True

    def _calculate_head_pose(self, img_w, img_h, landmarks):
        """
        머리 회전각(Yaw, Pitch, Roll) 계산을 통해 정면 주시 여부 판단
        """
        face_3d = []
        face_2d = []

        # 코 끝, 턱 끝, 왼쪽 눈 끝, 오른쪽 눈 끝, 입 왼쪽, 입 오른쪽
        mesh_points = [1, 152, 33, 263, 61, 291]
        
        for idx in mesh_points:
            lm = landmarks[idx]
            x, y = int(lm.x * img_w), int(lm.y * img_h)
            face_2d.append([x, y])
            face_3d.append([x, y, lm.z]) # 깊이 z는 상대적임

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        # 카메라 매트릭스 (가정)
        focal_length = 1 * img_w
        cam_matrix = np.array([ [focal_length, 0, img_h / 2],
                                [0, focal_length, img_w / 2],
                                [0, 0, 1]])

        # 왜곡 계수 (없음 가정)
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        # PnP 문제 해결 -> 회전 벡터, 이동 벡터
        success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)

        if not success:
            return False

        # 회전 행렬로 변환
        rmat, jac = cv2.Rodrigues(rot_vec)

        # 오일러 각으로 변환
        angles, mtxR, mtxQ, Q, x, y, z = cv2.RQDecomp3x3(rmat)

        # x: Pitch (위아래), y: Yaw (좌우), z: Roll (기울기)
        pitch = angles[0] * 360
        yaw = angles[1] * 360
        
        # 정면 기준: 상하좌우 15도 이내
        if -15 < pitch < 15 and -15 < yaw < 15:
            return True
        return False

    def process_frame(self, image_data: bytes):
        """
        프레임 데이터를 받아 분석하고 내부 상태를 업데이트함
        """
        try:
            if self.start_time is None:
                self.start_time = time.time()

            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return
                
            img_h, img_w, _ = img.shape
            
            # MediaPipe를 위해 RGB로 변환
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(img_rgb)

            self.total_frames += 1

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # 1. Head Pose (정면 주시 여부)
                    if self._calculate_head_pose(img_w, img_h, face_landmarks.landmark):
                        self.gaze_center_frames += 1
                        self.stable_head_frames += 1 # 간단히 정면 주시를 안정성으로 간주
                    
                    # 2. Smile Detection (입꼬리 랜드마크 활용)
                    # 입 왼쪽: 61, 입 오른쪽: 291, 윗입술: 13, 아랫입술: 14
                    # 입꼬리가 올라갔는지 간단히 y좌표 비교 (눈 대비 등)는 복잡하므로 
                    # 여기서는 간단히 입의 가로 길이가 세로 길이 대비 일정 비율 이상이면 미소로 간주하거나
                    # DeepFace 감정 분석 결과를 병합하는 것이 좋음.
                    # 여기서는 MediaPipe만으로 약식 구현: 입 꼬리(61, 291)의 y좌표가 입 중심(13, 14)보다 현저히 낮으면? (일반적으로 웃으면 입꼬리가 올라감 -> y좌표가 작아짐)
                    # 이것은 꽤 까다로우므로, 여기서는 '안정적인 자세' 점수에 비중을 둡니다.
                    pass

        except Exception as e:
            print(f"Confidence Analysis Error: {e}")

    def get_confidence_score(self):
        """
        최종 자신감 점수 계산 (0~100)
        """
        if self.total_frames == 0:
            return 0
            
        # 1. 시선/자세 안정성 점수 (100점 만점)
        stability_score = (self.stable_head_frames / self.total_frames) * 100
        
        # 점수 보정 (너무 엄격하지 않게)
        final_score = min(100, stability_score * 1.2) # 20% 보너스
        
        return int(final_score)

    def reset(self):
        self.total_frames = 0
        self.gaze_center_frames = 0
        self.stable_head_frames = 0
        self.start_time = None
