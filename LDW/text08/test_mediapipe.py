import mediapipe as mp
try:
    print(f"Mediapipe version: {mp.__version__}")
    print(f"Solutions available: {dir(mp.solutions)}")
    face_mesh = mp.solutions.face_mesh
    print("FaceMesh initialized successfully")
except AttributeError as e:
    print(f"AttributeError: {e}")
except Exception as e:
    print(f"Error: {e}")
