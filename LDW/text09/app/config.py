import os
import logging
import shutil
from dotenv import load_dotenv

# ---------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 프로젝트 루트 / .env 로드
# ---------------------------------------------------------
# 현재 파일 위치: app/config.py
# BASE_DIR: .../LDW/text09 (프로젝트 루트)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))  # .../big20

# .env 로드 (big20 루트에 위치한다고 가정)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ---------------------------------------------------------
# 데이터베이스 설정
# ---------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

# ---------------------------------------------------------
# FFmpeg 경로/실행파일 탐색 (Windows 안정화)
# ---------------------------------------------------------
# 1) PATH에 이미 잡혀 있으면 shutil.which("ffmpeg")로 탐색 가능
# 2) 기본 설치 경로로 많이 쓰는 C:\ffmpeg\bin\ffmpeg.exe도 추가 확인
DEFAULT_FFMPEG_DIR = r"C:\ffmpeg\bin"
DEFAULT_FFMPEG_EXE = os.path.join(DEFAULT_FFMPEG_DIR, "ffmpeg.exe")

def get_ffmpeg_exe() -> str | None:
    """ffmpeg 실행 파일 경로를 최대한 확실하게 찾아 반환"""
    # (1) PATH에서 탐색
    ff = shutil.which("ffmpeg")
    if ff:
        return ff

    # (2) 기본 경로(C:\ffmpeg\bin) 존재 시 PATH에 추가 후 재탐색
    if os.path.exists(DEFAULT_FFMPEG_DIR):
        os.environ["PATH"] += os.pathsep + DEFAULT_FFMPEG_DIR
        ff2 = shutil.which("ffmpeg")
        if ff2:
            return ff2

    # (3) 기본 exe 경로 직접 확인
    if os.path.exists(DEFAULT_FFMPEG_EXE):
        return DEFAULT_FFMPEG_EXE

    return None

FFMPEG_EXE = get_ffmpeg_exe()
if FFMPEG_EXE:
    logger.info(f"✅ FFmpeg 실행 파일 확인: {FFMPEG_EXE}")
else:
    logger.warning("⚠️ FFmpeg 실행 파일을 찾을 수 없습니다. 오디오/비디오 처리가 실패할 수 있습니다.")

# ---------------------------------------------------------
# 경로 설정 (전부 절대경로로 통일!!!)
#   - 실행 위치(CWD)에 의존하지 않게 만들어서
#     '저장 위치'와 '정적 서빙 위치'가 항상 같아지게 함
# ---------------------------------------------------------
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 이력서 업로드 폴더
UPLOAD_FOLDER = os.path.join(UPLOADS_DIR, "resumes")

# 면접 답변 오디오 폴더(지원자 녹음 webm 등)
AUDIO_FOLDER = os.path.join(UPLOADS_DIR, "audio")

# TTS 오디오 출력 폴더
TTS_FOLDER = os.path.join(UPLOADS_DIR, "tts_audio")

# Wav2Lip 립싱크 비디오 출력 폴더
WAV2LIP_OUTPUT_FOLDER = os.path.join(UPLOADS_DIR, "Wav2Lip_mp4")

# 데이터 폴더 (모델 입력 데이터 등)
DATA_FOLDER = DATA_DIR

# ---------------------------------------------------------
# API 키 설정
# ---------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------------------------------------------------
# Wav2Lip 비디오 생성 관련 경로 설정
# ---------------------------------------------------------
# Wav2Lip 엔진 디렉토리 (프로젝트 루트 기준)
WAV2LIP_DIR = os.path.join(BASE_DIR, "Wav2Lip")

# Wav2Lip 추론 스크립트 경로
WAV2LIP_INFERENCE_SCRIPT = os.path.join(WAV2LIP_DIR, "inference.py")

# Wav2Lip GAN 가중치 파일 경로
WAV2LIP_CHECKPOINT = os.path.join(WAV2LIP_DIR, "checkpoints", "wav2lip_gan.pth")

# 면접관 얼굴 이미지 경로
WAV2LIP_FACE_IMAGE = os.path.join(DATA_DIR, "man.png")

# ---------------------------------------------------------
# 필수 디렉토리 자동 생성
# ---------------------------------------------------------
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
os.makedirs(WAV2LIP_OUTPUT_FOLDER, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)