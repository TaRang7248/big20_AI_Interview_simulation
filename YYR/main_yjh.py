import sys
import os
import uuid
import traceback
import shutil  # 파일 저장용

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware  # <--- 이거 추가!
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from fastapi.staticfiles import StaticFiles

# 프로젝트 모듈 임포트
from YYR.agents.interview_graph import app as interview_graph
from YYR.services.voice_service import transcribe_audio
from YYR.services.tts_service import generate_audio
from YYR.database import get_db, SessionLocal
# [수정] EvaluationReport 모델 추가 임포트
from YYR.models import InterviewSession, Transcript, EvaluationReport
# [수정] 리포트 생성 서비스 추가 임포트ㄹ
from YYR.services.report_service import generate_interview_report
# [추가] 비디오 면접(Video Interview)
from YYR.services.vision_service import analyze_face_emotion
# [추가] 업로드 API 추가 및 RAG 연동 임포트
from YYR.services.rag_service import process_resume_pdf, get_relevant_context
# 이전 세션이 준 새로운 import
from sqlalchemy import text
from YYR.models import User


from passlib.context import CryptContext
import bcrypt as _bcrypt
from pydantic import BaseModel, Field
from typing import Literal, Optional


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())

# 1. FastAPI 앱 초기화
app = FastAPI(
    title="AI Interview Agent (YJH)",
    description="LangGraph + RAG + DB + Voice + Report (Full Version)",
    version="1.0.0"
)

# YYR 폴더 기준으로 generated_audio 경로 통일
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "generated_audio")

os.makedirs(AUDIO_DIR, exist_ok=True)

app.mount("/generated_audio", StaticFiles(directory=AUDIO_DIR), name="generated_audio")

# CORS 미들웨어 설정 (app 생성 바로 아래에 추가)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 주소 허용 (보안상 로컬 개발용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 데이터 모델 정의
class ChatRequest(BaseModel):
    user_input: str
    thread_id: str = "session_1"

class TextChatRequest(BaseModel):
    user_input: str
    thread_id: str
    role: Literal["ux", "tech", "data"] = "tech"   # ✅ data 추가

class TextChatResponse(BaseModel):
    status: str
    thread_id: str
    user_text: str
    ai_text: str
    audio_url: str | None = None
    is_finished: bool = False

class ChatResponse(BaseModel):
    response: str
    current_phase: str
    question_count: int


# --- [Helper] DB 저장 함수 ---
from collections import defaultdict
from datetime import datetime

# ✅ 설정: 이 개수 미만이면 DB에 저장하지 않음(임시 버퍼만)
MIN_TRANSCRIPTS_TO_PERSIST = 4  # human/ai 합쳐서 4개 이상이면 저장 시작

# ✅ 임시 버퍼: thread_id별로 (sender, content, timestamp) 쌓기
_TRANSCRIPT_BUFFER = defaultdict(list)
_PERSIST_ENABLED = set()  # 저장이 "활성화"된 thread_id 집합


