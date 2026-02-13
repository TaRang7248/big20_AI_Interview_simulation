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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # .../LDW/text09
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR)) # .../big20 (추정) - 원본 로직 유지

# 원본 코드: os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
# server.py 기준: dir(server.py) = text09
# dir(text09) = LDW
# dir(LDW) = big20_AI_Interview_simulation (아, 여기가 루트인가 봅니다)
# 원본이 잘 작동했다면, 새 위치인 app/config.py에서는 dirname을 4번 해야 같음.

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")

# Paths (Relative to execute entry point, usually text09/)
UPLOAD_FOLDER = 'uploads/resumes'
AUDIO_FOLDER = 'uploads/audio'
TTS_FOLDER = 'uploads/tts_audio'

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
