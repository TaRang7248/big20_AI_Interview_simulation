import os
import uuid
import shutil
import psycopg2
import json
import logging
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from threading import Timer
import webbrowser

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")
UPLOAD_FOLDER = 'uploads/resumes'
AUDIO_FOLDER = 'uploads/audio'
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Helper ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT,
            connect_timeout=3
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"DB Connection Failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# --- Pydantic Models ---
class UserRegister(BaseModel):
    id_name: str
    pw: str
    name: str
    dob: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    type: str = 'applicant'

class UserLogin(BaseModel):
    id_name: str
    pw: str

class PasswordVerify(BaseModel):
    id_name: str
    pw: str

class PasswordChange(BaseModel):
    id_name: str
    new_pw: str

class UserUpdate(BaseModel):
    pw: Optional[str] = None
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    
class JobCreate(BaseModel):
    title: str
    job: Optional[str] = ''
    deadline: Optional[str] = ''
    content: Optional[str] = ''
    id_name: Optional[str] = None

class JobUpdate(BaseModel):
    title: str
    job: Optional[str] = ''
    deadline: Optional[str] = ''
    content: Optional[str] = ''
    id_name: Optional[str] = None

class StartInterviewRequest(BaseModel):
    id_name: str
    job_title: str

# --- Helper Functions ---

def extract_text_from_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"PDF Extraction Error: {e}")
        return ""

