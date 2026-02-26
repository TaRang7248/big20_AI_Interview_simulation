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

@router.delete("/{id_name}")
def delete_user(id_name: str):
    """
    사용자 회원 탈퇴 처리 (연관 데이터 포함 삭제)
    """
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # 1. 연관된 인터뷰 데이터 삭제 (ON DELETE CASCADE가 설정되지 않은 테이블들 처리)
        # 인터뷰 결과 삭제
        c.execute('DELETE FROM interview_result WHERE id_name = %s', (id_name,))
        # 인터뷰 진행 내역 삭제
        c.execute('DELETE FROM interview_progress WHERE id_name = %s', (id_name,))
        # 인터뷰 정보 삭제
        c.execute('DELETE FROM interview_information WHERE id_name = %s', (id_name,))
        # 인터뷰 공고 삭제
        c.execute('DELETE FROM interview_announcement WHERE id_name = %s', (id_name,))
        
        # 2. 사용자 계정 삭제
        c.execute('DELETE FROM users WHERE id_name = %s', (id_name,))
        
        conn.commit()
        
        if c.rowcount > 0:
            return {"success": True, "message": "회원 탈퇴 및 모든 관련 데이터 삭제가 완료되었습니다."}
        else:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"회원 탈퇴 처리 중 오류 발생: {str(e)}")
    finally:
        conn.close()
