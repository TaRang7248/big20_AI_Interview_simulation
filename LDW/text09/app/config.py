import os
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 로드 (상위 디렉토리 탐색)
# 현재 파일 위치: app/config.py -> 부모: app -> 부모: text09 -> 부모: LDW
# 원본 server.py 위치 기준과 동일하게 맞춤 (text09 폴더 내에 server.py가 있었음)
# .env 위치는 text09의 상위 3단계 위? 원본 코드 참조:
# os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
# 원본 server.py 경로: .../LDW/text09/server.py
# 원본 로드 경로: .../LDW/text09/../../.env -> .../big20/.env (추정)
# 새 경로: .../LDW/text09/app/config.py
# 따라서 한 단계 더 올라가야 함.

# New path adjustment: config is in app/config.py.
# __file__ = .../text09/app/config.py
# dirname(__file__) = .../text09/app
# dirname(dirname(__file__)) = .../text09 (This is the project root now)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # .../LDW/text09
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR)) # .../big20 (Keep original logic if needed)

# Load .env (Adjust path if needed, assuming it's still in big20 root)
load_dotenv(os.path.join(ROOT_DIR, '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

# Paths (Relative to execute entry point, usually text09/)
# Updated for new structure
UPLOAD_FOLDER = 'uploads/resumes' # Keep uploads in root or move to data? Let's keep in root for now as per plan
AUDIO_FOLDER = 'uploads/audio'
TTS_FOLDER = 'uploads/tts_audio'

# Use data folder for specific data files if referenced
DATA_FOLDER = 'data'

# Google Gemini API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
