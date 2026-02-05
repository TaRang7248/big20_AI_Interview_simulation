-- 3. 음성 인식 데이터 (STT Processing)
-- 정확도 분석 및 보정을 위해 원문과 정제본을 분리하여 관리합니다.

-- speech_transcripts: STT 데이터
CREATE TABLE IF NOT EXISTS speech_transcripts (
    stt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    media_id INTEGER,
    stt_raw_text TEXT,
    stt_normalized_text TEXT,
    confidence REAL,
    stt_model_name_ver TEXT, -- stt_model_name/ver
    FOREIGN KEY (message_id) REFERENCES messages(message_id),
    FOREIGN KEY (media_id) REFERENCES media_assets(media_id)
);
