
## 📊 RAG 시스템 DB 테이블 구조

> 최종 수정일: 2026-02-24

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
| `user_id` | `INTEGER` (FK → `users.id`, ON DELETE CASCADE) | 이력서 소유 사용자 ID |
| `resume_id` | `INTEGER` (FK → `user_resumes.id`, ON DELETE CASCADE) | 이력서 메타데이터 참조 ID |

> ⚠️ `user_id`, `resume_id`는 DB 레벨 FK로, PGVectorStore가 아닌 DB 스키마에서 직접 관리합니다.

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
| `transcript_id` | `INTEGER` (FK → `transcripts.id`, ON DELETE CASCADE) | 면접 대화 기록 참조 ID |

> ⚠️ `transcript_id`는 DB 레벨 FK로, PGVectorStore가 아닌 DB 스키마에서 직접 관리합니다.

**데이터 원본:** `Data/data.json` (6,108개 Q&A → 6,110개 청크)
**생성 주체:** `ResumeRAG(table_name=QA_TABLE).load_and_index_json()`
**인덱싱 API:** `POST /api/qa-data/index` (JWT 인증 필요)

---

### 앱 테이블 1: `users` — 사용자 계정

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

### 앱 테이블 2: `user_resumes` — 이력서 메타데이터

이력서 파일의 메타정보를 영구 저장하여, 서버 재시작/재로그인 시에도 자동 복원합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 이력서 ID |
| `user_id` | Integer (FK → `users.id`, ON DELETE CASCADE) | 소유 사용자 ID |
| `user_email` | String(255), INDEX | 사용자 이메일 (조회용) |
| `filename` | String(500) | 원본 파일명 (예: 홍길동_이력서.pdf) |
| `file_path` | String(1000) | 서버 저장 경로 (uploads/xxx.pdf) |
| `file_size` | Integer | 파일 크기 (bytes) |
| `uploaded_at` | DateTime | 업로드 일시 |
| `is_active` | Integer | 활성 여부 (1=사용 중, 0=삭제됨) |

**생성 주체:** SQLAlchemy `Base.metadata.create_all()`
**업로드 API:** `POST /api/interview/upload-resume`

---

### 앱 테이블 3: `job_postings` — 채용 공고

인사담당자가 작성한 채용 공고 정보를 저장합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 공고 ID |
| `recruiter_email` | String(255) | 작성자(인사담당자) 이메일 |
| `title` | String(200) | 공고 제목 |
| `company` | String(100) | 회사명 |
| `location` | String(200) | 근무지 |
| `job_category` | String(50) | 직무 분야 (backend, frontend 등) |
| `experience_level` | String(30) | 경력 수준 (신입, 1~3년 등) |
| `description` | Text | 상세 내용 (직무 설명, 자격요건 등) |
| `salary_info` | String(100) | 급여 정보 |
| `status` | String(20) | open / closed |
| `created_at` | DateTime | 생성일 |
| `updated_at` | DateTime | 수정일 |
| `deadline` | String(10) | 마감일 (YYYY-MM-DD) |

**생성 주체:** SQLAlchemy `Base.metadata.create_all()`

---

### 앱 테이블 4: `interview_sessions` — 면접 세션

면접 진행 세션을 기록합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 세션 ID |
| `candidate_id` | Integer (FK → `users.id`, ON DELETE CASCADE) | 응시자 ID |
| `job_posting_id` | Integer (FK → `job_postings.id`, ON DELETE SET NULL) | 채용 공고 ID |
| `status` | — | 면접 상태 |
| `created_at` | DateTime | 생성일 |
| `total_score` | — | 총점 |

---

### 앱 테이블 5: `transcripts` — 면접 대화 기록

면접 중 발화 내역을 순서대로 기록합니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 대화 ID |
| `interview_id` | Integer (FK → `interview_sessions.id`, ON DELETE CASCADE) | 면접 세션 ID |
| `speaker` | — | 발화자 (interviewer / candidate) |
| `text` | Text | 발화 내용 |
| `sentiment_score` | — | 감성 점수 |
| `timestamp` | DateTime | 발화 시각 |
| `sequence_number` | Integer | 발화 순서 |

---

### 앱 테이블 6: `evaluation_reports` — 면접 평가 보고서

면접 완료 후 생성되는 종합 평가 보고서입니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | Integer (PK) | 보고서 ID |
| `interview_id` | Integer (FK → `interview_sessions.id`, ON DELETE CASCADE) | 면접 세션 ID |
| `technical_score` | — | 기술 점수 |
| `communication_score` | — | 커뮤니케이션 점수 |
| `cultural_fit_score` | — | 조직 적합도 점수 |
| `problem_solving_socre` | — | 문제 해결 점수 |
| `non_verbal_score` | — | 비언어적 평가 점수 |
| `total_score` | — | 총점 |
| `summary_text` | Text | 평가 요약 |
| `details_json` | JSON | 상세 평가 데이터 |
| `pass_fail_decisions` | — | 합격/불합격 판정 |
| `created_at` | DateTime | 생성일 |

---

### 정리: DB에 존재하는 테이블 (8개)

| 테이블명 | 용도 | 생성 주체 | 현재 Row 수 |
|----------|------|-----------|:-----------:|
| `users` | 사용자 계정 정보 | SQLAlchemy `Base.metadata.create_all()` | 5 |
| `user_resumes` | 이력서 파일 메타데이터 | SQLAlchemy `Base.metadata.create_all()` | 1 |
| `job_postings` | 채용 공고 | SQLAlchemy `Base.metadata.create_all()` | 1 |
| `interview_sessions` | 면접 세션 기록 | DB 스키마 (수동 생성) | 0 |
| `transcripts` | 면접 대화 내역 | DB 스키마 (수동 생성) | 0 |
| `evaluation_reports` | 면접 평가 보고서 | DB 스키마 (수동 생성) | 0 |
| `resume_embeddings` | 이력서 PDF 임베딩 벡터 | `PGVectorStore` V2 (`PGEngine.init_vectorstore_table`) | 20 |
| `qa_embeddings` | 면접 Q&A 참조 임베딩 벡터 | `PGVectorStore` V2 (`PGEngine.init_vectorstore_table`) | 6,110 |

---

### FK 관계도 (Entity Relationship)

```
users (PK: id)
 ├──< user_resumes.user_id          (ON DELETE CASCADE)
 ├──< interview_sessions.candidate_id (ON DELETE CASCADE)
 └──< resume_embeddings.user_id       (ON DELETE CASCADE)

job_postings (PK: id)
 └──< interview_sessions.job_posting_id (ON DELETE SET NULL)

interview_sessions (PK: id)
 ├──< transcripts.interview_id        (ON DELETE CASCADE)
 └──< evaluation_reports.interview_id  (ON DELETE CASCADE)

user_resumes (PK: id)
 └──< resume_embeddings.resume_id      (ON DELETE CASCADE)

transcripts (PK: id)
 └──< qa_embeddings.transcript_id      (ON DELETE CASCADE)
```

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
LLM(EXAONE 3.5 7.8B)이 이력서 컨텍스트 + Q&A 참조를 바탕으로 질문/평가 생성
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