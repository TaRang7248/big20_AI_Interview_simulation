-- 4. 피드백 화면 (Evaluation & Result)
-- 면접 결과 총평, 점수, 합불 여부 및 근거를 구조화한 영역입니다.

-- interview_evaluations: 면접 총평
CREATE TABLE IF NOT EXISTS interview_evaluations (
    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    summary_text TEXT,
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (interview_id) REFERENCES interviews(interview_id)
);

-- evaluation_scores: 항목별 점수
CREATE TABLE IF NOT EXISTS evaluation_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL,
    score_type TEXT, -- communication, technical, etc.
    score_value INTEGER,
    rationale_text TEXT,
    FOREIGN KEY (evaluation_id) REFERENCES interview_evaluations(evaluation_id)
);

-- pass_fail_decisions: 최종 합불 여부
CREATE TABLE IF NOT EXISTS pass_fail_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL,
    decision TEXT, -- pass, fail
    decision_reason_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_id) REFERENCES interview_evaluations(evaluation_id)
);

-- evidence_links: 평가 근거 연결 (Optional)
CREATE TABLE IF NOT EXISTS evidence_links (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    FOREIGN KEY (score_id) REFERENCES evaluation_scores(score_id),
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);
