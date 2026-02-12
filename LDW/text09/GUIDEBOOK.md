# AI 면접 시뮬레이션 가이드북 (GUIDEBOOK)

## 1. 개요 (Overview)
본 프로젝트는 **웹 기반 AI 면접 시뮬레이션**입니다. 사용자가 이력서(PDF)를 업로드하면, AI가 이를 분석하여 맞춤형 질문을 생성하고, 음성 인터페이스(STT/TTS)를 통해 실전과 같은 모의 면접을 진행합니다.

특히, 이력서 인식 성능을 극대화하기 위해 **PyMuPDF(이미지 변환) + EasyOCR(광학 문자 인식)** 기술을 도입하여, 텍스트형 PDF뿐만 아니라 스캔된 이미지형 PDF도 정확하게 인식합니다.

## 2. 개발 환경 (Environment)
- **OS**: Windows (권장)
- **Language**: Python 3.10+, JavaScript (Frontend)
- **Framework**: FastAPI (Backend), Vanilla JS/HTML/CSS (Frontend)
- **Database**: PostgreSQL (데이터 저장), Redis (옵션)
- **AI/ML Engine**: 
  - **PyTorch (CUDA 12.1)**: EasyOCR 및 로컬 ML 모델 가속
  - **OpenAI API**: GPT-4o (질문 생성, 평가), Whisper (STT)

## 3. 프로그램 실행 방법 (How to Run)

### 3.1. 필수 설치
1. **Python 패키지 설치**:
   ```bash
   pip install -r requirements.txt
   ```
2. **PyTorch (CUDA 12.1) 설치**:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

### 3.2. 서버 실행
터미널에서 `server.py`가 있는 디렉토리로 이동 후:
```bash
uvicorn server:app --reload
```
- 서버가 정상적으로 실행되면 `http://127.0.0.1:8000` 주소로 백엔드가 활성화됩니다.
- 실행 시 로그에 `✅ PyTorch CUDA Available!` 문구가 뜨는지 확인하세요.

### 3.3. 클라이언트 실행
`index.html` 파일을 브라우저(Chrome 권장)에서 엽니다. 또는 `Live Server` 확장을 사용하면 더 원활합니다.

## 4. 사용하는 주요 모델 및 라이브러리

### 4.1. PDF 분석 (OCR)
- **PyMuPDF (fitz)**: PDF 파싱 및 페이지를 고해상도 이미지로 렌더링.
- **EasyOCR**: 렌더링된 이미지에서 텍스트(한글/영어) 추출. GPU 가속 지원.

### 4.2. 대화형 AI (Generative AI)
- **GPT-4o (OpenAI)**: 
  - 이력서 기반 맞춤형 질문 생성.
  - 사용자 답변 평가 및 피드백.
  - 면접관 페르소나 연기.

### 4.3. 음성 인식 (STT)
- **Whisper (OpenAI API)**: 사용자의 음성 답변을 텍스트로 변환.

## 5. 주요 기능 사용법

1. **로그인/회원가입**: ID/PW를 생성하여 접속.
2. **채용 공고 관리**: (관리자) 직무 공고 생성 및 수정.
3. **이력서 업로드**: 지원하려는 공고에 맞춰 PDF 이력서 업로드. (이미지/스캔본 인식 가능)
4. **면접 시작**: 카메라/마이크 권한 허용 후 면접 시작.
5. **실시간 질의응답**: AI 면접관의 질문을 듣고 음성으로 답변.
6. **결과 피드백**: 면접 종료 후 기술, 문제해결, 소통 능력 등에 대한 AI의 상세 피드백 확인.

## 6. 파일 구조 설명 (File Structure)

```
📂 루트 디렉토리
├── 📄 server.py           # FastAPI 백엔드 메인 서버
├── 📄 index.html          # 메인 프론트엔드 UI
├── 📄 app.js             # 프론트엔드 로직 (API 호출, UI 제어)
├── 📄 styles.css         # 스타일 시트
├── 📄 requirements.txt    # 파이썬 의존성 목록
├── 📄 SETUP.md           # 상세 설치 가이드
├── 📂 db/                # 데이터베이스 관련 파일
├── 📂 uploads/           # 업로드된 이력서 및 오디오 저장소
└── 📂 __pycache__/       # 파이썬 캐시
```
