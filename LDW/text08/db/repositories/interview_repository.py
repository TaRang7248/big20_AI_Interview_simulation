import sqlite3
from typing import Optional, List, Dict, Any
from ..connection import get_connection

class InterviewRepository:
    def create_interview(self, user_id: int, resume_id: int, persona: str) -> int:
        """
        Starts a new interview session.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO interviews (user_id, resume_id, persona, status)
                VALUES (?, ?, ?, 'running')
                """,
                (user_id, resume_id, persona)
            )
            interview_id = cursor.lastrowid
            conn.commit()
            return interview_id
        finally:
            conn.close()

    def update_interview_status(self, interview_id: int, status: str, end_time: Optional[str] = None):
        """
        Updates the status of an interview (e.g., 'completed').
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if end_time:
                cursor.execute(
                    "UPDATE interviews SET status = ?, end_time = ? WHERE interview_id = ?",
                    (status, end_time, interview_id)
                )
            else:
                cursor.execute(
                    "UPDATE interviews SET status = ? WHERE interview_id = ?",
                    (status, interview_id)
                )
            conn.commit()
        finally:
            conn.close()

    def add_message(self, interview_id: int, role: str, content: str, sequence: int) -> int:
        """
        Adds a message (question/answer/system) to the interview.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO messages (interview_id, role, content_text, sequence_no)
                VALUES (?, ?, ?, ?)
                """,
                (interview_id, role, content, sequence)
            )
            message_id = cursor.lastrowid
            conn.commit()
            return message_id
        finally:
            conn.close()

    def get_messages(self, interview_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all messages for a specific interview, ordered by sequence.
        """
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM messages WHERE interview_id = ? ORDER BY sequence_no ASC",
                (interview_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_media_asset(self, interview_id: int, media_type: str, path: str, duration: int) -> int:
        """
        Saves metadata for a media file (video/audio).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO media_assets (interview_id, media_type, storage_path, duration_ms)
                VALUES (?, ?, ?, ?)
                """,
                (interview_id, media_type, path, duration)
            )
            media_id = cursor.lastrowid
            conn.commit()
            return media_id
        finally:
            conn.close()
