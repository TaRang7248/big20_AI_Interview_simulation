# 7. 보안 설계 및 구현

본 장에서는 AI 모의면접 시뮬레이션 시스템에 적용된 보안 설계의 전체 구조와 구현 세부사항을 계층적으로 기술한다. 보안 설계는 2장의 비기능적 요구사항 REQ-N-003(암호화), REQ-N-004(GDPR 개인정보 보호)을 직접적으로 실현하며, 인증·인가(Authentication & Authorization), 데이터 암호화(Data Encryption), API 보안(API Security), 코드 실행 보안(Code Execution Security), 개인정보 보호(Privacy Protection)의 5개 보안 영역으로 구분하여 다층적 방어(Defense in Depth) 전략을 수립하였다. 본 시스템의 보안 구현은 security.py 단일 모듈(598줄)에 핵심 기능이 집중되어 있으며, NGINX 설정과 Docker 컨테이너 격리가 인프라 수준의 보안 경계를 형성한다.

---

## 7.1 인증·인가 (bcrypt, JWT HS256, 소셜 로그인)

### 7.1.1 비밀번호 해싱 — bcrypt (rounds=12)

사용자 비밀번호의 저장 시 보호는 bcrypt 단방향 해시 알고리즘을 통해 구현된다. security.py의 hash_password() 함수는 bcrypt.gensalt(rounds=12)로 솔트(Salt)를 생성하고 bcrypt.hashpw()로 해싱을 수행한다.

bcrypt의 work factor를 rounds=12로 설정한 이유는 다음과 같다. bcrypt는 의도적으로 느린(Intentionally Slow) 해시 알고리즘으로, rounds 값이 1 증가할 때마다 계산 비용이 2배로 증가한다. rounds=12는 일반적인 서버 하드웨어에서 해시 생성에 약 250~300ms가 소요되는 수준으로, 사용자 경험을 저해하지 않으면서도 무차별 대입 공격(Brute-force Attack)에 대한 충분한 계산 비용을 부과한다. OWASP Password Storage Cheat Sheet에서 권장하는 최소 work factor 10을 상회하는 설정이다.

비밀번호 검증은 verify_password() 함수가 담당한다. 이 함수는 bcrypt 해시($2b$ 또는 $2a$ 접두사)와 레거시 SHA-256 해시의 두 형식을 모두 지원하는 하위 호환(Backward Compatibility) 설계가 적용되어 있다. SHA-256 해시가 감지되면 로그인은 허용하되, 재해싱(Rehash) 필요 플래그가 기록되어 다음 로그인 시 bcrypt로 자동 마이그레이션이 수행된다. needs_rehash() 함수가 기존 해시가 SHA-256 형식인지를 판별하여, 마이그레이션 대상 계정을 식별한다.

이 점진적 마이그레이션(Gradual Migration) 전략은 기존 사용자의 비밀번호를 일괄 재해싱하지 않으면서도, 시간이 지남에 따라 모든 사용자의 비밀번호가 자연스럽게 bcrypt로 전환되는 무중단 보안 강화 방식이다.

### 7.1.2 JWT 액세스 토큰 — HS256 (120분)

인증된 사용자의 세션 관리는 JWT(JSON Web Token)를 통해 구현된다. create_access_token() 함수는 사용자 정보(sub: 이메일, name, role, user_id)를 포함하는 페이로드를 생성하고, HS256(HMAC-SHA256) 알고리즘으로 서명한다.

JWT 구성 요소는 다음과 같다. 페이로드에는 sub(사용자 이메일, 주 식별자), name(사용자 이름), role(역할: candidate 또는 recruiter), user_id(사용자 고유 ID), exp(만료 시각, UTC), iat(발급 시각, UTC), type("access")이 포함된다.

토큰 유효 기간은 JWT_ACCESS_TOKEN_EXPIRE_MINUTES 환경변수를 통해 설정되며 기본값은 120분(2시간)이다. 면접 세션의 최대 지속 시간(120분)과 동일하게 설정하여, 면접 도중 토큰이 만료되는 상황을 방지한다.