def save_transcript(db, thread_id: str, sender: str, content: str):
    """
    (개선) 짧은 테스트 대화는 DB에 저장하지 않기 위해 버퍼링.
    - thread_id별로 임시로 쌓아두다가,
    - 누적 개수가 MIN_TRANSCRIPTS_TO_PERSIST 이상이 되면
      -> 세션 생성 + 버퍼 전체를 DB에 한번에 저장하고,
      -> 이후부터는 들어오는 대화는 즉시 DB에 저장.
    """
    try:
        ts = datetime.now()

        # 0) 이미 저장 활성화된 thread_id면 즉시 DB 저장
        if thread_id in _PERSIST_ENABLED:
            session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
            if not session:
                print(f"🆕 [DB] 새 세션 생성: {thread_id}")
                session = InterviewSession(thread_id=thread_id, candidate_name="Unknown")
                db.add(session)
                db.commit()
                db.refresh(session)

            transcript = Transcript(session_id=session.id, sender=sender, content=content)
            db.add(transcript)
            db.commit()
            print(f"💾 [DB 저장] {sender}: {content[:30]}...")
            return

        # 1) 아직 활성화 전이면 버퍼에만 쌓기
        _TRANSCRIPT_BUFFER[thread_id].append((sender, content, ts))
        buffered_count = len(_TRANSCRIPT_BUFFER[thread_id])
        print(f"🧪 [BUFFER] {thread_id} buffered={buffered_count} (DB 저장 보류)")

        # 2) 기준 넘으면: 세션 생성 + 버퍼 전체 DB 저장 + 저장 활성화
        if buffered_count >= MIN_TRANSCRIPTS_TO_PERSIST:
            session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
            if not session:
                print(f"🆕 [DB] 새 세션 생성(버퍼 flush): {thread_id}")
                session = InterviewSession(thread_id=thread_id, candidate_name="Unknown")
                db.add(session)
                db.commit()
                db.refresh(session)

            # 버퍼에 쌓인 것들을 순서대로 모두 저장
            for s, c, _ in _TRANSCRIPT_BUFFER[thread_id]:
                db.add(Transcript(session_id=session.id, sender=s, content=c))
            db.commit()

            # 활성화 및 버퍼 비우기
            _PERSIST_ENABLED.add(thread_id)
            _TRANSCRIPT_BUFFER.pop(thread_id, None)

            print(f"✅ [DB] 버퍼 flush 완료 + 저장 활성화: {thread_id}")

    except Exception as e:
        print(f"❌ [DB 저장 실패] {e}")
        db.rollback()

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/signup")
def signup(req: SignupRequest):
    db = SessionLocal()
    try:
        # 이미 있는 이메일인지 확인
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 사용 중인 이메일이에요.")
        
        hashed_pw = hash_password(req.password)
        user = User(email=req.email, hashed_password=hashed_pw, name=req.name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"status": "success", "user_id": user.id, "email": user.email, "name": user.name}
    finally:
        db.close()

