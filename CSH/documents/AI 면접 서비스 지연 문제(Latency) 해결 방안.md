
현재 시스템의 전체 파이프라인을 분석한 결과를 바탕으로 지연 최적화 방안을 제안합니다.

---

## 현재 시스템 지연 구조 분석

| 단계 | 현재 상태 | 예상 지연 |
|------|-----------|-----------|
| **STT** | Google Web Speech API (브라우저) | ~0.5-1s (네트워크 의존) |
| **RAG 검색** | nomic-embed-text + pgvector, Redis 캐시 | 캐시 히트: ~10ms / 미스: ~1-3s |
| **LLM 추론** | exaone3.5:7.8b, GTX 1660 6GB, num_ctx=8192 | **~15-24s** ← **최대 병목** |
| **한국어 가드** | 실패 시 최대 2회 재생성 | 0 ~ **+48s** (worst case) |
| **TTS** | Hume AI Octave 2 (API) | ~1-2s |
| **SLA 목표** | 1.5초 이내 | **현재 달성 불가** |

---

## 최적화 제안 (우선순위 순)

### 1. LLM 모델 경량화 (효과: ★★★★★)
**가장 큰 병목**인 LLM 추론 시간을 줄이는 가장 직접적인 방법입니다.

| 옵션 | 파라미터 | 예상 효과 |
|------|----------|-----------|
| **A. 더 작은 모델 사용** | `exaone3.5:2.4b` 또는 `gemma2:2b` | 추론 시간 3-5배 감소 (5-8s → **3-5s**) |
| **B. 양자화 모델** | `exaone3.5:7.8b-q4_0` | 20-30% 속도 향상, VRAM 절약 |
| **C. 클라우드 LLM API** | GPT-4o-mini, Claude Haiku 등 | **1-3s**로 단축, 비용 발생 |

```python
# 예시: 환경변수로 모델 전환
# .env
LLM_MODEL=exaone3.5:2.4b   # 7.8b → 2.4b로 변경
```

### 2. `num_ctx` 축소 (효과: ★★★★☆)
현재 `num_ctx=8192`는 GTX 1660 VRAM 대비 과도합니다. VRAM 사용량이 줄면 추론 속도가 직접적으로 향상됩니다.

```python
# 현재: num_ctx=8192 (VRAM 약 5-6GB 사용)
# 권장: num_ctx=4096 (VRAM 약 3-4GB → 추론 속도 30-50% 향상)
LLM_NUM_CTX=4096
```

대화 히스토리는 이미 최근 5턴(`MAX_HIST=10`)으로 제한되어 있으므로, 4096으로도 RAG 컨텍스트 + 프롬프트 + 히스토리 수용이 충분합니다.

### 3. `num_predict` 제한 (효과: ★★★☆☆)
현재 `num_predict` 미설정(-1)으로 모델이 stop 토큰까지 무한 생성합니다. 면접 질문은 보통 50-150 토큰이므로 상한을 설정하면 불필요한 생성을 방지할 수 있습니다.

```python
self.question_llm = ChatOllama(
    model=DEFAULT_LLM_MODEL,
    temperature=DEFAULT_LLM_TEMPERATURE,
    num_ctx=DEFAULT_LLM_NUM_CTX,
    num_predict=256,  # ★ 최대 256토큰으로 제한 → 불필요한 장문 생성 방지
)
```

### 4. 한국어 가드 재생성 최소화 (효과: ★★★☆☆)
현재 한국어 비율이 낮으면 **최대 2회 재생성**하는데, 이것이 지연을 2-3배로 증폭시킵니다.

| 방안 | 설명 |
|------|------|
| **A. 재생성 횟수 줄이기** | `LLM_KOREAN_MAX_RETRIES=1` (2→1) |
| **B. 비율 기준 완화** | `LLM_KOREAN_MIN_RATIO=0.5` (0.6→0.5) |
| **C. 프롬프트 강화** | 재생성 대신 프롬프트에 한국어 강제 지시를 더 강화 |

### 5. RAG 검색과 프롬프트 조립 병렬화 (효과: ★★☆☆☆)
현재 SSE 스트리밍 내에서 resume RAG와 Q&A RAG가 순차 실행됩니다. 이를 `asyncio.gather`로 병렬화하면 1-2초 절약 가능합니다.

```python
# Before (순차)
resume_docs = await run_rag_async(retriever, query)
qa_docs = await run_rag_async(qa_retriever, query)

# After (병렬)
resume_docs, qa_docs = await asyncio.gather(
    run_rag_async(retriever, query),
    run_rag_async(qa_retriever, query),
)
```

### 6. SSE 스트리밍 최적화 — 이미 구현됨 (효과: ★★★★☆)
`ChatOllama.astream()` + SSE 토큰 스트리밍이 이미 구현되어 있어 **체감 지연**은 크게 완화되고 있습니다. 첫 토큰이 나오기까지의 시간(TTFT)만 줄이면 됩니다.

### 7. Ollama GPU 레이어 설정 (효과: ★★☆☆☆)
Ollama는 기본적으로 모델의 일부 레이어만 GPU에 로드합니다. 수동으로 전체 레이어를 GPU에 올리면 추론이 빨라집니다.

```bash
# 환경변수로 GPU 레이어 수 강제 설정
set OLLAMA_NUM_GPU=999   # 가능한 모든 레이어를 GPU에 로드
ollama serve
```

단, GTX 1660 6GB에서 7.8B 모델 전체를 GPU에 올리면 OOM이 발생할 수 있으므로 **2.4B 모델과 조합**하는 것이 안전합니다.

### 8. TTS 지연 최적화 (효과: ★★☆☆☆)
현재 Hume AI 크레딧이 소진되어 Web Speech API 폴백을 사용 중인데, 이 경우 TTS 지연은 거의 없습니다 (로컬 처리). Hume AI 복구 후에는:

| 방안 | 설명 |
|------|------|
| **선 스트리밍** | LLM 첫 문장이 완성되면 TTS를 즉시 시작 (전체 응답 대기 X) |
| **TTS 캐싱** | 자주 사용하는 인삿말/마무리 멘트를 미리 합성하여 캐싱 |

---

## 종합 권장 조합 (즉시 적용 가능)

환경변수만 변경하면 서버 재시작으로 **코드 수정 없이** 적용 가능한 조합입니다:

```env
# .env 또는 환경변수
LLM_MODEL=exaone3.5:2.4b       # 모델 경량화 (7.8b → 2.4b)
LLM_NUM_CTX=4096                # 컨텍스트 축소 (8192 → 4096)
LLM_KOREAN_MAX_RETRIES=1        # 재생성 횟수 축소 (2 → 1)
LLM_TIMEOUT_SEC=30              # 타임아웃 단축 (60 → 30)
```

**예상 효과**: 현재 15-24s → **3-8s** (환경변수만 변경 시)

`num_predict` 추가와 RAG 병렬화까지 코드 수정하면 추가로 1-2s 더 절약 가능합니다. 어떤 방안을 적용할지 알려주시면 바로 구현하겠습니다.