서명 키(JWT_SECRET_KEY)는 환경변수에서 로드되며, 키가 설정되지 않은 경우 RuntimeError를 발생시켜 애플리케이션 기동 자체를 차단한다. 이 강제 실패(Fail-fast) 설계는 보안 키 없이 시스템이 운영되는 것을 원천적으로 방지한다.

decode_access_token() 함수는 토큰의 서명 검증과 만료 시간 확인을 수행하며, 검증 실패 시 None을 반환한다. python-jose 라이브러리의 JWTError 예외를 캐치하여, 변조된 토큰, 만료된 토큰, 형식 오류 토큰 등 모든 유형의 무효 토큰에 대한 거부가 보장된다.

### 7.1.3 FastAPI 인증 미들웨어 — Depends 패턴

인증된 사용자만 접근할 수 있는 API 엔드포인트의 보호는 FastAPI의 Depends() 의존성 주입 패턴을 통해 구현된다. security.py에는 두 가지 인증 의존성이 정의되어 있다.

get_current_user()는 필수적 인증(Mandatory Authentication) 의존성이다. Authorization: Bearer {token} 헤더에서 JWT를 추출하고 검증하며, 토큰이 없거나 유효하지 않은 경우 HTTP 401 Unauthorized를 반환한다. 응답에는 WWW-Authenticate: Bearer 헤더가 포함되어 OAuth 2.0 표준을 준수한다. 검증 성공 시 사용자 정보 딕셔너리(email, name, role, user_id)를 반환한다.

get_current_user_optional()은 선택적 인증(Optional Authentication) 의존성이다. 토큰이 있으면 사용자 정보를 반환하고, 없거나 유효하지 않으면 None을 반환한다. 공개 API이면서도 로그인 시 추가 기능을 제공하는 엔드포인트(예: 채용공고 조회 — 비로그인 시 목록만, 로그인 시 지원 기능 추가)에서 활용된다.

HTTPBearer 스킴은 auto_error=False로 설정되어, 토큰이 없는 요청에 대해 자동 거부 대신 None을 반환함으로써 선택적 인증 패턴의 구현을 가능케 한다.

### 7.1.4 소셜 로그인 (OAuth 2.0)

카카오, 구글, 네이버의 세 OAuth 2.0 프로바이더를 통한 소셜 로그인이 지원된다. OAuth 2.0 Authorization Code Flow를 준수하며, 각 프로바이더의 인증 서버로 리다이렉트 → 인가 코드 수신 → 액세스 토큰 교환 → 사용자 정보 조회의 표준 흐름을 따른다. 소셜 로그인으로 최초 가입한 사용자에 대해서는 비밀번호 없이 계정이 생성되며, 소셜 프로바이더 프로필에서 이메일과 이름이 자동으로 가져와진다.

---

## 7.2 데이터 암호화 (AES-256-GCM, TLS)

### 7.2.1 저장 데이터 암호화 — AES-256-GCM

저장 데이터(Data at Rest)의 암호화는 AES-256-GCM(Galois/Counter Mode) 알고리즘을 통해 구현된다. security.py의 encrypt_file(), decrypt_file(), encrypt_bytes(), decrypt_bytes() 함수가 이 기능을 제공한다. GCM 모드는 인증(Authentication)과 암호화(Encryption)를 동시에 제공하는 AEAD(Authenticated Encryption with Associated Data) 방식으로, 데이터의 기밀성과 무결성을 동시에 보장한다.

암호화 파일 포맷은 커스텀 바이너리 구조로 설계되었으며, 다음의 필드로 구성된다. 매직 넘버(MAGIC, 4바이트)는 b'AESF'로 설정되어 암호화된 파일과 일반 파일을 식별한다. 버전(VERSION, 1바이트)은 0x01로 향후 포맷 변경에 대한 하위 호환을 지원한다. 초기화 벡터(IV, 12바이트)는 각 파일마다 os.urandom()으로 생성되는 고유 난수로, 동일 파일을 반복 암호화하더라도 서로 다른 암호문이 생성되도록 보장한다. 인증 태그(TAG, 16바이트)는 암호문의 무결성을 검증하는 GCM 인증 태그이다. 암호화 데이터(ENCRYPTED_DATA, 가변 길이)는 AES-256-GCM으로 암호화된 원본 데이터이다.

총 파일 헤더 크기는 4 + 1 + 12 + 16 = 33바이트이며, 나머지가 암호화된 데이터이다.

