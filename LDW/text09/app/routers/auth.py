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

# --- ID/PW 찾기 기능 추가 ---
from ..models import FindIdRequest, FindPwStep1Request, FindPwStep2Request
import random

# 임시 인증번호 저장소 (실제 운영 환경에서는 Redis 등을 사용 권장)
verification_codes = {}

@router.post("/find-id")
def find_id(data: FindIdRequest):
    """
    이름과 이메일로 아이디(id_name)를 찾습니다.
    """
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        # 이름(name)과 이메일(email)이 일치하는 사용자 확인
        c.execute('SELECT id_name FROM users WHERE name = %s AND email = %s', (data.name, data.email))
        row = c.fetchone()
        if row:
            return {"success": True, "id_name": row['id_name']}
        else:
            return {"success": False, "message": "해당하는 아이디가 없습니다."}
    except Exception as e:
        logger.error(f"Find ID Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/find-pw-step1")
def find_pw_step1(data: FindPwStep1Request):
    """
    아이디 확인 후 이메일로 4자리 인증번호를 발송합니다.
    """
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        # 아이디 존재 여부 및 이메일 확인
        c.execute('SELECT email FROM users WHERE id_name = %s', (data.id_name,))
        row = c.fetchone()
        if row:
            email = row['email']
            # 4자리 무작위 숫자 생성
            code = str(random.randint(1000, 9999))
            verification_codes[data.id_name] = code
            
            # TODO: 실제 이메일 발송 로직 추가 (현재는 시뮬레이션으로 응답에 포함하거나 로그 출력)
            logger.info(f"[비밀번호 찾기] 아이디: {data.id_name}, 이메일: {email}, 인증번호: {code}")
            
            # 사용자에게는 이메일이 발송되었다는 메시지만 전달
            # 테스트 편의를 위해 code를 반환값에 포함 (실제 배포시에는 제거)
            return {"success": True, "message": f"{email}로 인증번호가 전송되었습니다.", "debug_code": code}
        else:
            return {"success": False, "message": "해당 아이디를 찾을 수 없습니다."}
    except Exception as e:
        logger.error(f"Find PW Step 1 Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/find-pw-step2")
def find_pw_step2(data: FindPwStep2Request):
    """
    인증번호 확인 후 비밀번호(pw)를 알려줍니다.
    """
    if data.id_name in verification_codes and verification_codes[data.id_name] == data.verification_code:
        # 인증 성공 시 저장된 코드 삭제
        del verification_codes[data.id_name]
        
        conn = get_db_connection()
        try:
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute('SELECT pw FROM users WHERE id_name = %s', (data.id_name,))
            row = c.fetchone()
            if row:
                return {"success": True, "pw": row['pw']}
            else:
                raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
        finally:
            conn.close()
    else:
        return {"success": False, "message": "인증번호가 일치하지 않습니다."}
