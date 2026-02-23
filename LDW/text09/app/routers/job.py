from fastapi import APIRouter, HTTPException
from typing import Optional
from psycopg2.extras import RealDictCursor
from ..database import get_db_connection
from ..models import JobCreate, JobUpdate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("")
def get_jobs(user_id: Optional[str] = None):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        if user_id:
            query = """
                SELECT id, title, job, deadline, content, qualifications, preferred_qualifications, benefits, hiring_process, number_of_hires, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at 
                FROM interview_announcement 
                ORDER BY (CASE WHEN id_name = %s THEN 0 ELSE 1 END), created_at DESC
            """
            c.execute(query, (user_id,))
        else:
            c.execute("SELECT id, title, job, deadline, content, qualifications, preferred_qualifications, benefits, hiring_process, number_of_hires, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement ORDER BY created_at DESC")
            
        rows = c.fetchall()
        return {"success": True, "jobs": [dict(row) for row in rows]}
    finally:
        conn.close()

@router.get("/{id}")
def get_job_detail(id: int):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT id, title, job, deadline, content, qualifications, preferred_qualifications, benefits, hiring_process, number_of_hires, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement WHERE id = %s", (id,))
        row = c.fetchone()
        if row:
            return {"success": True, "job": dict(row)}
        else:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    finally:
        conn.close()

@router.post("")
def create_job(job: JobCreate):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO interview_announcement (title, job, deadline, content, qualifications, preferred_qualifications, benefits, hiring_process, number_of_hires, id_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (job.title, job.job, job.deadline, job.content, job.qualifications, job.preferred_qualifications, job.benefits, job.hiring_process, job.number_of_hires, job.id_name))
        new_id = c.fetchone()[0]
        conn.commit()
        return {"success": True, "message": "공고가 등록되었습니다.", "id": new_id}
    finally:
        conn.close()

@router.put("/{id}")
def update_job(id: int, job: JobUpdate):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id_name FROM interview_announcement WHERE id = %s", (id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        if row[0] != job.id_name:
            raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")
        
        c.execute('''
            UPDATE interview_announcement
            SET title = %s, job = %s, deadline = %s, content = %s, qualifications = %s, preferred_qualifications = %s, benefits = %s, hiring_process = %s, number_of_hires = %s
            WHERE id = %s
        ''', (job.title, job.job, job.deadline, job.content, job.qualifications, job.preferred_qualifications, job.benefits, job.hiring_process, job.number_of_hires, id))
        conn.commit()
        return {"success": True, "message": "공고가 수정되었습니다."}
    finally:
        conn.close()

@router.delete("/{id}")
def delete_job(id: int, id_name: str):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id_name FROM interview_announcement WHERE id = %s", (id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
        if row[0] != id_name:
            raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
        
        c.execute('DELETE FROM interview_announcement WHERE id = %s', (id,))
        conn.commit()
        return {"success": True, "message": "공고가 삭제되었습니다."}
    finally:
        conn.close()
