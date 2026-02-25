import os
import uuid
import shutil
import logging
import json
from datetime import datetime
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from ..database import get_db_connection, logger
from ..config import UPLOAD_FOLDER, AUDIO_FOLDER
from ..models import StartInterviewRequest
from ..services.pdf_service import extract_text_from_pdf
from ..services.llm_service import summarize_resume, generate_next_question, evaluate_answer_bg, get_job_questions
from ..services.stt_service import transcribe_audio
from ..services.tts_service import generate_tts_audio
from ..services.analysis_service import analyze_interview_result

router = APIRouter(prefix="/api", tags=["interview"])
# Note: Using "/api" prefix because we mix /api/interview and /api/upload and /api/interview-results

@router.post("/interview/start")
async def start_interview(background_tasks: BackgroundTasks, data: StartInterviewRequest):
    """
    1. 이력서 및 직무 정보 로드.
    2. 풀 준비 (가져오기 또는 생성).
    3. LLM을 통해 첫 번째 질문 생성.
    4. Interview_Progress에 저장.
    """
    interview_number = str(uuid.uuid4())
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 이력서 경로 가져오기
        c.execute("SELECT resume FROM interview_information WHERE id_name = %s AND job = %s ORDER BY created_at DESC LIMIT 1", (data.id_name, data.job_title))
        row = c.fetchone()
        if not row:
             # 대체 방안: 해당 사용자의 아무 이력서나 찾기
             c.execute("SELECT resume FROM interview_information WHERE id_name = %s ORDER BY created_at DESC LIMIT 1", (data.id_name,))
             row = c.fetchone()
             if not row:
                 return {"success": False, "message": "이력서를 찾을 수 없습니다. 먼저 이력서를 등록해주세요."}
        
        resume_path = row[0]
        resume_text = extract_text_from_pdf(resume_path)
        
        # 지원자 이름 확인
        c.execute("SELECT name FROM users WHERE id_name = %s", (data.id_name,))
        user_row = c.fetchone()
        applicant_name = user_row[0] if user_row else "지원자"

        # 1. 첫 번째 질문: 자기소개 (고정)
        first_question = f"안녕하세요, {applicant_name}님. 면접을 시작하겠습니다. 먼저 간단하게 자기소개를 부탁드립니다."
        
        # 세션 이름 결정 (예: 면접-1)
        c.execute("SELECT COUNT(DISTINCT interview_number) FROM Interview_Progress WHERE id_name = %s", (data.id_name,))
        interview_count = c.fetchone()[0]
        base_session_name = f"면접-{interview_count + 1}"
        session_name = base_session_name
        
        # 중복 체크 로직: 이미 존재하는 세션 이름인지 확인하고, 중복 시 고유값 할당
        suffix = 1
        while True:
            c.execute("SELECT COUNT(*) FROM Interview_Progress WHERE id_name = %s AND session_name = %s", (data.id_name, session_name))
            if c.fetchone()[0] == 0:
                break
            session_name = f"{base_session_name}({suffix})"
            suffix += 1

        # 이력서 요약 (새 기능)
        resume_summary = summarize_resume(resume_text)

        # 백그라운드에서 질문 풀 준비
        background_tasks.add_task(get_job_questions, data.job_title)

        # DB에 저장
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question, id_name, session_name, announcement_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (interview_number, applicant_name, data.job_title, resume_summary, first_question, data.id_name, session_name, data.announcement_id))
        
        conn.commit()
        
        # TTS 음성 생성 (비디오 생성 시도 포함)
        logger.info(f"첫 질문 TTS 생성 중... 텍스트: {first_question[:30]}")
        tts_result = await generate_tts_audio(first_question)
        
        # TTS 결과에서 URL과 타입 추출
        audio_url = None
        audio_type = "audio"
        if isinstance(tts_result, dict):
            audio_url = tts_result.get("url")
            audio_type = tts_result.get("type", "audio")
        elif isinstance(tts_result, str):
            audio_url = tts_result  # 하위 호환성 유지
        
        logger.info(f"첫 질문 미디어 URL: {audio_url} (타입: {audio_type})")

        return {
            "success": True,
            "interview_number": interview_number,
            "question": first_question,
            "audio_url": audio_url,
            "audio_type": audio_type,
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
    2. 이전 질문 찾기.
    3. 답변 평가.
    4. 다음 질문 생성.
    5. 저장 및 반환.
    """
    
    conn = None
    try:
        # 1. 파일명을 결정하기 위해 DB를 연결하고 세션 정보를 먼저 가져옵니다.
        conn = get_db_connection()
        c = conn.cursor()
        
        # 이 면접의 가장 마지막 행을 찾습니다.
        c.execute("""
            SELECT id, Create_Question, Resume, id_name, announcement_id FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id DESC LIMIT 1
        """, (interview_number,))
        row = c.fetchone()
        
        if not row:
             logger.error("No active question found.")
             if conn: conn.close()
             return {"success": False, "message": "진행 중인 면접을 찾을 수 없습니다."}
             
        current_row_id = row[0]
        prev_question = row[1]
        resume_summary = row[2] if row[2] else ""
        id_name = row[3]
        announcement_id = row[4]
        
        # 세션 이름 가져오기
        c.execute("SELECT session_name FROM Interview_Progress WHERE id = %s", (current_row_id,))
        session_name = c.fetchone()[0]

        # 2. 새로운 형식으로 오디오 파일 저장
        # 형식: YYYY-MM-DD-HH-MM-SS-{session_name}.webm
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        audio_filename = f"{timestamp}-{session_name}.webm"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
            
        # 3. STT (Whisper + Gemini + 분석)
        stt_result = transcribe_audio(audio_path)
        
        # 딕셔너리 반환 형식 처리
        if isinstance(stt_result, dict):
            applicant_answer = stt_result.get("text", "")
            audio_analysis = stt_result.get("analysis", {})
            logger.info(f"Audio Analysis: {audio_analysis}")
        else:
            # 레거시 반환을 위한 대체 수단
            applicant_answer = str(stt_result)
            audio_analysis = None
        
        # 4. 질문 단계 결정
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

        # 5. 참고용 직무 질문 가져오기
        ref_questions = get_job_questions(job_title)

        # 6. 평가 및 다음 질문 생성
        # 6. 다음 질문 우선 생성 (빠른 응답을 위해)
        # 중복을 방지하기 위해 이전의 모든 질문을 가져옵니다.
        c.execute("SELECT Create_Question FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        history_rows = c.fetchall()
        
        history_questions = [r[0] for r in history_rows if r[0]]

        next_question = generate_next_question(
            job_title, 
            applicant_name, 
            current_q_count, 
            prev_question, 
            applicant_answer, 
            next_phase, 
            resume_summary, 
            ref_questions,
            history_questions,
            audio_analysis=audio_analysis
        )

        # 7. 현재 답변, 시간 등을 DB에 업데이트 (평가는 나중에 채워넣도록 함)
        # Answer_Evaluation 칼럼은 일단 NULL 또는 '평가 중...' 으로 설정
        c.execute("""
            UPDATE Interview_Progress 
            SET Question_answer = %s, answer_time = %s, Answer_Evaluation = %s
            WHERE id = %s
        """, (applicant_answer, answer_time, "평가 진행 중...", current_row_id))
        
        interview_finished = False
        if next_phase == "END":
             interview_finished = True
        else:
            # 8. 다음 질문 레코드 삽입 (END가 아닐 경우)
            c.execute('''
                INSERT INTO Interview_Progress (
                    Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question, id_name, session_name, announcement_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (interview_number, applicant_name, job_title, resume_summary, next_question, id_name, session_name, announcement_id))
        
        conn.commit()
        
        # --- NEW: 비디오 분석 요약 추가 및 백그라운드 평가 태스크 추가 ---
        from ..services.analysis_service import get_recent_video_log_summary
        video_summary = get_recent_video_log_summary(interview_number, duration_seconds=60)

        # 백그라운드 태스크로 평가는 넘김
        background_tasks.add_task(
            evaluate_answer_bg,
            job_title=job_title,
            applicant_name=applicant_name,
            current_q_count=current_q_count,
            prev_question=prev_question,
            applicant_answer=applicant_answer,
            next_phase=next_phase,
            resume_summary=resume_summary,
            audio_analysis=audio_analysis,
            interview_number=interview_number,
            current_row_id=current_row_id,
            video_summary=video_summary
        )

        if interview_finished:
             background_tasks.add_task(analyze_interview_result, interview_number, job_title, applicant_name, id_name, announcement_id)

        
        conn.commit()
        conn.close()
        conn = None # 연결이 닫힌 경우 finally 블록에서 이슈가 발생하지 않도록 방지

        # 면접이 계속되면 다음 질문 TTS 생성
        audio_url = None
        audio_type = "audio"
        if not interview_finished:
            tts_result = await generate_tts_audio(next_question)
            if isinstance(tts_result, dict):
                audio_url = tts_result.get("url")
                audio_type = tts_result.get("type", "audio")
            elif isinstance(tts_result, str):
                audio_url = tts_result  # 하위 호환성 유지

        return {
            "success": True,
            "next_question": next_question,
            "audio_url": audio_url,
            "audio_type": audio_type,
            "transcript": applicant_answer,
            "interview_finished": interview_finished,
            "session_name": session_name
        }

    except Exception as e:
        logger.error(f"Answer Submission Error: {e}")
        if conn: conn.close()
        # Return a valid JSON even on error so frontend loading stops
        return {
            "success": False, 
            "message": f"시스템 오류가 발생했습니다. (Error: {str(e)})",
            "next_question": "오류가 발생하여 다음 질문으로 넘어갑니다.",
            "audio_url": None,
            "transcript": "오류 발생",
            "interview_finished": False,
            "session_name": "ErrorSession"
        }

@router.post("/upload/resume")
async def upload_resume(resume: UploadFile = File(...), id_name: str = Form(...), job_title: str = Form(...)):
    if not resume.filename.lower().endswith('.pdf'):
         raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
    
    filename = f"{id_name}_{uuid.uuid4()}_{resume.filename}" # 더 안전한 파일 이름
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
            
        conn = get_db_connection()
        c = conn.cursor()
        # 필요한 경우 이 사용자/직무에 대한 기존 이력서를 삭제하거나 단순히 새로 삽입합니다.
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
