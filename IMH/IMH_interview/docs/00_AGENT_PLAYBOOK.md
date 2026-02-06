# 00_AGENT_PLAYBOOK (공유 모듈 중심 / API 우선 → on-prem 교체)

본 문서는 AI 코딩 에이전트가 IMH 면접 시스템을 개발할 때 따라야 할 운영 규칙 + 개발 계획 + 실행 계획이다.
목표는 "API 기반으로 코어를 빠르게 완성"한 뒤, "on-prem 모델로 교체/최적화" 하는 것이다.
또한 팀원들과 기능 모듈을 공유하기 쉽게, 핵심 기능을 재사용 가능한 패키지 단위로 설계한다.

---

## 0) 절대 규칙 (변경 승인 게이트)

### 0.1 코드 변경 전 승인 프로토콜 (필수)
에이전트는 아래 순서를 지키지 않으면 코드를 수정하면 안 된다.

1) 변경 제안서(Plan Only) 작성
- 어떤 파일을
- 왜 바꾸는지
- 무엇을 추가/변경/삭제하는지
- 영향 범위(API/DB/테스트/마이그레이션/환경)
- 롤백 방법(되돌리기)

2) 사용자(프로젝트 오너)의 "허락"을 받은 뒤에만 실제 코드 변경 수행

3) 변경 후 반드시 기록
- docs/DEV_LOG.md (변경 요약 / 테스트 / 다음 할 일)

> 사용자의 "허락" 전에는 실제 코드 변경/커밋/대규모 diff 출력 금지.
> 계획서까지만 작성한다.

### 0.2 Python 코드 품질 규칙
- 함수/클래스: 타입힌트 + docstring 필수 (Google Style 권장)
- 예외 처리: 의미 있는 커스텀 예외 계층 사용 (핵심 패키지에서 통일)
- 모듈 경계: app(FastAPI)는 얇게, core는 packages에

### 0.3 로그 규칙 (MD가 아닌 진짜 로그파일)
- 에이전트가 개발/테스트/실행 중 발견하는 에러는 MD가 아닌 로그파일(.log)에 남긴다.
- 스택트레이스 포함을 위해 logger.exception()을 사용한다.
- 로그 파일 위치: IMH/IMH_Interview/logs/ 하위
- docs/DEV_LOG.md에는 "요약 + 로그 경로"만 남긴다.

---

## 1) 최상위 폴더 구조 (공유 모듈 최적화)

모든 개발 코드는 IMH/IMH_Interview/ 아래에서만 생성/수정한다.
참고문서는 코드와 분리해 혼동을 방지한다.

IMH/IMH_Interview/
├─ apps/                          # 실행 가능한 앱(얇게 유지)
│  ├─ api/                         # FastAPI (면접/플레이그라운드)
│  └─ worker/                      # (선택) 배치/비동기 작업 실행 엔트리
│
├─ packages/                      # 팀 공유가 쉬운 재사용 패키지들(핵심)
│  ├─ imh_core/                    # 공통: 설정, 로깅, 예외, DTO, 유틸
│  ├─ imh_providers/               # Provider 추상화 + 구현(API/Local)
│  ├─ imh_analysis/                # emotion/visual/voice 분석 파이프라인
│  └─ imh_eval/                    # 루브릭/스코어링/리포트 생성(LLM 포함)
│
├─ web/                           # (선택) 프론트/대시보드(Playground UI)
│
├─ docs/                          # 산출 문서(사람이 읽는 것)
│  ├─ 00_AGENT_PLAYBOOK.md
│  └─ DEV_LOG.md
│
├─ logs/                          # 진짜 로그파일
│  ├─ agent/                       # 에이전트/개발/테스트 로그
│  └─ runtime/                     # 서버 런타임 로그
│
├─ _refs/                         # 참고/원문 문서(UI 초안, 스펙, 슬라이드, docx 등)
└─ scripts/                       # 로컬 실행/테스트/도구 스크립트

### 1.1 _refs 폴더명 추천 (확정)
- IMH/IMH_Interview/_refs/
  - 이유: docs(산출물)과 refs(참고 원문) 분리로 에이전트 혼동 방지

---

## 2) 공유 가능한 모듈 설계 원칙 (팀 공유/재사용)

