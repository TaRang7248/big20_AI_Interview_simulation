-- 2. 면접 진행 화면 (Interview Process & Media)
-- 면접 상태, 대화 내용, 영상/음성 및 필기 데이터를 관리하는 영역입니다.

-- interviews: 면접 세션 정보
CREATE TABLE IF NOT EXISTS interviews (
    interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    resume_id INTEGER,
    persona TEXT,
    status TEXT DEFAULT 'running', -- running, completed
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id)
);

-- messages: 질문과 답변 통합 테이블
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    role TEXT NOT NULL, -- q (question), a (answer), sys (system)
    content_text TEXT,
    sequence_no INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
);

-- interview_progress: UI 진행도 표시 (Optional)
CREATE TABLE IF NOT EXISTS interview_progress (
    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    total_questions_planned INTEGER,
    current_step INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
);

-- media_assets: 영상/음성 기록 메타데이터
CREATE TABLE IF NOT EXISTS media_assets (
    media_id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    media_type TEXT, -- video, audio
    storage_path TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
);

-- media_timeline_segments: 질문-답변 구간 매핑
CREATE TABLE IF NOT EXISTS media_timeline_segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    start_ms INTEGER,
    end_ms INTEGER,
    FOREIGN KEY (media_id) REFERENCES media_assets(media_id),
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);

-- whiteboard_notes: 화이트보드 펜 데이터
CREATE TABLE IF NOT EXISTS whiteboard_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    author_type TEXT, -- user, ai
    content_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
);
