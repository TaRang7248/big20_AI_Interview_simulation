import os
import uuid
import shutil
import psycopg2
import json
import logging
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    pw: str
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


# --- API Endpoints ---

@app.post("/api/register")
def register(user: UserRegister):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('SELECT id_name FROM users WHERE id_name = %s', (user.id_name,))
        if c.fetchone():
            raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
        
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
        c.execute('SELECT pw FROM users WHERE id_name = %s', (id_name,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        if row[0] != data.pw:
            raise HTTPException(status_code=401, detail="비밀번호가 일치하지 않습니다.")
        
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
        
        # Get Job Questions Pool
        questions_pool = get_job_questions(data.job_title)
        
        # Determine Applicant Name
        c.execute("SELECT name FROM users WHERE id_name = %s", (data.id_name,))
        user_row = c.fetchone()
        applicant_name = user_row[0] if user_row else "지원자"

        # Generate 1st Question
        prompt = f"""
        당신은 면접관입니다. 
        직무: {data.job_title}
        지원자 이름: {applicant_name}
        
        [이력서 내용]
        {resume_text[:2000]}... (생략)
        
        [질문 풀]
        {questions_pool}
        
        위 정보를 바탕으로 면접을 시작하는 첫 번째 질문을 하나만 만들어주세요. 
        인사말과 함께 자연스럽게 질문해주세요. 한국어로 해주세요.
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        first_question = completion.choices[0].message.content.strip()
        
        # Save to DB
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Resume, Create_Question
            ) VALUES (%s, %s, %s, %s, %s)
        ''', (interview_number, applicant_name, data.job_title, resume_text[:1000], first_question))
        # Note: Saving truncated resume text to avoid huge DB size if text is long.
        
        conn.commit()
        
        return {
            "success": True,
            "interview_number": interview_number,
            "question": first_question
        }
        
    except Exception as e:
        logger.error(f"Start Interview Error: {e}")
        return {"success": False, "message": "면접 시작 중 오류가 발생했습니다."}
    finally:
        conn.close()

# --- Logic: Submit Answer & Next Question ---
@app.post("/api/interview/answer")
async def submit_answer(
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
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko"
            )
        applicant_answer = transcript.text
        
        # 2. Find Previous Question (The one with this interview number and NO answer yet)
        conn = get_db_connection()
        c = conn.cursor()
        
        # We find the latest row for this interview
        c.execute("""
            SELECT id, Create_Question, Resume FROM Interview_Progress 
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
        
        # 3. Evaluate & 4. Next Question
        prompt = f"""
        [상황]
        직무: {job_title}
        면접자: {applicant_name}
        
        [이전 질문]
        {prev_question}
        
        [지원자 답변]
        {applicant_answer}
        
        [작업 1] 이 답변을 평가해주세요. (관리자용, 지원자에게 보이지 않음, 장단점 및 점수 포함)
        [작업 2] 답변 내용을 바탕으로 꼬리 질문을 하거나, 다른 주제로 넘어가는 다음 면접 질문을 하나만 생성해주세요.
        
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
        
        result = json.loads(completion.choices[0].message.content)
        evaluation = result.get("evaluation", "평가 불가")
        next_question = result.get("next_question", "면접을 마칩니다.")
        
        # 5. Update DB (Current Row)
        c.execute("""
            UPDATE Interview_Progress 
            SET Question_answer = %s, answer_time = %s, Answer_Evaluation = %s
            WHERE id = %s
        """, (applicant_answer, answer_time, evaluation, current_row_id))
        
        # 6. Insert New Row (Next Question)
        # resume context is copied for simplicity or we can just ignore it for subsequent rows
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, Create_Question, Resume
            ) VALUES (%s, %s, %s, %s, %s)
        ''', (interview_number, applicant_name, job_title, next_question, resume_context))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "next_question": next_question,
            "transcript": applicant_answer # Optional: show back to user?
        }
        
    except Exception as e:
        logger.error(f"Answer Submission Error: {e}")
        return {"success": False, "message": f"오류 발생: {str(e)}"}


# --- Static Files ---
app.mount("/", StaticFiles(directory=".", html=True), name="static")

def open_browser():
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    print("FastAPI Server running on http://localhost:5000")
    Timer(1, open_browser).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