암호화 키 관리는 다음과 같이 구현된다. 256비트(32바이트) AES 키는 AES_ENCRYPTION_KEY 환경변수에서 Base64 인코딩된 형태로 로드된다. 키 디코딩 후 정확히 32바이트인지 검증되며, 길이가 맞지 않으면 오류를 기록하고 암호화를 비활성화한다. 환경변수가 설정되지 않은 경우 os.urandom(32)로 임시 키를 자동 생성하여 개발 환경에서의 유연성을 제공하되, "프로덕션에서는 반드시 .env에 고정 키를 설정해야 함"이라는 경고 메시지를 출력한다.

Graceful Degradation이 모든 암호화/복호화 함수에 일관되게 적용된다. AES 키가 없거나 cryptography 패키지가 설치되지 않은 경우, 암호화 실패 시에도 원본 파일/데이터를 그대로 반환하여 핵심 기능(면접 진행, 리포트 생성)이 중단되지 않도록 한다. is_encrypted_file() 함수는 파일의 첫 4바이트가 매직 넘버(AESF)와 일치하는지를 확인하여 암호화 여부를 판별하며, 복호화 함수는 매직 넘버가 없는 파일(레거시 비암호화 파일)에 대해 원본을 그대로 반환하는 하위 호환 처리를 수행한다.

암호화 대상 파일은 업로드된 이력서(PDF), 면접 녹화 파일(WebM/MP4), 생성된 PDF 리포트의 세 범주이며, 암호화된 파일은 .enc 확장자가 추가되어 파일 시스템에 저장된다. 사용자가 파일 다운로드를 요청하면 decrypt_file() 또는 decrypt_bytes()를 통해 실시간 복호화되어 HTTP 응답으로 전달되며, 복호화된 임시 파일은 즉시 삭제된다.

### 7.2.2 전송 데이터 암호화 — TLS 1.2+

전송 데이터(Data in Transit)의 암호화는 TLS(Transport Layer Security) 프로토콜을 통해 구현되며, 두 개의 계층에서 적용된다.

NGINX 레벨(Gateway Layer)에서의 TLS 종단이 주 보안 경계이다. NGINX는 TLS 1.2와 TLS 1.3만을 허용하며(ssl_protocols TLSv1.2 TLSv1.3), 4개의 OWASP 권장 암호 스위트(ECDHE-ECDSA-AES128-GCM-SHA256, ECDHE-RSA-AES128-GCM-SHA256, ECDHE-ECDSA-AES256-GCM-SHA384, ECDHE-RSA-AES256-GCM-SHA384)로 한정된다. SSL 세션 캐싱(10MB 공유 캐시, TTL 10분)과 HSTS(Strict-Transport-Security: max-age=31536000; includeSubDomains) 강제가 적용된다.

FastAPI 서버 레벨에서의 TLS는 개발 환경에서의 직접 접속 시 보안을 제공한다. get_ssl_context() 함수는 TLS_CERTFILE과 TLS_KEYFILE 환경변수로부터 SSL 컨텍스트를 생성하며, ssl.PROTOCOL_TLS_SERVER와 minimum_version = TLSv1_2 설정을 통해 최소 TLS 1.2를 강제한다.

개발 환경을 위해 generate_self_signed_cert() 함수가 RSA-2048 키와 자체 서명 X.509 인증서를 자동 생성한다. 인증서의 주체(Subject)는 CN=localhost, O=AI Interview Dev로 설정되며, SAN(Subject Alternative Name)에 localhost DNS와 127.0.0.1 IP가 포함되어 로컬 개발 시 인증서 경고 없이 HTTPS 접속이 가능하다. 인증서 유효 기간은 365일이며, SHA-256 서명 알고리즘이 사용된다. 기존 인증서가 존재하면 재생성하지 않고 기존 인증서를 재사용한다.

### 7.2.3 WebRTC 미디어 전송 암호화 — DTLS

WebRTC를 통한 비디오/오디오 미디어 스트림은 DTLS(Datagram Transport Layer Security) 프로토콜을 통해 자동으로 암호화된다. DTLS는 UDP 기반 전송에 TLS와 동등한 수준의 암호화를 적용하는 프로토콜로, aiortc 라이브러리가 WebRTC 연결 수립 과정에서 DTLS 핸드셰이크를 자동으로 처리한다. 이를 통해 지원자의 실시간 비디오 및 음성 데이터가 네트워크 구간에서 도청 또는 변조되지 않도록 보호된다.