@app.post("/auth/login")
def login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == req.email).first()
        if not verify_password(req.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸어요.")
        
        return {
            "status": "success",
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    finally:
        db.close()

# 3. 헬스 체크
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "AI 면접관(Voice+DB+Report) 준비 완료."}


# 4. 텍스트 대화 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """텍스트로 대화하고 DB에 저장합니다."""
    db = SessionLocal()  # DB 세션 열기
    try:
        # [저장] 사용자 입력
        save_transcript(db, request.thread_id, "human", request.user_input)

        # LangGraph 실행
        config = {"configurable": {"thread_id": request.thread_id}}
        inputs = {"messages": [HumanMessage(content=request.user_input)]}

        result = interview_graph.invoke(inputs, config=config)
        last_message = result["messages"][-1]

        # [저장] AI 응답
        save_transcript(db, request.thread_id, "ai", last_message.content)

        return ChatResponse(
            response=last_message.content,
            current_phase=result.get("phase", "unknown"),
            question_count=result.get("question_count", 0)
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()  # DB 세션 닫기

@app.post("/chat/text", response_model=TextChatResponse)
async def chat_text_with_tts(req: TextChatRequest):
    """
    텍스트 입력 -> LangGraph -> TTS -> JSON 반환
    (Web Speech API 프론트와 연결용)
    """
    db = SessionLocal()
    try:
        user_text = (req.user_input or "").strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="user_input is empty")

        # 1) DB 저장 (human)
        save_transcript(db, req.thread_id, "human", user_text)

        # 2) LangGraph
        config = {"configurable": {"thread_id": req.thread_id}}
        inputs = {
            "messages": [HumanMessage(content=user_text)],
            "role": req.role,   # ✅ role을 LangGraph state로 전달
            }
        result = interview_graph.invoke(inputs, config=config)

        ai_text = result["messages"][-1].content

        # 3) DB 저장 (ai)
        save_transcript(db, req.thread_id, "ai", ai_text)

                # 4) TTS 생성
        output_filename = f"response_{uuid.uuid4()}.mp3"
        audio_result = await generate_audio(ai_text, output_file=output_filename)

        # 5) 프론트가 접근할 URL 만들기 (안전 처리)
        audio_url = None
        if audio_result:
            # (A) generate_audio가 이미 "/generated_audio/xxx.mp3" 형태로 주는 경우
            if isinstance(audio_result, str) and audio_result.startswith("/generated_audio/"):
                audio_url = audio_result

            # (B) generate_audio가 파일 경로(C:\... / .../generated_audio/xxx.mp3)를 주는 경우
            else:
                # 파일이 실제로 존재하면, 현재 서버의 generated_audio 폴더로 복사(필요시)
                if isinstance(audio_result, str) and os.path.exists(audio_result):
                    target_path = os.path.join("generated_audio", output_filename)

                    # 같은 파일이면 복사 생략, 다르면 복사
                    if os.path.abspath(audio_result) != os.path.abspath(target_path):
                        shutil.copy(audio_result, target_path)

                # 어쨌든 서버는 /generated_audio 로 마운트되어 있으니 이 URL로 접근
                audio_url = f"/generated_audio/{output_filename}"
                print("✅ [TTS] target_path =", target_path)
                print("✅ [TTS] exists? =", os.path.exists(target_path))

        print(f"🔍 [result keys] {result.keys()}")
        print(f"🔢 [question_count] {result.get('question_count', 0)}")
        is_finished = result.get("question_count", 0) >= 7
        print(f"🏁 [is_finished] {is_finished}")

        return TextChatResponse(
            status="success",
            thread_id=req.thread_id,
            user_text=user_text,
            ai_text=ai_text,
            audio_url=audio_url,
            is_finished=is_finished
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 5. 음성 대화 (Audio -> Audio) 엔드포인트
@app.post("/chat/voice/audio")
async def chat_voice_audio_endpoint(
    file: UploadFile = File(...),
    thread_id: str = "voice_session_final_test"  # 기본값 통일
):
    """
    [Full Duplex] 음성 파일 업로드 -> STT -> LangGraph -> TTS -> 음성 파일 반환
    """
    db = SessionLocal()
    try:
        # (디버그) content-type 확인하고 싶으면 아래 한 줄을 잠깐 켜도 됨
        # print("📌 upload content_type =", file.content_type, "filename =", file.filename)

        # 1. STT 변환 (Google)
        audio_bytes = await file.read()
        user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
        print(f"🎤 User(STT): {user_text}")

        if not user_text.strip():
            raise HTTPException(status_code=400, detail="음성이 인식되지 않았습니다.")

        # [저장] 사용자 입력
        save_transcript(db, thread_id, "human", user_text)

        # ---------------------------------------------------------
        # [RAG 핵심 로직] 이력서에서 관련 내용 검색
        retrieved_context = get_relevant_context(thread_id, user_text)

        final_input_text = user_text
        if retrieved_context:
            print(f"📚 [RAG 검색 성공] 이력서 내용 참고함 (길이: {len(retrieved_context)})")
            # 프롬프트 엔지니어링: 사용자 몰래 컨텍스트를 주입
            final_input_text = f"""
            [System Note: The following is relevant information retrieved from the candidate's resume. Use it to formulate your response or next question.]
            --- Resume Context ---
            {retrieved_context}
            ----------------------

            User's Input: {user_text}
            """
        # ---------------------------------------------------------

        # 2. LangGraph 실행 (주입된 텍스트 전달)
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [HumanMessage(content=final_input_text)]}

        result = interview_graph.invoke(inputs, config=config)
        ai_text = result["messages"][-1].content
        print(f"🤖 AI(Logic): {ai_text}")

        # [저장] AI 응답
        save_transcript(db, thread_id, "ai", ai_text)

        # 3. TTS 변환 (OpenAI)
        output_filename = f"response_{uuid.uuid4()}.mp3"
        audio_path = await generate_audio(ai_text, output_file=output_filename)

        # 🔴 mp3를 정적 폴더로 복사
        target_path = os.path.join(AUDIO_DIR, output_filename)
        shutil.copy(audio_path, target_path)

        # 4. 파일 반환
        return {
            "status": "success",
            "thread_id": thread_id,
            "user_text": user_text,
            "ai_text": ai_text,
            "audio_url": f"/generated_audio/{output_filename}",
            }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 6. [신규 추가] 면접 결과 리포트 생성 API
@app.post("/report/{thread_id}")
async def create_report_endpoint(thread_id: str):
    """
    특정 세션(thread_id)의 대화 기록을 분석하여 상세 평가 리포트를 생성합니다.
    """
    db = SessionLocal()
    try:
        # 1. 세션 조회
        session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

        # 2. 대화 기록 조회
        transcripts = db.query(Transcript).filter(Transcript.session_id == session.id).order_by(Transcript.timestamp).all()

        if not transcripts:
            raise HTTPException(status_code=400, detail="대화 기록이 없습니다.")

        print(f"📊 [리포트 생성 시작] 세션: {thread_id}, 대화 수: {len(transcripts)}건")

        # 3. LLM 분석 실행 (Rubric 기반)
        report_data = await generate_interview_report(transcripts)

        if not report_data:
            raise HTTPException(status_code=500, detail="리포트 생성 실패")

        # 4. 결과 DB 저장
        report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session.id).first()

        # 점수 형변환 (float -> int)
        total_score_int = int(report_data.get("total_weighted_score", 0))

        if not report:
            report = EvaluationReport(
                session_id=session.id,
                total_score=total_score_int,
                technical_score=report_data["hard_skill"]["score"],
                communication_score=report_data["communication"]["score"],
                summary=report_data["overall_summary"],
                details=report_data  # 전체 상세 데이터(JSON) 저장
            )
            db.add(report)
        else:
            # 기존 리포트 갱신
            report.total_score = total_score_int
            report.technical_score = report_data["hard_skill"]["score"]
            report.communication_score = report_data["communication"]["score"]
            report.summary = report_data["overall_summary"]
            report.details = report_data

        db.commit()
        db.refresh(report)

        print(f"✅ [리포트 저장 완료] ID: {report.id}, 점수: {total_score_int}점")
        return {"status": "success", "report": report_data}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# [신규] 비전(얼굴) 분석 엔드포인트