### 2.1 패키지 경계
- apps/api: 라우터/DI/요청응답 변환만 담당 (얇게)
- packages/*: 재사용 가능한 순수 파이썬 모듈로 구성 (공유 핵심)

### 2.2 공유 방식 (Git/팀 개발 최적)
- packages/* 는 독립적으로도 동작 가능하게 설계한다.
- 향후 공유 방법:
  - (A) 같은 레포 내에서 import
  - (B) packages/를 별도 레포로 떼거나, git subtree/submodule로 분리 가능
  - (C) 내부 PyPI/패키지 배포도 가능하도록 구조 유지

### 2.3 외부 의존성 최소화
- packages/imh_core 는 가장 가벼운 의존성만 허용 (FastAPI 같은 웹 프레임워크 금지)
- providers/analysis/eval 은 필요 라이브러리 의존 가능하나, 인터페이스는 core에 둔다.

---

## 3) Provider 추상화 (API ↔ on-prem 교체 가능)

### 3.1 공통 인터페이스 (Protocol/ABC)
각 분석 항목은 "인터페이스" + "구현체(API/Local)" 로 나눈다.

- STTProvider
  - transcribe_file(audio_path) -> Transcript
  - transcribe_stream(chunks) -> TranscriptStream
- LLMProvider
  - generate(messages, options) -> LLMResponse
  - generate_stream(messages, options) -> AsyncIterator[Token]
- EmotionProvider
  - analyze_video(video_path, fps=1) -> EmotionSeries + Summary
- VisualProvider
  - analyze_video(video_path, fps=1) -> GazePostureSummary
- VoiceProvider
  - analyze_audio(audio_path) -> VoiceMetrics

### 3.2 Streaming 토글(토큰 비용/지연 최적화)
LLM 입력 전달 방식은 런타임 설정으로 토글한다.
- MODE_STREAM: 실시간 토큰/부분 STT를 LLM에 전달
- MODE_BATCH: 응답 완료 후 한 번에 전달(토큰 절약/비용 예측 용이)

설정은 DB 스키마 변경 없이도 바뀌어야 한다.

---

## 4) Playground (정적 파일 업로드로 빠른 성능 확인)

### 4.1 목적
- 실시간 면접 세션 없이도 모델 성능을 빠르게 교체/비교
- 오디오/비디오 파일 업로드로 즉시 결과 확인

### 4.2 Playground API 최소 엔드포인트(초안)
- POST /playground/stt        (audio) -> transcript
- POST /playground/emotion    (video) -> emotion series + summary
- POST /playground/visual     (video) -> gaze/posture summary
- POST /playground/voice      (audio) -> voice metrics
- POST /playground/run        (audio/video + options) -> combined report

반드시 옵션 포함:
- provider 선택(api/local)
- stream_mode 선택(stream/batch)
- fps, 샘플링 설정
- 결과 저장 여부(store=true/false)

---

## 5) 개발 계획 (공유 모듈 기반 로드맵)

### Phase 0: 운영/기록/로그 체계 고정 (가장 먼저)
- [ ] docs/DEV_LOG.md 생성 (사람용 요약 기록)
- [ ] logs/agent/, logs/runtime/ 생성
- [ ] packages/imh_core/logging.py: RotatingFileHandler 기반 로거 구축
- [ ] 에러는 무조건 logs/*.log에 남기고, DEV_LOG에는 요약 + 경로만 남김

### Phase 1: Core 패키지(imh_core) 먼저 완성
- [ ] imh_core/config: 환경설정(Provider 선택, stream_mode, fps 등)
- [ ] imh_core/errors: 커스텀 예외 계층
- [ ] imh_core/dto: Transcript, EmotionSeries 등 공통 데이터 모델
- [ ] imh_core/logging: 로거 유틸

### Phase 2: Provider 패키지(imh_providers)
- [ ] 인터페이스 정의 + 더미(Mock) 구현으로 테스트 가능 상태
- [ ] API 기반 LLM Provider (OpenAI 등)
- [ ] Local Provider는 스텁(껍데기)만 먼저, 나중에 on-prem 채움

### Phase 3: Analysis 패키지(imh_analysis)
- [ ] DeepFace Emotion 분석(파일 기반)
- [ ] MediaPipe Visual 분석(파일 기반)
- [ ] Parselmouth Voice 분석(파일 기반)

### Phase 4: apps/api (FastAPI) 연결
- [ ] /playground/stt 부터 end-to-end 성공
- [ ] /playground/run 통합 리포트까지 확장
- [ ] 서버는 원칙적으로 영상 저장 안 함(필요 시 결과만 저장)

### Phase 5: 면접 세션 연동(후순위)
- [ ] 텍스트 기반 면접 세션 → 동일 DTO/리포트 파이프라인 재사용
- [ ] 실시간/배치 토글을 실제 면접 플로우에 적용

---

## 6) 실행 계획 (에이전트 프롬프트 템플릿)

### 6.1 작업 시작 프롬프트 (허락 전: 계획만)
너는 IMH 프로젝트의 AI 코딩 에이전트다.
- 변경 전에는 반드시 "변경 제안서"를 먼저 작성하고 사용자 허락을 받아라.
- 모든 코드는 IMH/IMH_Interview/ 아래에서만 작성하라.
- packages/ 중심으로 공유 가능한 모듈로 설계하라.
- 에러는 logs/*.log에 남기고, docs/DEV_LOG.md에는 요약+경로만 남겨라.

현재 작업: <사용자가 지시한 작업 1개>

출력 형식:
1) 변경 제안서(파일/이유/내용/영향/롤백)
2) 사용자 허락 요청

### 6.2 허락 후 구현 프롬프트
사용자가 허락했다.
- 제안서대로 구현하라.
- 구현 후 반드시:
  - logs에 에러가 남도록 로깅 설정 점검
  - docs/DEV_LOG.md에 변경 요약/테스트 방법/다음 작업 기록

출력 형식:
1) 변경 요약
2) 생성/수정 파일 목록
3) 로컬 테스트 방법(curl 예시 포함)
4) DEV_LOG 업데이트 내용 요약
5) 다음 작업 제안 1~2개

---

## 7) DEV_LOG 기록 규칙 (사람용)

DEV_LOG에는 "정리된 내용"만 남긴다.
- 변경 사항(무엇을 왜 했는지)
- 테스트 방법/결과