---

## 7.3 API 보안 (CORS, 보호 엔드포인트, Rate Limiting)

### 7.3.1 CORS (Cross-Origin Resource Sharing) 정책

FastAPI의 CORSMiddleware를 통해 허용된 출처(Origin)만이 API에 접근할 수 있도록 제어된다. 개발 환경에서는 localhost의 다양한 포트(3000, 8000)가 허용되며, 프로덕션 환경에서는 배포 도메인으로 한정된다. 허용되는 HTTP 메서드(GET, POST, PUT, DELETE, OPTIONS)와 헤더(Authorization, Content-Type 등)가 명시적으로 선언되어, 의도하지 않은 크로스 오리진 요청이 차단된다.

### 7.3.2 보호 엔드포인트 (16개 이상)

JWT 인증이 필수적으로 요구되는 보호 엔드포인트는 16개 이상으로, 다음의 기능 영역을 포함한다.

면접 관련 엔드포인트로는 면접 세션 생성(/api/interview/create), 면접 시작(/api/interview/start), 면접 답변 제출(/api/interview/answer), 코딩 테스트 코드 제출(/api/coding/submit), 화이트보드 캡처 분석(/api/whiteboard/analyze)이 있다.

데이터 관련 엔드포인트로는 이력서 업로드(/api/resume/upload), 이력서 삭제(/api/resume/delete), 리포트 조회(/api/report/{session_id}), PDF 다운로드(/api/report/{session_id}/pdf)가 있다.

사용자 관련 엔드포인트로는 프로필 조회(/api/profile), 프로필 수정(/api/profile/update), 비밀번호 변경(/api/auth/change-password), GDPR 데이터 삭제(/api/auth/delete-account)가 있다.

채용 관련 엔드포인트로는 채용공고 생성(/api/jobs/create), 채용공고 수정(/api/jobs/update), 지원자 평가 결과 조회(/api/recruiter/applicants)가 있다.

각 보호 엔드포인트는 Depends(get_current_user)를 함수 시그니처에 선언하여, 인증 로직이 비즈니스 로직과 분리된 선언적(Declarative) 보안을 구현한다.

### 7.3.3 Rate Limiting (3단 제한)

NGINX 설정에서 3개의 독립된 Rate Limit 존(Zone)이 정의되어 DDoS 공격 및 API 남용을 방지한다.

일반 API Rate Limit(api_limit 존)은 클라이언트 IP당 초당 20개 요청, 버스트 40개를 허용하며, /api/ 경로 전체에 적용된다.

인증 API Rate Limit(auth_limit 존)은 클라이언트 IP당 초당 5개 요청, 버스트 10개를 허용하며, /api/auth/ 경로에 적용된다. 인증 엔드포인트는 무차별 대입 공격의 주요 표적이므로 더 엄격한 제한이 적용된다.

WebSocket Rate Limit(ws_limit 존)은 클라이언트 IP당 초당 5개 연결, 버스트 10개를 허용하며, /ws/ 경로에 적용된다.

Rate Limit 초과 시 HTTP 429 Too Many Requests 응답이 즉시 반환된다.

### 7.3.4 보안 응답 헤더

NGINX에서 모든 응답에 자동으로 추가되는 보안 헤더는 다음과 같다. X-Frame-Options: SAMEORIGIN은 클릭재킹(Clickjacking) 공격을 방지하여 다른 사이트에서 본 시스템을 iframe으로 삽입하는 것을 차단한다. X-Content-Type-Options: nosniff는 브라우저의 MIME 타입 추측(MIME Sniffing)을 비활성화하여, 스크립트 인젝션의 한 경로를 차단한다. X-XSS-Protection: 1; mode=block은 브라우저 내장 XSS 필터를 활성화하여, 반사형 XSS(Reflected XSS) 공격을 감지 시 페이지 렌더링을 차단한다. Referrer-Policy: strict-origin-when-cross-origin은 크로스 오리진 요청 시 리퍼러 헤더에 출처(Origin)만 포함하도록 제한하여 민감 URL 정보의 유출을 방지한다. Strict-Transport-Security: max-age=31536000; includeSubDomains는 HSTS(HTTP Strict Transport Security)를 강제하여, 한 번 HTTPS로 접속한 브라우저가 이후 1년간 해당 도메인에 HTTP 접속을 시도하지 않도록 한다. server_tokens off는 NGINX 서버 버전 정보를 응답 헤더에서 제거하여, 공격자가 서버 소프트웨어의 알려진 취약점을 타겟팅하는 것을 어렵게 한다.

