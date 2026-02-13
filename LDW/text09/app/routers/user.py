from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor
from ..database import get_db_connection
from ..models import UserUpdate

router = APIRouter(prefix="/api/user", tags=["user"])

@router.get("/{id_name}")
def get_user_info(id_name: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT id_name, name, dob, gender, email, address, phone, type FROM users WHERE id_name = %s', (id_name,))
        row = c.fetchone()
        if row:
            return {"success": True, "user": dict(row)}
        else:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    finally:
        conn.close()

@router.put("/{id_name}")
def update_user_info(id_name: str, data: UserUpdate):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE users SET email = %s, phone = %s, address = %s WHERE id_name = %s
        ''', (data.email, data.phone, data.address, id_name))
        conn.commit()
        return {"success": True, "message": "정보가 수정되었습니다."}
    finally:
        conn.close()
