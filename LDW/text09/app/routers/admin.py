from fastapi import APIRouter, HTTPException
from typing import Optional
from psycopg2.extras import RealDictCursor
import os
from ..database import get_db_connection, logger
from ..services.pdf_service import extract_text_from_pdf

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/applicants")
def get_admin_applicants(admin_id: Optional[str] = None):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT r.interview_number, r.id_name, u.name as applicant_name, 
                   r.title as announcement_title, r.announcement_job, r.pass_fail, 
                   to_char(r.created_at, 'YYYY-MM-DD HH24:MI:SS') as interview_time,
                   r.email
            FROM Interview_Result r
            JOIN users u ON r.id_name = u.id_name
            JOIN interview_announcement ia ON r.title = ia.title
            WHERE 1=1
        """
        params = []
        if admin_id:
            query += " AND ia.id_name = %s"
            params.append(admin_id)
            
        query += " ORDER BY r.created_at DESC"
        
        c.execute(query, tuple(params))
        rows = c.fetchall()
        return {"success": True, "applicants": [dict(row) for row in rows]}
    except Exception as e:
        logger.error(f"Admin Applicants Error: {e}")
        raise HTTPException(status_code=500, detail="지원자 목록 로드 중 오류 발생")
    finally:
        conn.close()

@router.get("/applicant-details/{interview_number}")
def get_applicant_details(interview_number: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Get Interview Result
        c.execute("SELECT * FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        result = c.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="면접 결과를 찾을 수 없습니다.")
        
        session_name = result.get('session_name')
        
        # 2. Get Interview Q&A Progress
        if session_name:
            c.execute("SELECT Create_Question, Question_answer, Answer_Evaluation, answer_time FROM Interview_Progress WHERE session_name = %s ORDER BY id ASC", (session_name,))
        else:
            c.execute("SELECT Create_Question, Question_answer, Answer_Evaluation, answer_time FROM Interview_Progress WHERE Interview_Number = %s ORDER BY id ASC", (interview_number,))
            
        progress = c.fetchall()
        
        # 3. Get Resume Text
        # First check interview_information for original PDF text
        c.execute("SELECT id_name, announcement_job FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        res_info = c.fetchone()
        
        resume_text = ""
        if res_info:
            c.execute("SELECT resume FROM interview_information WHERE id_name = %s AND job = %s ORDER BY created_at DESC LIMIT 1", (res_info['id_name'], res_info['announcement_job']))
            info_row = c.fetchone()
            if info_row:
                resume_path = info_row['resume']
                if os.path.exists(resume_path):
                    resume_text = extract_text_from_pdf(resume_path)
            
        # Fallback to truncated text in Interview_Progress if PDF extraction failed or file missing
        if not resume_text:
            c.execute("SELECT Resume FROM Interview_Progress WHERE Interview_Number = %s LIMIT 1", (interview_number,))
            prog_row = c.fetchone()
            if prog_row:
                resume_text = prog_row['Resume'] # Capital R

        return {
            "success": True,
            "result": dict(result),
            "progress": [dict(p) for p in progress],
            "resume_text": resume_text,
            "resume_image_path": result.get('resume_image_path')
        }
    finally:
        conn.close()
