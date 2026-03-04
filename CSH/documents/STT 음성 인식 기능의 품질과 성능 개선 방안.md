

---

## 오인식 원인 분석

### 1. 오디오 입력 품질 문제 (가장 큰 원인)

**`getUserMedia`에 오디오 제약 조건이 없습니다** ([page.tsx L437](CSH/frontend/src/app/interview/page.tsx#L437)):

```tsx
// 현재 — 브라우저 기본값에 의존
await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
```

`echoCancellation`, `noiseSuppression`, `autoGainControl` 등을 명시하지 않아 브라우저 기본 동작에 의존합니다. 특히:
- **에코 캔슬 미보장**: TTS가 스피커로 재생될 때 마이크가 이를 다시 수음 → Deepgram이 TTS 음성을 사용자 발화로 인식
- **노이즈 억제 미보장**: 배경 소음이 발화와 혼합되면 유사 발음("비즈니스" ↔ "피트니스")을 혼동

### 2. 리샘플링 품질 문제

**프론트엔드 `toPcm16k()`** ([page.tsx L251](CSH/frontend/src/app/interview/page.tsx#L251))와 **서버 `_convert_frame_to_pcm16_mono_16k()`** ([integrated_interview_server.py L7188](CSH/integrated_interview_server.py#L7188)) 모두 **선형 보간(linear interpolation)**으로 리샘플링합니다.

브라우저 오디오 sampleRate는 보통 **44100Hz 또는 48000Hz** → 16000Hz로 다운샘플링할 때 선형 보간은 고주파 성분을 제대로 필터링하지 못해 **앨리어싱(aliasing)** 이 발생합니다. 이것이 자음 구별력을 떨어뜨리는 핵심 요인입니다 (ㅂ/ㅍ, ㅈ/ㅊ 같은 고주파 자음).

### 3. Deepgram 키워드 부스팅 미사용

현재 Deepgram 연결 설정에 **`keywords` 파라미터**가 없습니다. 면접 맥락에서 자주 등장하는 용어(비즈니스, 프로젝트, 아키텍처 등)를 부스팅하면 인식 정확도가 크게 향상됩니다.

### 4. ScriptProcessorNode (deprecated API)

page.tsx: `createScriptProcessor(4096, 1, 1)` — Web Audio API에서 **deprecated**된 노드입니다. 메인 스레드에서 오디오 처리가 이뤄져 프레임 드롭이 발생할 수 있고, 이로 인해 음성 일부가 누락됩니다.

---

## 개선 방안

<Thinking>
수정 계획:

1. **getUserMedia 오디오 제약 조건 강화** (page.tsx)
   - echoCancellation, noiseSuppression, autoGainControl, sampleRate 명시

2. **Deepgram keywords 부스팅** (integrated_interview_server.py)
   - 면접 도메인 키워드 + 세션별 질문 키워드를 Deepgram에 전달

3. **프론트엔드 리샘플링 개선** (page.tsx)
   - 저역 통과 필터(LPF) 적용 후 다운샘플링으로 앨리어싱 방지

수정 파일: 2개
- page.tsx (getUserMedia + 리샘플링)
- integrated_interview_server.py (keywords 부스팅)

부작용: 없음 (기존 동작을 관여하지 않는 품질 개선)
테스트: 빌드 검증 + 구문 검증
</Thinking>

수정할 파일 2개, 예상 변경 3건입니다:

| 파일 | 변경 | 부작용 |
|------|------|--------|
| page.tsx | getUserMedia 오디오 제약 조건 + 앨리어싱 방지 LPF 리샘플링 | 없음 |
| integrated_interview_server.py | Deepgram keywords 부스팅 (면접 도메인 용어) | 없음 |

진행할까요?