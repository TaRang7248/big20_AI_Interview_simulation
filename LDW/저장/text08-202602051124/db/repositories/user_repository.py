import sqlite3
from typing import Optional, Dict, Any, Tuple
from ..connection import get_connection

class UserRepository:
    def create_user(self, email: str, password_hash: str) -> int:
        """
        Creates a new user and returns the user_id.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError(f"User with email {email} already exists.")
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user by email.
        """
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user by ID.
        """
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def save_user_pii(self, user_id: int, name: str, birth_date: str, gender: str, address: str) -> int:
        """
        Saves user's personally identifiable information (PII).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO user_pii (user_id, name, birth_date, gender, address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, name, birth_date, gender, address)
            )
            pii_id = cursor.lastrowid
            conn.commit()
            return pii_id
        except sqlite3.IntegrityError:
            # Handle update if PII already exists for user
            cursor.execute(
                """
                UPDATE user_pii 
                SET name=?, birth_date=?, gender=?, address=?
                WHERE user_id=?
                """,
                (name, birth_date, gender, address, user_id)
            )
            conn.commit()
            # Retrieve the ID after update
            cursor.execute("SELECT pii_id FROM user_pii WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def save_resume(self, user_id: int, target_role: str, skills: str, experience: str, certifications: str) -> int:
        """
        Saves or updates a user's resume.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO resumes (user_id, target_role, skills_text, experience_text, certifications_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, target_role, skills, experience, certifications)
            )
            resume_id = cursor.lastrowid
            conn.commit()
            return resume_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
