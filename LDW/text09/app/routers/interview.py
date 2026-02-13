import os
import uuid
import shutil
import logging
import json
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from ..database import get_db_connection, logger
from ..config import UPLOAD_FOLDER, AUDIO_FOLDER
from ..models import StartInterviewRequest
from ..services.pdf_service import extract_text_from_pdf
from ..services.llm_service import summarize_resume, evaluate_answer, get_job_questions
from ..services.stt_service import transcribe_audio
from ..services.tts_service import generate_tts_audio
from ..services.analysis_service import analyze_interview_result

router = APIRouter(prefix="/api", tags=["interview"])
# Note: Using "/api" prefix because we mix /api/interview and /api/upload and /api/interview-results

@router.post("/interview/start")
async def start_interview(background_tasks: BackgroundTasks, data: StartInterviewRequest):
    """
    1. Load Resume & Job Info.
    2. Prepare Pool (Get or Create).
    3. Generate 1st Question via LLM.
    4. Save to Interview_Progress.
    """
    interview_number = str(uuid.uuid4())
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get Resume Path
        c.execute("SELECT resume FROM interview_information WHERE id_name = %s AND job = %s ORDER BY created_at DESC LIMIT 1", (data.id_name, data.job_title))
        row = c.fetchone()
        if not row:
             # Fallback: try finding any resume for this user
             c.execute("SELECT resume FROM interview_information WHERE id_name = %s ORDER BY created_at DESC LIMIT 1", (data.id_name,))
             row = c.fetchone()
             if not row:
                 return {"success": False, "message": "이력서를 찾을 수 없습니다. 먼저 이력서를 등록해주세요."}
        
        resume_path = row[0]
        resume_text = extract_text_from_pdf(resume_path)
        
        # Determine Applicant Name
        c.execute("SELECT name FROM users WHERE id_name = %s", (data.id_name,))
        user_row = c.fetchone()
        applicant_name = user_row[0] if user_row else "지원자"

        # 1. First Question: Self Introduction (Fixed)
        first_question = f"안녕하세요, {applicant_name}님. 면접을 시작하겠습니다. 먼저 간단하게 자기소개를 부탁드립니다."
        
        # Determine Session Name (e.g., 면접-1)
        c.execute("SELECT COUNT(DISTINCT interview_number) FROM Interview_Progress WHERE id_name = %s", (data.id_name,))
        interview_count = c.fetchone()[0]
        session_name = f"면접-{interview_count + 1}"

        # Resume Summarization (New Feature)
        resume_summary = summarize_resume(resume_text)

        # Prepare Question Pool in Background
        background_tasks.add_task(get_job_questions, data.job_title)

        # Save to DB
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question, id_name, session_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (interview_number, applicant_name, data.job_title, resume_summary, first_question, data.id_name, session_name))
        
        conn.commit()
        
        # Generate TTS
        logger.info(f"Generating first question TTS... Text: {first_question[:30]}")
        audio_url = await generate_tts_audio(first_question)
        logger.info(f"First Question Audio URL: {audio_url}")

        return {
            "success": True,
            "interview_number": interview_number,
            "question": first_question,
            "audio_url": audio_url,
            "session_name": session_name
        }
        
    except Exception as e:
        logger.error(f"Start Interview Error: {e}")
        return {"success": False, "message": "면접 시작 중 오류가 발생했습니다."}
    finally:
        conn.close()

