import sqlite3
from typing import Optional, List, Dict, Any
from ..connection import get_connection

class EvaluationRepository:
    def create_evaluation(self, interview_id: int, summary: str, feedback: str) -> int:
        """
        Creates an evaluation record for an interview.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO interview_evaluations (interview_id, summary_text, feedback_text)
                VALUES (?, ?, ?)
                """,
                (interview_id, summary, feedback)
            )
            evaluation_id = cursor.lastrowid
            conn.commit()
            return evaluation_id
        finally:
            conn.close()

    def add_score(self, evaluation_id: int, score_type: str, value: int, rationale: str) -> int:
        """
        Adds a score for a specific category (e.g., 'Communication', 'Technical').
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO evaluation_scores (evaluation_id, score_type, score_value, rationale_text)
                VALUES (?, ?, ?, ?)
                """,
                (evaluation_id, score_type, value, rationale)
            )
            score_id = cursor.lastrowid
            conn.commit()
            return score_id
        finally:
            conn.close()

    def set_pass_fail_decision(self, evaluation_id: int, decision: str, reason: str) -> int:
        """
        Records the final pass/fail decision.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO pass_fail_decisions (evaluation_id, decision, decision_reason_text)
                VALUES (?, ?, ?)
                """,
                (evaluation_id, decision, reason)
            )
            decision_id = cursor.lastrowid
            conn.commit()
            return decision_id
        finally:
            conn.close()

    def get_evaluation(self, interview_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves the evaluation for a given interview.
        """
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM interview_evaluations WHERE interview_id = ?",
                (interview_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