def get_job_questions(job_title):
    """
    Fetches questions for a job title.
    If not in pool, selects from interview_answer using LLM and saves to pool.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Check Pool
    c.execute("SELECT question_id FROM job_question_pool WHERE job_title = %s", (job_title,))
    rows = c.fetchall()
    
    if rows:
        # Fetch actual question text
        question_ids = [row[0] for row in rows]
        # Dynamically build query for IN clause
        placeholders = ','.join(['%s'] * len(question_ids))
        c.execute(f"SELECT question FROM interview_answer WHERE id IN ({placeholders})", tuple(question_ids))
        questions = [r[0] for r in c.fetchall()]
        conn.close()
        return questions

    # 2. If no pool, create one
    logger.info(f"No pool found for {job_title}. Creating one using LLM...")
    c.execute("SELECT id, question FROM interview_answer") # Fetch ALL questions
    all_questions = c.fetchall() # list of (id, question)
    
    if not all_questions:
        conn.close()
        return ["자기소개를 해주세요."]

    # Convert to JSON for LLM
    questions_json = [{"id": q[0], "question": q[1]} for q in all_questions]
    
    prompt = f"""
    당신은 채용 담당자입니다.
    지원 직무: {job_title}
    
    아래 전체 면접 질문 리스트에서 해당 직무에 가장 적합한 핵심 질문 5~10개를 선별해주세요.
    반드시 JSON 형식으로 ID 리스트만 반환해주세요. 예: [1, 5, 10, ...]
    
    질문 리스트:
    {json.dumps(questions_json[:300], ensure_ascii=False)} 
    (데이터가 많으면 일부만 전송됨)
    """
    # Note: Sending all data might be too large. Truncating to 300 for safety if needed, 
    # but strictly we should probably filter by keyword first if dataset is huge. 
    # For now assuming data.json size is manageable for GPT-4o context window if it's not massive. 
    # user said "once", so this is a one-time cost.
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content)
        selected_ids = result.get("ids", [])
        
        # fallback if json structure is different
        if not selected_ids and "usage" not in result: # just in case
             # try to parse list if it returned raw list
             pass

        if not selected_ids:
             # If LLM fails, pick random 5
             selected_ids = [q[0] for q in all_questions[:5]]

        # Save to Pool
        for q_id in selected_ids:
            c.execute("INSERT INTO job_question_pool (job_title, question_id) VALUES (%s, %s)", (job_title, q_id))
        
        conn.commit()
        
        # Return text
        c.execute(f"SELECT question FROM interview_answer WHERE id = ANY(%s)", (selected_ids,))
        questions = [r[0] for r in c.fetchall()]
        conn.close()
        return questions

    except Exception as e:
        logger.error(f"LLM Pool Creation Error: {e}")
        conn.close()
        return ["자기소개를 부탁드립니다.", "성격의 장단점은 무엇인가요?"]



class IdCheckRequest(BaseModel):
    id_name: str

# --- API Endpoints ---

@app.post("/api/check-id")
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


@app.post("/api/register")
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

@app.post("/api/login")
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

@app.post("/api/verify-password")
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

@app.get("/api/user/{id_name}")
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

@app.put("/api/user/{id_name}")
def update_user_info(id_name: str, data: UserUpdate):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        # Password check removed as requested
        # c.execute('SELECT pw FROM users WHERE id_name = %s', (id_name,))
        # ... validation removed ...
        
        c.execute('''
            UPDATE users SET email = %s, phone = %s, address = %s WHERE id_name = %s
        ''', (data.email, data.phone, data.address, id_name))
        conn.commit()
        return {"success": True, "message": "정보가 수정되었습니다."}
    finally:
        conn.close()

@app.post("/api/change-password")
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

@app.get("/api/jobs")
def get_jobs():
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT id, title, job, deadline, content, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement ORDER BY created_at DESC")
        rows = c.fetchall()
        return {"success": True, "jobs": [dict(row) for row in rows]}
    finally:
        conn.close()

@app.get("/api/jobs/{id}")
def get_job_detail(id: int):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT id, title, job, deadline, content, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement WHERE id = %s", (id,))
        row = c.fetchone()
        if row:
            return {"success": True, "job": dict(row)}
        else:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    finally:
        conn.close()

@app.post("/api/jobs")
def create_job(job: JobCreate):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO interview_announcement (title, job, deadline, content, id_name)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (job.title, job.job, job.deadline, job.content, job.id_name))
        new_id = c.fetchone()[0]
        conn.commit()
        return {"success": True, "message": "공고가 등록되었습니다.", "id": new_id}
    finally:
        conn.close()

@app.put("/api/jobs/{id}")
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
            SET title = %s, job = %s, deadline = %s, content = %s
            WHERE id = %s
        ''', (job.title, job.job, job.deadline, job.content, id))
        conn.commit()
        return {"success": True, "message": "공고가 수정되었습니다."}
    finally:
        conn.close()

@app.delete("/api/jobs/{id}")
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

@app.post("/api/upload/resume")
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

# --- Logic: Start Interview ---
@app.post("/api/interview/start")
def start_interview(data: StartInterviewRequest):
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
        c.execute("SELECT COUNT(DISTINCT interview_number) FROM Interview_Progress WHERE applicant_id = %s", (data.id_name,))
        interview_count = c.fetchone()[0]
        session_name = f"면접-{interview_count + 1}"

        # Save to DB
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question, applicant_id, session_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (interview_number, applicant_name, data.job_title, resume_text[:1000], first_question, data.id_name, session_name))
        # Note: Saving truncated resume text to avoid huge DB size if text is long.
        
        conn.commit()
        
        return {
            "success": True,
            "interview_number": interview_number,
            "question": first_question,
            "session_name": session_name
        }
        
    except Exception as e:
        logger.error(f"Start Interview Error: {e}")
        return {"success": False, "message": "면접 시작 중 오류가 발생했습니다."}
    finally:
        conn.close()

# --- Logic: Submit Answer & Next Question ---
@app.post("/api/interview/answer")
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
        applicant_answer = ""
        try:
            # Check file size before sending to Whisper (optional but good)
            file_size = os.path.getsize(audio_path)
            if file_size < 100: # Too small to be a valid audio file
                 applicant_answer = "답변 없음"
            else:
                with open(audio_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        language="ko",
                        prompt="이것은 면접 지원자의 답변입니다. 절대로 추측하지 마세요. ai 개인적인 생각을 넣지 마세요. 오직 지원자의 명확한 답변 내용만 텍스트로 변환해 주세요."
                    )
                applicant_answer = transcript.text.strip()
        except Exception as stt_e:
            logger.error(f"STT Error: {stt_e}")
            # If the error message mentions 'too short', it's essentially 'No Answer'
            applicant_answer = "답변 없음"
        
        # Hallucination Filtering Removed as per request
        # hallucination_phrases logic was here
        
        # Check if answer is too short to be a valid answer (e.g. just punctuation)
        if len(applicant_answer) < 2:
            logger.info(f"Filtered Short Noise or Empty: {applicant_answer}")
            applicant_answer = "답변 없음"
        
        # 2. Find Previous Question (The one with this interview number and NO answer yet)
        conn = get_db_connection()
        c = conn.cursor()
        
        # We find the latest row for this interview
        c.execute("""
            SELECT id, Create_Question, Resume, applicant_id FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id DESC LIMIT 1
        """, (interview_number,))
        row = c.fetchone()
        
        if not row:
             # Should not happen
             logger.error("No active question found.")
             conn.close()
             return {"success": False, "message": "진행 중인 면접을 찾을 수 없습니다."}
             
        current_row_id = row[0]
        prev_question = row[1]
        resume_context = row[2] if row[2] else ""
        applicant_id = row[3] # Get applicant_id from progress record
        
        # Get session_name from current row to propagate it
        c.execute("SELECT session_name FROM Interview_Progress WHERE id = %s", (current_row_id,))
        session_name = c.fetchone()[0]
        
        # 3. Evaluate & 4. Next Question
        # 3. Determine Question Phase
        # Count how many questions have been asked including this one
        c.execute("SELECT COUNT(*) FROM Interview_Progress WHERE Interview_Number = %s", (interview_number,))
        current_q_count = c.fetchone()[0]
        logger.info(f"Answer Submission. Interview={interview_number}, Count={current_q_count}")
        
        # Phase Logic
        # Q1 (Done): Self Intro
        # Q2 ~ Q6 (Next): Technical Questions (Target: 5 Total)
        # Q7 ~ Q11 (Next): Personality Questions (Target: 5 Total)
        # Q12 (Next): Closing
        
        next_phase = ""
        if current_q_count < 6:
            next_phase = "직무 기술(Technical Skill)"
        elif current_q_count < 11:
            next_phase = "인성 및 가치관(Personality & Culture Fit)"
        elif current_q_count == 11:
            next_phase = "마무리(Closing)"
        else:
            next_phase = "END"

        # 4. Evaluate & Generate Next Question
        if next_phase == "END":
             evaluation_prompt = f"""
             [상황]
             직무: {job_title}
             면접자: {applicant_name}
             마무리 질문에 대한 답변: {applicant_answer}
             
             [작업]
             - 만약 답변이 "답변 없음"이라면, "지원자가 마지막 발언을 하지 않았습니다."라고 평가하고 성실성 부분에서 낮은 평가를 주세요.
             - 답변이 있다면 그 내용을 바탕으로 간단히 평가해주세요. (관리자용)
             """
             # Simple eval for last answer
             completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": evaluation_prompt}]
             )
             evaluation = completion.choices[0].message.content
             next_question = "면접이 종료되었습니다. 수고하셨습니다."
             logger.info(f"Phase END reached. current_q_count={current_q_count}")
             
        else:
            prompt = f"""
            [상황]
            직무: {job_title}
            면접자: {applicant_name}
            현재 진행 단계: {current_q_count}번째 질문 완료. 다음은 {current_q_count + 1}번째 질문인 [{next_phase}] 단계입니다.
            
            [이전 질문]
            {prev_question}
            
            [지원자 답변]
            {applicant_answer}
            
            [작업 1] 이 답변을 평가해주세요. (관리자용, 지원자에게 보이지 않음, 장단점 및 점수 포함)
            - 만약 답변이 "답변 없음"이라면, "답변을 하지 않았습니다."라고 평가하고 점수를 매우 낮게(0-10점 사이) 책정하세요.
            - 답변이 중단되었거나 불완전하더라도 지금까지 말한 음성 답변만으로 최선을 다해 평가하세요.
            
            [작업 2] 다음 질문을 생성해주세요.
            - 단계: {next_phase}
            - {next_phase}에 맞는 질문을 해주세요.
            - 만약 '마무리(Closing)' 단계라면, "마지막으로 하고 싶은 말이 있나요?" 또는 "면접을 마치며 궁금한 점이 있나요?" 같은 질문을 해주세요.
            - 이전 답변 내용과 자연스럽게 이어지거나, 새로운 주제로 전환해도 됩니다.
            
            반드시 JSON 형식으로 반환해주세요.
            {{
                "evaluation": "평가 내용...",
                "next_question": "다음 질문..."
            }}
            """
            
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            content = completion.choices[0].message.content
            # Robust JSON Parsing
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            
            try:
                result = json.loads(content)
                evaluation = result.get("evaluation", "평가 불가")
                next_question = result.get("next_question", "다음 질문을 준비 중입니다.")
            except json.JSONDecodeError:
                 logger.error(f"JSON Parse Error. Content: {content}")
                 evaluation = "평가 실패"
                 next_question = "다음 질문으로 넘어가겠습니다."
        
        # 5. Update DB (Current Row)
        c.execute("""
            UPDATE Interview_Progress 
            SET Question_answer = %s, answer_time = %s, Answer_Evaluation = %s
            WHERE id = %s
        """, (applicant_answer, answer_time, evaluation, current_row_id))
        
        # Check if interview is finished
        interview_finished = False
        if next_phase == "END":
             interview_finished = True
             # Trigger Final Analysis (Background Task)
             background_tasks.add_task(analyze_interview_result, interview_number, job_title, applicant_name, applicant_id)
        else:
            # 6. Insert New Row (Next Question) ONLY if not finished
            # resume context is copied for simplicity or we can just ignore it for subsequent rows
            c.execute('''
                INSERT INTO Interview_Progress (
                    Interview_Number, Applicant_Name, Job_Title, Create_Question, Resume, applicant_id, session_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (interview_number, applicant_name, job_title, next_question, resume_context, applicant_id, session_name))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "next_question": next_question,
            "transcript": applicant_answer,
            "interview_finished": interview_finished,
            "session_name": session_name
        }
        
    except Exception as e:
        logger.error(f"Answer Submission Error: {e}")
        return {"success": False, "message": f"오류 발생: {str(e)}"}

# --- Logic: Analyze Interview Result ---
def analyze_interview_result(interview_number, job_title, applicant_name, applicant_id):
    logger.info(f"Analyzing interview result for {interview_number}...")
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Fetch Announcement Details (Title & Job Description)
        # We assume job_title passed here matches the 'title' in interview_announcement
        c.execute("""
            SELECT title, job 
            FROM interview_announcement 
            WHERE title = %s 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (job_title,))
        announcement_row = c.fetchone()
        
        announcement_title = announcement_row[0] if announcement_row else job_title
        announcement_job = announcement_row[1] if announcement_row else "직무 내용 없음"

        # Fetch all Q&A and session_name
        c.execute("""
            SELECT Create_Question, Question_answer, Answer_Evaluation, session_name
            FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id ASC
        """, (interview_number,))
        rows = c.fetchall()
        
        session_name = rows[0][3] if rows else "알 수 없음" # session_name is same for all rows in a session
        
        interview_log = ""
        for row in rows:
            q = row[0]
            a = row[1] if row[1] else "답변 없음"
            e = row[2] if row[2] else "평가 없음"
            interview_log += f"Q: {q}\nA: {a}\nEval: {e}\n\n"
            
        prompt = f"""
        당신은 면접관입니다. 다음은 지원자의 전체 면접 기록입니다.
        
        [면접 정보]
        지원자: {applicant_name}
        지원 직무: {announcement_title}
        직무 내용: {announcement_job}
        
        [면접 기록]
        {interview_log}
        
        [요청 사항]
        위 기록을 바탕으로 다음 4가지 항목을 평가하고 점수(0~100점)를 매겨주세요.
        1. 기술(직무 적합성): Tech
        2. 문제해결능력: Problem Solving
        3. 의사소통능력: Communication
        4. 비언어적 요소(태도, 성실성 등 답변 내용에서 유추): Non-verbal
        
        그리고 최종적으로 '합격' 또는 '불합격'을 결정해주세요.
        
        반드시 JSON 형식으로 반환해주세요.
        {{
            "tech_score": 85,
            "tech_eval": "기술적 이해도가 높음...",
            "problem_solving_score": 80,
            "problem_solving_eval": "논리적으로 접근함...",
            "communication_score": 90,
            "communication_eval": "명확하게 의사를 전달함...",
            "non_verbal_score": 88,
            "non_verbal_eval": "성실한 태도가 보임...",
            "pass_fail": "합격"
        }}
        pass_fail 값은 반드시 "합격" 또는 "불합격" 이어야 합니다.
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = completion.choices[0].message.content
        result = json.loads(content)
        
        pass_fail = result.get("pass_fail", "불합격")
        if pass_fail not in ["합격", "불합격"]:
             pass_fail = "불합격"
             
        c.execute("""
            INSERT INTO Interview_Result (
                interview_number, 
                tech_score, tech_eval, 
                problem_solving_score, problem_solving_eval, 
                communication_score, communication_eval, 
                non_verbal_score, non_verbal_eval, 
                pass_fail,
                announcement_title, announcement_job,
                applicant_id, session_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            interview_number,
            int(result.get("tech_score", 0)), result.get("tech_eval", ""),
            int(result.get("problem_solving_score", 0)), result.get("problem_solving_eval", ""),
            int(result.get("communication_score", 0)), result.get("communication_eval", ""),
            int(result.get("non_verbal_score", 0)), result.get("non_verbal_eval", ""),
            pass_fail,
            announcement_title, announcement_job,
            applicant_id, session_name
        ))
        
        conn.commit()
        logger.info(f"Interview result saved for {interview_number}")
        
    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        # Ensure we write a failure record so frontend doesn't hang
        try:
             c.execute("""
                INSERT INTO Interview_Result (
                    interview_number, 
                    tech_score, tech_eval, 
                    problem_solving_score, problem_solving_eval, 
                    communication_score, communication_eval, 
                    non_verbal_score, non_verbal_eval, 
                    pass_fail,
                    announcement_title, announcement_job,
                    applicant_id, session_name
                ) VALUES (%s, 0, '분석 실패', 0, '분석 실패', 0, '분석 실패', 0, '분석 실패', '보류', %s, '분석 중 오류 발생', %s, %s)
            """, (interview_number, job_title, applicant_id, session_name))
             conn.commit()
        except Exception as db_e:
             logger.error(f"Failed to write error record: {db_e}")

    finally:
        conn.close()

