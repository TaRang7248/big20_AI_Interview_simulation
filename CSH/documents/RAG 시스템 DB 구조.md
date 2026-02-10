
## 📊 RAG 시스템 DB 테이블 구조

---

### 아키텍처 개요

시스템은 `langchain_postgres` 패키지의 **V2 `PGVectorStore`** + **`PGEngine`** 을 사용합니다.
데이터 유형(이력서 / Q&A)에 따라 **독립된 물리 테이블**에 벡터를 저장하여,
검색 범위가 명확하고 테이블 단위 관리가 가능합니다.

```
resume_rag.py
├── RESUME_TABLE = "resume_embeddings"   ← 이력서 PDF 벡터
├── QA_TABLE     = "qa_embeddings"       ← 면접 Q&A 참조 벡터
│
├── PGEngine.from_connection_string()    ← psycopg3 async 엔진
├── engine.init_vectorstore_table()      ← 테이블 자동 생성
└── PGVectorStore.create_sync()          ← 벡터 CRUD 인터페이스
```

---

### 테이블 1: `resume_embeddings` — 이력서 벡터 저장

사용자가 업로드한 이력서 PDF를 청크 분할 → 임베딩하여 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `langchain_id` | `UUID` (PK) | 문서 청크 고유 ID |
| `content` | `TEXT` | 원본 텍스트 (이력서 청크, `search_document:` 접두사 포함) |
| `embedding` | `Vector(768)` | nomic-embed-text 임베딩 벡터 (768차원) |
| `langchain_metadata` | `JSON` | 메타데이터 (페이지 번호, 소스 파일명 등) |

**데이터 원본:** 사용자 업로드 PDF (`/api/interview/upload-resume`)
**생성 주체:** `ResumeRAG(table_name=RESUME_TABLE).load_and_index_pdf()`

---

### 테이블 2: `qa_embeddings` — 면접 Q&A 참조 벡터 저장

`Data/data.json`의 6,108개 기술면접 Q&A를 임베딩하여 저장합니다.
LLM이 면접 질문 생성 시 모범 답변을 참조하기 위한 용도입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `langchain_id` | `UUID` (PK) | 문서 청크 고유 ID |
| `content` | `TEXT` | "면접 질문: {q}\n모범 답변: {a}" 형태 (`search_document:` 접두사 포함) |
| `embedding` | `Vector(768)` | nomic-embed-text 임베딩 벡터 (768차원) |
| `langchain_metadata` | `JSON` | `{"source": "interview_qa_data", "qa_id": "1", "question": "...", "type": "interview_reference"}` |

**데이터 원본:** `Data/data.json` (6,108개 Q&A → 6,110개 청크)
**생성 주체:** `ResumeRAG(table_name=QA_TABLE).load_and_index_json()`
**인덱싱 API:** `POST /api/qa-data/index` (JWT 인증 필요)

---

### 앱 자체 테이블: `users`

`integrated_interview_server.py`에서 SQLAlchemy로 정의한 사용자 테이블:

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 사용자 ID |
| `email` | String(255), UNIQUE | 이메일 |
| `role` | String(20) | candidate / recruiter |
| `password_hash` | String(255) | bcrypt 해시 |
| `created_at` | DateTime | 생성일 |
| `name` | String(50) | 이름 |
| `birth_date` | String(10) | 생년월일 |
| `gender` | String(10) | 성별 |
| `address` | String(500) | 주소 |
| `phone` | String(20) | 전화번호 |

---

### 정리: DB에 존재하는 테이블

| 테이블명 | 용도 | 생성 주체 |
|----------|------|-----------|
| `users` | 사용자 계정 정보 | SQLAlchemy `Base.metadata.create_all()` |
| `resume_embeddings` | 이력서 PDF 임베딩 벡터 | `PGVectorStore` V2 (`PGEngine.init_vectorstore_table`) |
| `qa_embeddings` | 면접 Q&A 참조 임베딩 벡터 | `PGVectorStore` V2 (`PGEngine.init_vectorstore_table`) |
| `interviews` | 면접 세션 기록 | SQLAlchemy |
| `interview_questions` | 면접 질문 기록 | SQLAlchemy |
| `transcripts` | 면접 대화 내역 | SQLAlchemy |
| `evaluation_reports` | 면접 평가 보고서 | SQLAlchemy |
| `resumes` | 이력서 파일 정보 | SQLAlchemy |

