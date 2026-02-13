from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor
from ..database import get_db_connection, logger
from ..models import UserRegister, UserLogin, PasswordVerify, PasswordChange, IdCheckRequest

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/check-id")
def check_id_duplicate(request: IdCheckRequest):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id_name FROM users WHERE id_name = %s', (request.id_name,))
        if c.fetchone():
            return {"available": False, "message": "이미 존재하는 아이디입니다."}
        else:
            return {"available": True, "message": "사용 가능한 아이디입니다."}
    except Exception as e:
        logger.error(f"ID Check Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/register")
def register(user: UserRegister):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id_name FROM users WHERE id_name = %s', (user.id_name,))
        if c.fetchone():
            return {"success": False, "message": "이미 존재하는 아이디입니다."}
        
        c.execute('''
            INSERT INTO users (id_name, pw, name, dob, gender, email, address, phone, type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user.id_name, user.pw, user.name, user.dob, user.gender, user.email, user.address, user.phone, user.type))
        conn.commit()
        return {"success": True, "message": "회원가입 완료"}
    except Exception as e:
        logger.error(f"Register Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/login")
def login(user: UserLogin):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT * FROM users WHERE id_name = %s AND pw = %s', (user.id_name, user.pw))
        row = c.fetchone()
        if row:
            return {"success": True, "user": dict(row)}
        else:
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 일치하지 않습니다.")
    finally:
        conn.close()

@router.post("/verify-password")
def verify_password(data: PasswordVerify):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT pw FROM users WHERE id_name = %s', (data.id_name,))
        row = c.fetchone()
        if row and row[0] == data.pw:
            return {"success": True}
        else:
            raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")
    finally:
        conn.close()

@router.post("/change-password")
def change_password(data: PasswordChange):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('UPDATE users SET pw = %s WHERE id_name = %s', (data.new_pw, data.id_name))
        conn.commit()
        if c.rowcount > 0:
            return {"success": True, "message": "비밀번호가 변경되었습니다."}
        else:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    finally:
        conn.close()