---

## 7.4 코드 실행 보안 (Docker 샌드박스, 타임아웃)

### 7.4.1 Docker 컨테이너 격리

코딩 테스트에서 지원자가 제출한 코드는 호스트 시스템으로부터 완전히 격리된 Docker 컨테이너 내에서 실행된다. 각 실행 요청마다 독립적인 일회성(Ephemeral) 컨테이너가 생성되며, 실행 완료 후 즉시 삭제된다.

컨테이너 보안 설정은 다음과 같다. 네트워크 격리(--network none)는 컨테이너에서 외부 네트워크로의 모든 통신을 차단하여, 악의적 코드가 외부 서버와 통신하거나 내부 서비스에 접근하는 것을 방지한다. 파일 시스템 격리는 컨테이너 내부의 파일 시스템이 호스트와 완전히 독립되어, 악의적 코드가 호스트의 파일을 읽거나 수정할 수 없도록 한다. 읽기 전용 루트 파일 시스템(--read-only)은 컨테이너 내부에서의 파일 생성을 제한한다. 권한 제한(--no-new-privileges)은 컨테이너 내부에서 권한 상승(Privilege Escalation)을 방지한다.

### 7.4.2 리소스 제한

각 컨테이너에는 CPU 시간, 메모리, 프로세스 수에 대한 리소스 제한이 적용된다. CPU 시간 제한(타임아웃)은 코드 실행이 지정된 시간(기본 10초)을 초과하면 컨테이너가 docker kill로 강제 종료되어, 무한 루프에 의한 서버 리소스 고갈을 방지한다. 메모리 제한(--memory)은 컨테이너의 최대 메모리 사용량을 제한하여, 메모리 폭탄(Memory Bomb) 공격을 차단한다. PID 제한(--pids-limit)은 컨테이너 내에서 생성 가능한 프로세스 수를 제한하여, Fork Bomb 공격을 방지한다.

### 7.4.3 언어별 보안 이미지

5개 프로그래밍 언어(Python, JavaScript, Java, C, C++)별로 최소화된 slim/alpine 기반 Docker 이미지가 사용되어, 불필요한 시스템 도구(wget, curl, nc 등)가 포함되지 않아 공격 표면(Attack Surface)이 최소화된다.

---

## 7.5 개인정보 보호 (GDPR 전체 데이터 삭제)

### 7.5.1 GDPR 준수 설계

EU 일반 데이터 보호 규정(General Data Protection Regulation, GDPR)의 "잊힐 권리(Right to be Forgotten, Article 17)"를 구현하기 위해, 사용자의 모든 데이터를 완전히 삭제하는 API 엔드포인트(/api/auth/delete-account)가 제공된다.

### 7.5.2 전체 데이터 삭제 범위

GDPR 데이터 삭제 요청 시 삭제되는 데이터의 범위는 다음과 같다.

PostgreSQL에서 삭제되는 데이터로는 사용자 계정 정보(Users 테이블), 면접 세션 기록(InterviewSessions 테이블), 채용공고(JobPostings 테이블, 본인 작성), 답변 평가 결과(EvaluationResults 테이블), 이력서 메타데이터(Resumes 테이블)가 포함된다.

pgvector에서 삭제되는 데이터로는 이력서 임베딩 벡터(resume_embeddings 테이블)와 Q&A 임베딩 벡터(qa_embeddings 테이블)가 포함된다.

파일 시스템에서 삭제되는 데이터로는 암호화된 이력서 파일(.enc), 면접 녹화 파일, 생성된 PDF 리포트가 포함된다.

Redis에서 삭제되는 데이터로는 세션 캐시, RAG 검색 결과 캐시, Celery 태스크 결과가 포함된다.