---

### 데이터 흐름

#### 이력서 PDF → `resume_embeddings`

```
이력서 PDF 업로드 (/api/interview/upload-resume)
    ↓
PyPDFLoader → 텍스트 추출
    ↓
RecursiveCharacterTextSplitter → 1500자 청크 (300자 오버랩)
    ↓
"search_document: " 접두사 추가
    ↓
nomic-embed-text (Ollama) → 768차원 벡터 생성
    ↓
┌─────────────────────────────────────────────────────────┐
│ resume_embeddings                                       │
│   langchain_id = uuid-xxx...                            │
│   content = "search_document: 경력사항 3년..."           │
│   embedding = [0.12, -0.34, ...]  (768차원)             │
│   langchain_metadata = {"page": 1, "source": "resume"}  │
└─────────────────────────────────────────────────────────┘
```

#### Q&A JSON → `qa_embeddings`

```
Data/data.json (6,108개 Q&A)
    ↓
POST /api/qa-data/index (JWT 인증)
    ↓
각 항목 → "면접 질문: {q}\n모범 답변: {a}" Document 변환
    ↓
"search_document: " 접두사 추가
    ↓
nomic-embed-text → 768차원 벡터 생성 (배치 100개씩)
    ↓
┌─────────────────────────────────────────────────────────┐
│ qa_embeddings                                           │
│   langchain_id = uuid-yyy...                            │
│   content = "search_document: 면접 질문: CNN이란?..."    │
│   embedding = [0.45, 0.67, ...]  (768차원)              │
│   langchain_metadata = {"source": "interview_qa_data",  │
│     "qa_id": "42", "question": "CNN이란?",              │
│     "type": "interview_reference"}                      │
└─────────────────────────────────────────────────────────┘
```

#### 면접 중 검색 흐름

```
면접 중 사용자 답변 수신
    ↓
┌─ 1. 이력서 검색 ─────────────────────────────────┐
│  ResumeRAG(table_name=RESUME_TABLE)              │
│  → resume_embeddings에서 MMR 검색                 │
│  → 이력서 기반 맞춤 후속질문 생성                   │
└──────────────────────────────────────────────────┘
    ↓
┌─ 2. Q&A 참조 검색 ───────────────────────────────┐
│  ResumeRAG(table_name=QA_TABLE)                  │
│  → qa_embeddings에서 유사도 검색 (k=2)            │
│  → 모범 답변을 참고하여 평가 정확도 향상             │
└──────────────────────────────────────────────────┘
    ↓
LLM(Qwen3)이 이력서 컨텍스트 + Q&A 참조를 바탕으로 질문/평가 생성
```
---

### ResumeRAG 클래스 사용법

```python
from resume_rag import ResumeRAG, RESUME_TABLE, QA_TABLE

# 이력서 벡터 저장/검색
resume_rag = ResumeRAG(table_name=RESUME_TABLE)
resume_rag.load_and_index_pdf("path/to/resume.pdf")
results = resume_rag.similarity_search("Python 개발 경험")

# Q&A 참조 데이터 저장/검색
qa_rag = ResumeRAG(table_name=QA_TABLE)
qa_rag.load_and_index_json("Data/data.json")
results = qa_rag.similarity_search("딥러닝 CNN")

# 테이블 초기화 (전체 데이터 삭제)
qa_rag.clear_table()
```

**생성자 시그니처:** `ResumeRAG(table_name: str, connection_string: str = None)`
- `table_name`: 필수 — `RESUME_TABLE` 또는 `QA_TABLE` 사용
- `connection_string`: 선택 — 미지정 시 `POSTGRES_CONNECTION_STRING` 환경변수 사용