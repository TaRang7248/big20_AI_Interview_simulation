# CURRENT_STATE

이 문서는 AI 코딩 에이전트가 작업을 시작할 때마다 반드시 읽어야 하는 "현재 상태 브리핑"이다.
에이전트는 이 문서를 근거로만 판단하며, 기억/추측으로 프로젝트 방향을 바꾸면 안 된다.

---

## 1. 개발 전략(확정)
- 개발 우선순위: API 기반으로 코어 기능을 빠르게 개발한다.
- 이후 단계: on-prem 모델로 교체/최적화한다.
- 목표: API ↔ on-prem, streaming ↔ batch 를 언제든 교체 가능하도록 추상화한다.

---

## 2. 제품 핵심 기능(확정)
- Playground 탭(정적 파일 업로드 기반)이 최우선이다.
  - 오디오/영상 업로드만으로 STT/감정/시선·자세/목소리 분석 성능을 빠르게 검증한다.
- 실시간 면접 세션은 후순위(Playground가 안정화된 뒤).

---

## 3. 모델 구성(현재 기준)
- STT: Faster-Whisper (GPU VRAM ~1GB)
- LLM: gpt-4o / Qwen3-4B / A.X-4.0-light / EXAONE 7.8B / Llama3.1-KO (GPU VRAM ~4.5GB)
- Emotion: DeepFace (CPU 1fps)
- Visual: MediaPipe (CPU)
- Voice: Parselmouth (CPU)

---

## 4. 저장 정책(확정)
- 서버는 원칙적으로 사용자 영상/오디오 원본을 장기 저장하지 않는다.
- 저장은 분석 결과(요약 지표/점수/텍스트) 위주로 한다.

---

## 5. 폴더/모듈 구조(확정)
- 모든 개발 코드는 IMH/IMH_Interview/ 아래에서만 생성/수정한다.
- 공유 가능한 모듈을 위해 packages/ 중심으로 개발한다.
- apps/ 는 얇게 유지하고, 로직은 packages/ 로 이동한다.

권장 구조:
- apps/api : FastAPI 엔트리(라우터/DI/입출력 변환만)
- packages/imh_core : config/logging/errors/dto (가벼운 의존성)
- packages/imh_providers : Provider 인터페이스 + 구현(API/Local)
- packages/imh_analysis : emotion/visual/voice 분석 파이프라인
- packages/imh_eval : 루브릭/리포트/LLM 평가

---

## 6. 기록/로그 규칙(확정)
- 에이전트가 개발 중 발견하는 에러는 MD가 아니라 진짜 로그(.log)로 남긴다.
  - 로그 위치: IMH/IMH_Interview/logs/agent/*.log 및 logs/runtime/*.log
- docs/DEV_LOG.md 는 사람용 요약 기록(변경 요약/테스트/로그 경로만)이다.

---

## 7. 변경 승인 게이트(필수)
- 에이전트는 "코드 변경 전"에 반드시 변경 제안서(Plan)를 작성하고 사용자 허락을 받아야 한다.
- 허락 전에는 실제 코드/파일 수정 금지.