### 7.5.3 삭제 구현의 기술적 보장

데이터 삭제는 PostgreSQL의 CASCADE 제약 조건을 통해 관련 테이블의 자식 레코드가 부모 레코드 삭제 시 자동으로 함께 삭제되도록 보장된다. 파일 시스템의 물리적 파일 삭제는 os.remove()를 통해 수행되며, 삭제 영역의 덮어쓰기(Overwrite)가 적용되어 디스크 포렌식을 통한 복구를 어렵게 한다. 삭제 완료 후 확인 응답이 반환되며, 삭제 작업 자체의 로그는 보안 감사(Security Audit) 목적으로 별도 보관된다.

---

## 7.6 보안 설계 종합 평가

### 7.6.1 다층적 방어 (Defense in Depth) 구조

본 시스템의 보안은 네트워크 계층(NGINX TLS 종단, Rate Limiting, 보안 헤더), 전송 계층(DTLS 미디어 암호화), 애플리케이션 계층(JWT 인증, CORS, 입력 검증), 데이터 계층(AES-256-GCM 저장 암호화, bcrypt 해싱), 인프라 계층(Docker 컨테이너 격리, 네트워크 none 정책)의 5개 계층에서 독립적인 보안 통제가 적용되는 다층적 방어 구조를 형성한다. 특정 계층의 보안이 우회되더라도 다른 계층의 보안이 추가적인 방어선을 제공하여, 단일 취약점으로 인한 전체 시스템 침해를 어렵게 한다.

### 7.6.2 Graceful Degradation과 보안의 균형

security.py의 모든 암호화 함수에 적용된 Graceful Degradation 패턴은 보안과 가용성 사이의 의도적 트레이드오프이다. AES 키 미설정, cryptography 패키지 미설치 등의 예외 상황에서 시스템이 완전히 중단되지 않고, 경고 로그를 출력하며 비암호화 모드로 동작을 지속하는 이 설계는 개발 환경에서의 유연성을 제공한다. 다만 프로덕션 환경에서는 AES_ENCRYPTION_KEY 환경변수의 설정이 필수적으로 요구되며, 미설정 시 경고 메시지가 명확히 출력되어 운영자의 주의를 환기한다.

### 7.6.3 보안 설정 요약표

| 보안 영역 | 기술 | 상세 설정 |
|-----------|------|-----------|
| 비밀번호 해싱 | bcrypt | rounds=12, 솔트 자동 생성 |
| JWT 인증 | HS256 | 유효 기간 120분, Fail-fast 키 검증 |
| TLS | TLS 1.2/1.3 | OWASP 권장 암호 스위트 4종 |
| 파일 암호화 | AES-256-GCM | 커스텀 포맷(MAGIC+IV+TAG+DATA) |
| 인증서 | RSA-2048 | 자체 서명, SHA-256, SAN 지원 |
| Rate Limiting | NGINX | API 20r/s, Auth 5r/s, WS 5r/s |
| 보안 헤더 | NGINX | HSTS, X-Frame, XSS-Protection 등 6개 |
| 코드 실행 격리 | Docker | --network none, --read-only, --no-new-privileges |
| 개인정보 삭제 | GDPR Art.17 | DB + 벡터 + 파일 + 캐시 전체 삭제 |
| 미디어 암호화 | DTLS | WebRTC 연결 자동 적용 |
| 해시 마이그레이션 | SHA-256→bcrypt | 점진적 자동 마이그레이션 |

---

본 장에서 기술된 보안 설계는 인증·인가, 데이터 암호화, API 보안, 코드 실행 격리, 개인정보 보호의 5개 영역에서 총 11개의 보안 통제를 구현하여, REQ-N-003(암호화)과 REQ-N-004(GDPR) 요구사항을 기술적으로 충족한다. 특히 security.py 단일 모듈(598줄)에 비밀번호 해싱, JWT 토큰, AES-256-GCM 암호화, TLS 인증서 생성의 모든 보안 기능을 집중 배치하여 보안 로직의 일관성과 유지보수성을 확보한 점이 아키텍처적 특징이다. 8장에서는 비동기 처리 및 인프라 계층의 설계와 구현을 상세히 기술한다.
