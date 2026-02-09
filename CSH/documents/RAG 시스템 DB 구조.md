
## 📊 RAG 시스템 DB 테이블 구조

시스템에서 사용하는 `langchain_postgres`의 `PGVector` (V1)은 초기화 시 **2개의 테이블**을 PostgreSQL에 자동 생성합니다.

---

### 테이블 1: `langchain_pg_collection` — 컬렉션 관리

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `uuid` | `UUID` (PK) | 컬렉션 고유 ID |
| `name` | `String` (UNIQUE, NOT NULL) | 컬렉션 이름 |
| `cmetadata` | `JSON` | 컬렉션 메타데이터 |

resume_rag.py에서 `collection_name` 파라미터로 전달하는 값이 이 테이블의 `name` 컬럼에 저장됩니다.

**실제 저장되는 컬렉션 이름 예시:**
- 기본값: `"resume_vectors"` (ResumeRAG 클래스 기본 파라미터)
- 서버에서 실제 사용: `"resume_{session_id[:16]}"` — integrated_interview_server.py에서 세션별로 고유한 컬렉션 생성

---

### 테이블 2: `langchain_pg_embedding` — 임베딩 벡터 저장 (RAG 핵심)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | `String` (PK) | 문서 청크 ID |
| `collection_id` | `UUID` (FK → `langchain_pg_collection.uuid`) | 소속 컬렉션 |
| `embedding` | `Vector(768)` | nomic-embed-text 임베딩 벡터 (768차원) |
| `document` | `String` | 원본 텍스트 (이력서 청크 내용) |
| `cmetadata` | `JSONB` | 메타데이터 (페이지 번호, 출처 등) |

- `cmetadata` 컬럼에 GIN 인덱스(`jsonb_path_ops`) 자동 생성
- **모든 세션의 임베딩이 이 하나의 테이블**에 저장되며, `collection_id` FK로 구분됩니다

---

### 데이터 흐름 요약

```
이력서 PDF 업로드
    ↓
PyPDFLoader → 텍스트 추출
    ↓
RecursiveCharacterTextSplitter → 1500자 청크 (300자 오버랩)
    ↓
"search_document: " 접두사 추가
    ↓
nomic-embed-text → 768차원 벡터 생성
    ↓
┌─────────────────────────────────────────────────────────┐
│ langchain_pg_collection                                 │
│   name = "resume_{session_id[:16]}"                     │
│   uuid = abc-123...                                     │
├─────────────────────────────────────────────────────────┤
│ langchain_pg_embedding                                  │
│   collection_id = abc-123...  (FK)                      │
│   embedding = [0.12, -0.34, ...]  (768차원)             │
│   document = "search_document: 이력서 텍스트 청크..."    │
│   cmetadata = {"page": 1, "source": "resume.pdf"}       │
└─────────────────────────────────────────────────────────┘
```

### 앱 자체 테이블 (`users`)

RAG 외에 integrated_interview_server.py에서 SQLAlchemy로 정의한 **`users`** 테이블도 있습니다:

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

---

### 정리: DB에 존재하는 테이블 총 3개

| 테이블명 | 용도 | 생성 주체 |
|----------|------|-----------|
| `users` | 사용자 계정 정보 | SQLAlchemy `Base.metadata.create_all()` |
| `langchain_pg_collection` | RAG 컬렉션(세션) 관리 | `langchain_postgres` PGVector 자동 생성 |
| `langchain_pg_embedding` | 이력서 임베딩 벡터 저장 | `langchain_postgres` PGVector 자동 생성 |



## RAG 컬렉션이란?

### 쉬운 비유: 도서관의 서가(書架)

도서관에 수천 권의 책이 있다고 생각하세요.

- **모든 책을 한 더미에 쌓으면** → 원하는 책을 찾기 어렵고, 누구의 책인지도 구분 불가
- **서가별로 분류해두면** → "A번 서가 = 김철수의 이력서", "B번 서가 = 이영희의 이력서"처럼 빠르게 접근 가능

**컬렉션 = 서가**, **임베딩 벡터(청크) = 책** 입니다.

---

### 시스템에서의 실제 동작

사용자 A와 사용자 B가 각각 이력서를 업로드하면:

```
사용자 A 세션: abc123def456...
  → collection_name = "resume_abc123def456"
  → 이력서가 10개 청크로 쪼개져 저장됨

사용자 B 세션: xyz789uvw012...
  → collection_name = "resume_xyz789uvw012"
  → 이력서가 8개 청크로 쪼개져 저장됨
```

이 18개 청크는 **모두 `langchain_pg_embedding` 하나의 테이블**에 들어갑니다. 그런데 면접 중 사용자 A가 질문을 받으면, **A의 이력서에서만** 관련 내용을 찾아야 하지 B의 이력서에서 찾으면 안 됩니다.

---

### `langchain_pg_collection` 테이블이 필요한 이유

| 없으면 | 있으면 |
|--------|--------|
| 18개 청크가 뒤섞여 있음 | 컬렉션 ID로 구분됨 |
| 검색 시 A+B 이력서 전체에서 검색 | A의 컬렉션에서만 검색 |
| 삭제 시 전체를 날려야 함 | A의 컬렉션만 삭제 가능 |

**구조를 보면:**

```
langchain_pg_collection (서가 목록)
┌──────────────────────┬───────────────────────┐
│ uuid                 │ name                  │
├──────────────────────┼───────────────────────┤
│ aaa-111-...          │ resume_abc123def456   │  ← 사용자 A
│ bbb-222-...          │ resume_xyz789uvw012   │  ← 사용자 B
└──────────────────────┴───────────────────────┘
         ↕ FK 연결
langchain_pg_embedding (실제 데이터)
┌────┬───────────────┬───────────────────────┬──────────────────┐
│ id │ collection_id │ document              │ embedding        │
├────┼───────────────┼───────────────────────┼──────────────────┤
│ 1  │ aaa-111-...   │ "경력: 삼성전자..."    │ [0.12, -0.34...] │
│ 2  │ aaa-111-...   │ "학력: 서울대..."      │ [0.45, 0.67...]  │
│ 3  │ bbb-222-...   │ "경력: LG전자..."      │ [0.23, -0.11...] │
└────┴───────────────┴───────────────────────┴──────────────────┘
```

사용자 A가 면접 중 질문을 받으면:
1. `collection_name = "resume_abc123def456"` → `langchain_pg_collection`에서 `uuid = aaa-111` 조회
2. `langchain_pg_embedding`에서 `collection_id = aaa-111`인 것만 필터링하여 벡터 유사도 검색
3. → **A의 이력서 내용만** 정확하게 검색됨

---

### 핵심 정리

| 개념 | 역할 |
|------|------|
| **컬렉션** | "이 임베딩 데이터는 누구의 것인가"를 구분하는 **논리적 그룹** |
| **`langchain_pg_collection` 테이블** | 컬렉션의 이름과 UUID를 관리하는 **인덱스 테이블** |
| **`langchain_pg_embedding` 테이블** | 실제 텍스트 청크와 벡터가 저장되는 **데이터 테이블** |

컬렉션 테이블이 없으면 모든 사용자의 이력서 데이터가 구분 없이 섞이게 되어, **세션별 격리된 검색이 불가능**합니다. 이 시스템에서는 integrated_interview_server.py에서 `resume_{session_id[:16]}` 형식으로 세션마다 고유한 컬렉션을 만들어 이를 해결하고 있습니다.