@router.post("/interview/answer")
async def submit_answer(
    background_tasks: BackgroundTasks,
    interview_number: str = Form(...),
    applicant_name: str = Form(...),
    job_title: str = Form(...),
    answer_time: str = Form(...),
    audio: UploadFile = File(...)
):
    """
    1. STT (Whisper).
    2. Find Previous Question.
    3. Evaluate Answer.
    4. Generate Next Question.
    5. Save & Return.
    """
    
    # Save Audio File
    audio_filename = f"{interview_number}_{uuid.uuid4()}.webm"
    audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
    
    try:
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
            
        # 1. STT (Whisper)
        applicant_answer = transcribe_audio(audio_path)
        
        # 2. Find Previous Question
        conn = get_db_connection()
        c = conn.cursor()
        
        # We find the latest row for this interview
        c.execute("""
            SELECT id, Create_Question, Resume, id_name FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id DESC LIMIT 1
        """, (interview_number,))
        row = c.fetchone()
        
        if not row:
             logger.error("No active question found.")
             conn.close()
             return {"success": False, "message": "진행 중인 면접을 찾을 수 없습니다."}
             
        current_row_id = row[0]
        prev_question = row[1]
        resume_summary = row[2] if row[2] else ""
        id_name = row[3]
        
        # Get session_name
        c.execute("SELECT session_name FROM Interview_Progress WHERE id = %s", (current_row_id,))
        session_name = c.fetchone()[0]
        
        # 3. Determine Question Phase
        c.execute("SELECT COUNT(*) FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        current_q_count = c.fetchone()[0]
        logger.info(f"Answer Submission. Interview={interview_number}, Count={current_q_count}")
        
        next_phase = ""
        if current_q_count < 6:
            next_phase = "직무 기술(Technical Skill)"
        elif current_q_count < 11:
            next_phase = "인성 및 가치관(Personality & Culture Fit)"
        elif current_q_count == 11:
            next_phase = "마무리(Closing)"
        else:
            next_phase = "END"

        # 4. Fetch Job Questions for Reference
        ref_questions = get_job_questions(job_title)

        # 5. Evaluate & Generate Next Question
        evaluation, next_question = evaluate_answer(
            job_title, applicant_name, current_q_count, prev_question, applicant_answer, next_phase, resume_summary, ref_questions
        )

        # 5. Save Current Answer & Evaluation
        c.execute("""
            UPDATE Interview_Progress 
            SET Question_answer = %s, answer_time = %s, Answer_Evaluation = %s
            WHERE id = %s
        """, (applicant_answer, answer_time, evaluation, current_row_id))
        
        interview_finished = False
        if next_phase == "END":
             interview_finished = True
             background_tasks.add_task(analyze_interview_result, interview_number, job_title, applicant_name, id_name)
        else:
            # 6. Insert Next Question Record (if not END)
            c.execute('''
                INSERT INTO Interview_Progress (
                    Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question, id_name, session_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (interview_number, applicant_name, job_title, resume_summary, next_question, id_name, session_name))
        
        conn.commit()
        conn.close()

        # Generate TTS if not finished
        audio_url = None
        if not interview_finished:
             audio_url = await generate_tts_audio(next_question)

        return {
            "success": True,
            "next_question": next_question,
            "audio_url": audio_url,
            "transcript": applicant_answer,
            "interview_finished": interview_finished,
            "session_name": session_name
        }

    except Exception as e:
        logger.error(f"Answer Submission Error: {e}")
        return {"success": False, "message": f"오류 발생: {str(e)}"}

@router.post("/upload/resume")
async def upload_resume(resume: UploadFile = File(...), id_name: str = Form(...), job_title: str = Form(...)):
    if not resume.filename.lower().endswith('.pdf'):
         raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    
    filename = f"{id_name}_{uuid.uuid4()}_{resume.filename}" # More secure filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
            
        conn = get_db_connection()
        c = conn.cursor()
        # Delete old resume for this user/job if needed, or just insert new
        c.execute('''
            INSERT INTO interview_information (id_name, job, resume)
            VALUES (%s, %s, %s)
        ''', (id_name, job_title, filepath))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "이력서가 업로드되었습니다.", "filepath": filepath}
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail="파일 업로드 중 오류 발생")

@router.get("/interview/result/{interview_number}")
def get_interview_result(interview_number: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        row = c.fetchone()
        if row:
            return {"success": True, "result": dict(row)}
        else:
            return {"success": False, "message": "결과 분석 중입니다."}
    finally:
        conn.close()

@router.get("/interview-results/{id_name}")
def get_interview_results(id_name: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT title as announcement_title, announcement_job, 
                   to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as interview_time, 
                   pass_fail
            FROM Interview_Result 
            WHERE id_name = %s 
            ORDER BY created_at DESC
        """
        c.execute(query, (id_name,))
        rows = c.fetchall()
        return {"success": True, "results": [dict(row) for row in rows]}
    finally:
        conn.close()
