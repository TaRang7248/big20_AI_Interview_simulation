import os
import uuid
import shutil
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import google.generativeai as genai
import uvicorn
import webbrowser
from threading import Timer

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = os.getenv("DB_PORT", "5432")
UPLOAD_FOLDER = 'uploads/resumes'
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    print("WARNING: GEMINI_API_KEY not found in .env. LLM features will not work.")
    model = None

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
        print(f"DB Connection Failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Existing tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id_name TEXT PRIMARY KEY,
                pw TEXT NOT NULL,
                name TEXT NOT NULL,
                dob TEXT,
                gender TEXT,
                email TEXT,
                address TEXT,
                phone TEXT,
                type TEXT DEFAULT 'applicant'
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS interview_announcement (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                job TEXT,
                deadline TEXT,
                content TEXT,
                id_name TEXT REFERENCES users(id_name),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS interview_information (
                id SERIAL PRIMARY KEY,
                id_name TEXT REFERENCES users(id_name),
                job TEXT,
                resume TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS interview_answer (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL
            )
        ''')

        # NEW: Interview_Progress Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS Interview_Progress (
                id SERIAL PRIMARY KEY,
                Interview_Number TEXT NOT NULL,
                Applicant_Name TEXT NOT NULL,
                Job_Title TEXT,
                Create_Question TEXT,
                Question_answer TEXT,
                answer_time TEXT,
                Answer_Evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"DB Init Error: {e}")
    finally:
        if conn: conn.close()

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
    id_name: Optional[str] = None # For verification

class StartInterviewRequest(BaseModel):
    id_name: str
    job_title: str

class AnswerSubmission(BaseModel):
    interview_number: str
    applicant_name: str
    job_title: str
    question: str
    answer: str
    answer_time: str

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
        print(f"Register Error: {e}")
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
        c.execute('''
            INSERT INTO interview_information (id_name, job, resume)
            VALUES (%s, %s, %s)
        ''', (id_name, job_title, filepath))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "이력서가 업로드되었습니다.", "filepath": filepath}
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail="파일 업로드 중 오류 발생")

# --- LLM Interview Logic ---

@app.post("/api/interview/start")
def start_interview(data: StartInterviewRequest):
    """
    Starts an interview session.
    Generates the first question based on the job title.
    """
    interview_number = str(uuid.uuid4())
    
    # Simple prompt for the first question
    prompt = f"당신은 {data.job_title} 직무의 면접관입니다. 지원자에게 할 첫 번째 질문을 한국어로 하나만 만들어주세요."
    
    try:
        if model:
            response = model.generate_content(prompt)
            question = response.text.strip()
        else:
            question = f"{data.job_title} 직무에 지원하게 된 동기는 무엇인가요? (LLM 미설정)"

        return {
            "success": True,
            "interview_number": interview_number,
            "question": question
        }
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"success": False, "message": "질문 생성 중 오류가 발생했습니다."}

@app.post("/api/interview/answer")
def submit_answer(data: AnswerSubmission):
    """
    Evaluates the answer and generates the next question.
    Saves everything to Interview_Progress.
    """
    
    # 1. Evaluate current answer
    eval_prompt = f"""
    질문: {data.question}
    지원자 답변: {data.answer}
    
    위 답변을 {data.job_title} 직무 지원자로서 평가해주세요.
    평가 내용은 지원자에게 보이지 않으므로 솔직하고 비판적으로 분석해주세요.
    점수 (10점 만점)와 구체적인 피드백을 포함해주세요.
    """
    
    # 2. Generate next question
    next_q_prompt = f"""
    이전 질문: {data.question}
    지원자 답변: {data.answer}
    
    이전 답변을 바탕으로 {data.job_title} 직무 면접을 이어갈 다음 꼬리 질문을 하나만 만들어주세요. 한국어로 해주세요.
    """

    try:
        evaluation = "LLM 미설정으로 인한 평가 불가"
        next_question = "다음 질문입니다. (LLM 미설정)"
        
        if model:
             eval_response = model.generate_content(eval_prompt)
             evaluation = eval_response.text.strip()
             
             next_q_response = model.generate_content(next_q_prompt)
             next_question = next_q_response.text.strip()

        # 3. Save to DB
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO Interview_Progress (
                Interview_Number, Applicant_Name, Job_Title, 
                Create_Question, Question_answer, answer_time, Answer_Evaluation
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            data.interview_number, data.applicant_name, data.job_title,
            data.question, data.answer, data.answer_time, evaluation
        ))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "next_question": next_question,
            "evaluation_saved": True
        }

    except Exception as e:
        print(f"Interview Process Error: {e}")
        return {"success": False, "message": "면접 진행 중 오류가 발생했습니다."}


# --- Static Files (Must be last) ---
app.mount("/", StaticFiles(directory=".", html=True), name="static")

def open_browser():
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    init_db()
    print("FastAPI Server running on http://localhost:5000")
    Timer(1, open_browser).start()
    uvicorn.run(app, host="0.0.0.0", port=5000)
