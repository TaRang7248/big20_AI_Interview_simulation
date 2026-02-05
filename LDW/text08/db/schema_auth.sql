-- 1. 로그인 / 회원정보 / 이력서 (User & Auth)
-- 데이터 무결성과 개인정보 보호를 위해 PII를 분리하고 인증 체계를 수립한 영역입니다.

-- users: 기본 계정 정보를 저장
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- user_pii: 개인식별정보를 분리 저장
CREATE TABLE IF NOT EXISTS user_pii (
    pii_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    name TEXT,
    birth_date TEXT,
    gender TEXT,
    address TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- resumes: 이력서 정보
CREATE TABLE IF NOT EXISTS resumes (
    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_role TEXT,
    skills_text TEXT,
    experience_text TEXT,
    certifications_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- sessions: 사용자 접속 세션 관리
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- auth_tokens: 인증 토큰 관리
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id INTEGER,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