@app.get("/api/interview/result/{interview_number}")
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

@app.get("/api/interview-results/{id_name}")
def get_interview_results(id_name: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT announcement_title, announcement_job, 
                   to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as interview_time, 
                   pass_fail
            FROM Interview_Result 
            WHERE applicant_id = %s 
            ORDER BY created_at DESC
        """
        c.execute(query, (id_name,))
        rows = c.fetchall()
        return {"success": True, "results": [dict(row) for row in rows]}
    finally:
        conn.close()

@app.get("/api/admin/applicants")
def get_admin_applicants():
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        # Join Interview_Result with users to get applicant names
        query = """
            SELECT r.interview_number, r.applicant_id, u.name as applicant_name, 
                   r.announcement_title, r.announcement_job, r.pass_fail, 
                   to_char(r.created_at, 'YYYY-MM-DD HH24:MI:SS') as interview_time
            FROM Interview_Result r
            JOIN users u ON r.applicant_id = u.id_name
            ORDER BY r.created_at DESC
        """
        c.execute(query)
        rows = c.fetchall()
        return {"success": True, "applicants": [dict(row) for row in rows]}
    finally:
        conn.close()

@app.get("/api/admin/applicant-details/{interview_number}")
def get_applicant_details(interview_number: str):
    conn = get_db_connection()
    try:
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Get Interview Result
        c.execute("SELECT * FROM Interview_Result WHERE interview_number = %s", (interview_number,))
        result = c.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="면접 결과를 찾을 수 없습니다.")
        
        # 2. Get Interview Q&A Progress
        c.execute("""
            SELECT Create_Question, Question_answer, Answer_Evaluation, answer_time
            FROM Interview_Progress 
            WHERE Interview_Number = %s 
            ORDER BY id ASC
        """, (interview_number,))
        progress = c.fetchall()
        
        # 3. Get Resume Text
        # First check interview_information for original PDF text
        c.execute("""
            SELECT applicant_id, announcement_job FROM Interview_Result WHERE interview_number = %s
        """, (interview_number,))
        res_info = c.fetchone()
        
        resume_text = ""
        if res_info:
            c.execute("""
                SELECT resume FROM interview_information 
                WHERE id_name = %s AND job = %s 
                ORDER BY created_at DESC LIMIT 1
            """, (res_info['applicant_id'], res_info['announcement_job']))
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
            "resume_text": resume_text
        }
    finally:
        conn.close()


# --- Static Files ---
app.mount("/", StaticFiles(directory=".", html=True), name="static")

def open_browser():
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    print("FastAPI Server running on http://localhost:5000")
    Timer(1, open_browser).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
