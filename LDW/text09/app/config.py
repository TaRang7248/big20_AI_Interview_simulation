import os
import logging
from dotenv import load_dotenv

# ---------------------------------------------------------
# FFmpeg 경로 설정 (오디오/비디오 처리에 필수)
# ---------------------------------------------------------
# FFmpeg를 시스템 PATH에 추가하여 pydub/librosa 등이 찾을 수 있도록 함
ffmpeg_path = r"C:\ffmpeg\bin"
if os.path.exists(ffmpeg_path):
    os.environ["PATH"] += os.pathsep + ffmpeg_path
    logging.info(f"FFmpeg 경로를 PATH에 추가했습니다: {ffmpeg_path}")
else:
    logging.warning(f"FFmpeg 경로를 찾을 수 없습니다: {ffmpeg_path}. 오디오/비디오 처리가 실패할 수 있습니다.")


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# .env 파일 로드 (상위 디렉토리 탐색)
# ---------------------------------------------------------
# 현재 파일 위치: app/config.py → 부모: app → 부모: text09 (프로젝트 루트)
# .env 파일 위치: text09의 상위 2단계 = .../big20/.env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../LDW/text09
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))  # .../big20

# .env 로드 (big20 루트에 위치한다고 가정)
load_dotenv(os.path.join(ROOT_DIR, '.env'))

# ---------------------------------------------------------
# 데이터베이스 설정
# ---------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

# ---------------------------------------------------------
# 경로 설정 (서버 실행 위치인 text09/ 기준 상대 경로)
# ---------------------------------------------------------
# 이력서 업로드 폴더
UPLOAD_FOLDER = 'uploads/resumes'
# 면접 답변 오디오 폴더
AUDIO_FOLDER = 'uploads/audio'
# TTS 오디오 출력 폴더
TTS_FOLDER = 'uploads/tts_audio'
# Wav2Lip 립싱크 비디오 출력 폴더
WAV2LIP_OUTPUT_FOLDER = 'uploads/Wav2Lip_mp4'

# 데이터 폴더 (모델 입력 데이터 등)
DATA_FOLDER = 'data'

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
WAV2LIP_FACE_IMAGE = os.path.join(BASE_DIR, "data", "man.png")

# ---------------------------------------------------------
# 필수 디렉토리 자동 생성
# ---------------------------------------------------------
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
os.makedirs(WAV2LIP_OUTPUT_FOLDER, exist_ok=True)