@app.post("/analyze/face")
async def analyze_face_endpoint(file: UploadFile = File(...)):
    """
    면접자의 스냅샷(이미지)을 받아 감정을 분석합니다. (DeepFace)
    """
    try:
        image_bytes = await file.read()
        result = analyze_face_emotion(image_bytes)

        print(f"👁️ [Vision 분석 결과]: {result.get('dominant_emotion')}")

        return {
            "status": "success",
            "analysis": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# [신규] 이력서 PDF 업로드 API
@app.post("/upload/resume")
async def upload_resume(
    file: UploadFile = File(...),
    thread_id: str = "voice_session_final_test"
):
    """
    PDF 이력서를 업로드하고 RAG용 벡터 DB를 생성합니다.
    """
    try:
        # 1. 파일 임시 저장
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{thread_id}_{file.filename}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. RAG 처리 (텍스트 추출 및 임베딩)
        success = process_resume_pdf(thread_id, file_path)

        if not success:
            raise HTTPException(status_code=500, detail="이력서 처리 중 오류 발생")

        return {"status": "success", "message": "이력서 분석 완료! 이제 맞춤형 질문이 가능합니다."}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# [ 이전 세션이 준 새로운 코드 ] ============================
@app.get("/report/{thread_id}/result")
async def get_report_result(thread_id: str):
    db = SessionLocal()
    try:
        session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="세션 없음")

        report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session.id).first()
        if not report:
            raise HTTPException(status_code=404, detail="리포트 없음")

        d = report.details  # JSON

        return {
            "session_id": session.id,
            "total_score": report.total_score,
            "final_result": d.get("final_result"),
            "summary": d.get("overall_summary"),
            "radar": [
                {"axis": "hard_skill", "label": "기술 역량", "score": d["hard_skill"]["score"]},
                {"axis": "problem_solving", "label": "문제 해결", "score": d["problem_solving"]["score"]},
                {"axis": "communication", "label": "커뮤니케이션", "score": d["communication"]["score"]},
                {"axis": "attitude", "label": "태도", "score": d["attitude"]["score"]},
            ],
            "feedback": {
                "hard_skill": d["hard_skill"],
                "problem_solving": d["problem_solving"],
                "communication": d["communication"],
                "attitude": d["attitude"]
            },
            "created_at": report.created_at
        }
    finally:
        db.close()


