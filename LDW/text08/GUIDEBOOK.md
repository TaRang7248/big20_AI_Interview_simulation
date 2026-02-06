# AI 면접 프로그램 가이드북 (GUIDEBOOK)

이 가이드북은 AI 면접 시뮬레이션 프로그램의 설치, 실행 및 사용 방법을 설명합니다.

## 1. 개요 (Overview)
이 프로그램은 사용자의 웹캠과 마이크를 사용하여 실제 면접 상황을 시뮬레이션합니다. Python과 PyScript를 활용하여 웹 브라우저 상에서 동작합니다.

## 2. 시스템 요구사항 (System Requirements)
- **OS**: Windows, macOS, Linux
- **Python**: 3.10 이상
- **Web Browser**: 최신 버전의 Chrome, Edge (PyScript 호환 브라우저)
- **Hardware**: 웹캠, 마이크

## 3. 설치 및 실행 (Installation & Run)

### 3.1 의존성 설치
프로젝트 루트 디렉토리에서 다음 명령어를 실행하여 필요한 패키지를 설치합니다.
```bash
pip install -r requirements.txt
```

### 3.2 서버 실행
다음 명령어로 로컬 서버를 실행합니다.
```bash
python start_app.py
```
서버가 실행되면 브라우저에서 `http://localhost:8000` (또는 터미널에 표시된 주소)으로 접속합니다.

## 4. 문제 해결 (Troubleshooting)

### 4.1 SyntaxError: no binding for nonlocal 'is_recording' found
**증상**: 녹음 중지 또는 타이머 만료 시 프로그램이 멈추거나 콘솔에 에러가 발생함.
**원인**: 내부 함수 코드에서 변수 `is_recording`의 스코프 설정 문제.
**해결**: `static/py/interview_flow.py` 파일의 수정 패치가 적용되었습니다. (`nonlocal` -> `global`)

### 4.2 웹캠/마이크 접근 불가
브라우저 설정에서 해당 사이트의 카메라 및 마이크 접근 권한을 허용했는지 확인하세요.

### 4.3 카메라 연결 실패 (PyScript 제약 조건 오류)
**증상**: 카메라 권한을 허용했음에도 화면이 나오지 않거나 연결 오류가 발생함.
**원인**: PyScript에서 `to_js`를 사용하여 카메라 제약 조건(constraints)을 전달할 때, JavaScript가 인식하지 못하는 Map 객체로 변환되어 발생.
**해결**: `static/py/interview_flow.py`에서 제약 조건을 JSON 문자열로 변환 후 `JSON.parse`를 통해 순수 JS 객체로 전달하도록 수정됨.

### 4.4 실시간 STT(음성 인식) 기능
**기능**: 면접 답변 시 브라우저 내장(Web Speech API) 기능을 사용하여 음성을 실시간으로 텍스트로 변환해 화면에 표시합니다.
**참고**: 이 기능은 브라우저(특히 Chrome)의 지원 여부에 따라 동작이 달라질 수 있습니다. `interview_flow.py`는 녹음과 동시에 음성 인식을 시작하며, 인식된 텍스트는 `stt-output` 요소에 실시간으로 청크 단위로 표시됩니다.

### 4.5 Uncaught PythonError: TypeError: 'pyodide.ffi.JsProxy' object is not subscriptable
**증상**: 음성 인식 중 "TypeError: 'pyodide.ffi.JsProxy' object is not subscriptable" 에러 발생.
**원인**: Pyodide에서 JavaScript의 `SpeechRecognitionResultList`나 `SpeechRecognitionResult` 객체에 대괄호(`[]`) 인덱싱으로 접근하려 할 때 발생. `JsProxy` 객체는 리스트처럼 직접 인덱싱이 불가능할 수 있음.
**해결**: `interview_flow.py`에서 `event.results[i]` 대신 `event.results.item(i)`를 사용하고, `transcript` 접근 시에도 `.item(0)`을 사용하도록 코드를 수정함.

## 5. 프로젝트 구조 (Project Structure)
- `main.py` / `start_app.py`: 백엔드 서버 진입점
- `db/`: 데이터베이스 관련 파일
- `api/`: REST API 엔드포인트
- `services/`: 비즈니스 로직
- `static/`: 프론트엔드 리소스 (CSS, JS, Python 스크립트)
  - `static/py/interview_flow.py`: 클라이언트 사이드 면접 로직 (PyScript)
- `templates/`: HTML 템플릿