@app.get("/debug/db")
async def debug_db():
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT current_database() AS db, current_schema() AS schema")
        ).fetchone()
        return {"db": row[0], "schema": row[1]}
    finally:
        db.close()

@app.get("/admin/jobs")
async def list_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, job_code, title, role, status, applicants, updated_at, created_at
            FROM jobs
            ORDER BY created_at DESC
        """)).mappings().all()

        # rows는 RowMapping 리스트라 그대로 JSON으로 바꿔주면 됨
        return {"status": "success", "jobs": [dict(r) for r in rows]}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# [추가] 공고 등록 API (POST /admin/jobs)

class JobCreateRequest(BaseModel):
    job_code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    role: str = "tech"              # ✅ ux | tech | data
    status: str = "모집중"          # 모집중 | 마감 | 임시저장
    applicants: int = 0

@app.post("/admin/jobs")
async def create_job(payload: JobCreateRequest):
    db = SessionLocal()
    try:
        # job_code 중복이면 업데이트(UPSERT) / 없으면 삽입
        row = db.execute(
            text("""
                INSERT INTO jobs (job_code, title, role, status, applicants, updated_at, created_at)
                VALUES (:job_code, :title, :role, :status, :applicants, NOW(), NOW())
                ON CONFLICT (job_code) DO UPDATE
                SET title = EXCLUDED.title,
                    role = EXCLUDED.role,
                    status = EXCLUDED.status,
                    applicants = EXCLUDED.applicants,
                    updated_at = NOW()
                RETURNING id, job_code, title, role, status, applicants, updated_at, created_at
            """),
            {
                "job_code": payload.job_code.strip(),
                "title": payload.title.strip(),
                "role": payload.role,
                "status": payload.status,
                "applicants": int(payload.applicants or 0),
            }
        ).mappings().first()

        db.commit()
        return {"status": "success", "job": dict(row) if row else None}

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 다시 새로운 추가
@app.get("/report/session/{session_id}/result")
async def get_report_result_by_session_id(session_id: int):
    db = SessionLocal()
    try:
        report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="리포트 없음")

        d = report.details  # JSON

        return {
            "session_id": session_id,
            "total_score": report.total_score,
            "final_result": d.get("final_result"),
            "summary": d.get("overall_summary"),
            "radar": [
                {"axis": "hard_skill", "label": "기술 역량", "score": d["hard_skill"]["score"]},
                {"axis": "problem_solving", "label": "문제 해결", "score": d["problem_solving"]["score"]},
                {"axis": "communication", "label": "커뮤니케이션", "score": d["communication"]["score"]},
                {"axis": "attitude", "label": "태도", "score": d["attitude"]["score"]},
            ],
            "feedback": {
                "hard_skill": d["hard_skill"],
                "problem_solving": d["problem_solving"],
                "communication": d["communication"],
                "attitude": d["attitude"]
            },
            "created_at": report.created_at
        }
    finally:
        db.close()


# ✅ (중요) 직접 실행도 가능하게 하려면, 이 블록은 "맨 마지막"에 둔다.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("YYR.main_yjh:app", host="0.0.0.0", port=8001, reload=True)

@app.get("/user/{user_id}/sessions")
async def get_user_sessions(user_id: int):
    db = SessionLocal()
    try:
        sessions = db.execute(text("""
            SELECT s.id, s.thread_id, s.status, s.created_at,
                   r.total_score, r.details->>'final_result' as final_result
            FROM interview_sessions s
            LEFT JOIN evaluation_reports r ON r.session_id = s.id
            WHERE s.thread_id LIKE :pattern
            ORDER BY s.created_at DESC
            LIMIT 10
        """), {"pattern": f"session_{user_id}_%"}).mappings().all()

        return {"status": "success", "sessions": [dict(s) for s in sessions]}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()