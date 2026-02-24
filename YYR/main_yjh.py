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

# 프로젝트 모듈 임포트
from YJH.agents.interview_graph import app as interview_graph
from YYR.services.voice_service import transcribe_audio
from YJH.services.tts_service import generate_audio
from YJH.database import get_db, SessionLocal
# [수정] EvaluationReport 모델 추가 임포트
from YJH.models import InterviewSession, Transcript, EvaluationReport
# [수정] 리포트 생성 서비스 추가 임포트
from YJH.services.report_service import generate_interview_report
# [추가] 비디오 면접(Video Interview)
from YJH.services.vision_service import analyze_face_emotion
# [추가] 업로드 API 추가 및 RAG 연동 임포트
from YJH.services.rag_service import process_resume_pdf, get_relevant_context
# 이전 세션이 준 새로운 import
from sqlalchemy import text

# 1. FastAPI 앱 초기화
app = FastAPI(
    title="AI Interview Agent (YJH)",
    description="LangGraph + RAG + DB + Voice + Report (Full Version)",
    version="1.0.0"
)

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


class ChatResponse(BaseModel):
    response: str
    current_phase: str
    question_count: int


# --- [Helper] DB 저장 함수 ---
def save_transcript(db, thread_id: str, sender: str, content: str):
    """대화 내용을 DB에 저장하고 로그를 출력합니다."""
    try:
        # 1. 세션 찾기 (없으면 생성)
        session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
        if not session:
            print(f"🆕 [DB] 새 세션 생성: {thread_id}")
            session = InterviewSession(thread_id=thread_id, candidate_name="Unknown")
            db.add(session)
            db.commit()
            db.refresh(session)

        # 2. 대화 기록 저장
        transcript = Transcript(session_id=session.id, sender=sender, content=content)
        db.add(transcript)
        db.commit()
        print(f"💾 [DB 저장] {sender}: {content[:30]}...")  # 로그 출력
    except Exception as e:
        print(f"❌ [DB 저장 실패] {e}")
        db.rollback()


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

        # 4. 파일 반환
        return FileResponse(audio_path, media_type="audio/mpeg", filename="ai_response.mp3")

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

# import sys
# import os
# import uuid
# import traceback
# import shutil # 파일 저장용

# # 프로젝트 루트 경로 설정
# sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

# from fastapi import FastAPI, HTTPException, UploadFile, File
# from fastapi.responses import FileResponse
# from fastapi.middleware.cors import CORSMiddleware # <--- 이거 추가!
# from pydantic import BaseModel
# from langchain_core.messages import HumanMessage

# # 프로젝트 모듈 임포트
# from YJH.agents.interview_graph import app as interview_graph
# from YYR.services.voice_service import transcribe_audio
# from YJH.services.tts_service import generate_audio
# from YJH.database import get_db, SessionLocal
# # [수정] EvaluationReport 모델 추가 임포트
# from YJH.models import InterviewSession, Transcript, EvaluationReport
# # [수정] 리포트 생성 서비스 추가 임포트
# from YJH.services.report_service import generate_interview_report
# # [추가] 비디오 면접(Video Interview)
# from YJH.services.vision_service import analyze_face_emotion
# # [추가] 업로드 API 추가 및 RAG 연동 임포트
# from YJH.services.rag_service import process_resume_pdf, get_relevant_context
# # 이전 세션이 준 새로운 import
# from sqlalchemy import text

# # 1. FastAPI 앱 초기화
# app = FastAPI(
#     title="AI Interview Agent (YJH)",
#     description="LangGraph + RAG + DB + Voice + Report (Full Version)",
#     version="1.0.0"
# )

# # CORS 미들웨어 설정 (app 생성 바로 아래에 추가)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # 모든 주소 허용 (보안상 로컬 개발용)
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 2. 데이터 모델 정의
# class ChatRequest(BaseModel):
#     user_input: str
#     thread_id: str = "session_1"

# class ChatResponse(BaseModel):
#     response: str
#     current_phase: str
#     question_count: int

# # --- [Helper] DB 저장 함수 ---
# def save_transcript(db, thread_id: str, sender: str, content: str):
#     """대화 내용을 DB에 저장하고 로그를 출력합니다."""
#     try:
#         # 1. 세션 찾기 (없으면 생성)
#         session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
#         if not session:
#             print(f"🆕 [DB] 새 세션 생성: {thread_id}")
#             session = InterviewSession(thread_id=thread_id, candidate_name="Unknown")
#             db.add(session)
#             db.commit()
#             db.refresh(session)
        
#         # 2. 대화 기록 저장
#         transcript = Transcript(session_id=session.id, sender=sender, content=content)
#         db.add(transcript)
#         db.commit()
#         print(f"💾 [DB 저장] {sender}: {content[:30]}...") # 로그 출력
#     except Exception as e:
#         print(f"❌ [DB 저장 실패] {e}")
#         db.rollback()

# # 3. 헬스 체크
# @app.get("/")
# async def health_check():
#     return {"status": "ok", "message": "AI 면접관(Voice+DB+Report) 준비 완료."}

# # 4. 텍스트 대화 엔드포인트
# @app.post("/chat", response_model=ChatResponse)
# async def chat_endpoint(request: ChatRequest):
#     """텍스트로 대화하고 DB에 저장합니다."""
#     db = SessionLocal() # DB 세션 열기
#     try:
#         # [저장] 사용자 입력
#         save_transcript(db, request.thread_id, "human", request.user_input)

#         # LangGraph 실행
#         config = {"configurable": {"thread_id": request.thread_id}}
#         inputs = {"messages": [HumanMessage(content=request.user_input)]}
        
#         result = interview_graph.invoke(inputs, config=config)
#         last_message = result["messages"][-1]
        
#         # [저장] AI 응답
#         save_transcript(db, request.thread_id, "ai", last_message.content)

#         return ChatResponse(
#             response=last_message.content,
#             current_phase=result.get("phase", "unknown"),
#             question_count=result.get("question_count", 0)
#         )
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         db.close() # DB 세션 닫기

# # 5. 음성 대화 (Audio -> Audio) 엔드포인트
# @app.post("/chat/voice/audio")
# async def chat_voice_audio_endpoint(
#     file: UploadFile = File(...), 
#     thread_id: str = "voice_session_final_test" # # 기본값 통일
# ):
#     """
#     [Full Duplex] 음성 파일 업로드 -> STT -> LangGraph -> TTS -> 음성 파일 반환
#     """
#     db = SessionLocal()
#     try:
#         # 1. STT 변환 (Deepgram)
#         audio_bytes = await file.read()
#         user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
#         print(f"🎤 User(STT): {user_text}")

#         if not user_text.strip():
#             raise HTTPException(status_code=400, detail="음성이 인식되지 않았습니다.")

#         # [저장] 사용자 입력
#         save_transcript(db, thread_id, "human", user_text)

#         # ---------------------------------------------------------
#         # [RAG 핵심 로직] 이력서에서 관련 내용 검색
#         # 사용자의 발언(user_text)과 관련된 이력서 내용을 찾아옵니다.
#         # 예: 사용자가 "프로젝트 경험 말해볼게" -> 프로젝트 관련 이력서 내용 검색
#         retrieved_context = get_relevant_context(thread_id, user_text)
        
#         final_input_text = user_text
#         if retrieved_context:
#             print(f"📚 [RAG 검색 성공] 이력서 내용 참고함 (길이: {len(retrieved_context)})")
#             # 프롬프트 엔지니어링: 사용자 몰래 컨텍스트를 주입
#             final_input_text = f"""
#             [System Note: The following is relevant information retrieved from the candidate's resume. Use it to formulate your response or next question.]
#             --- Resume Context ---
#             {retrieved_context}
#             ----------------------
            
#             User's Input: {user_text}
#             """
#         # ---------------------------------------------------------

#         # 2. LangGraph 실행 (주입된 텍스트 전달)
#         config = {"configurable": {"thread_id": thread_id}}
#         inputs = {
#             "messages": [HumanMessage(content=final_input_text)] # 수정된 입력 사용
#         }
        
#         result = interview_graph.invoke(inputs, config=config)
#         ai_text = result["messages"][-1].content
#         print(f"🤖 AI(Logic): {ai_text}")

#         # [저장] AI 응답
#         save_transcript(db, thread_id, "ai", ai_text)

#         # 3. TTS 변환 (OpenAI)
#         output_filename = f"response_{uuid.uuid4()}.mp3"
#         audio_path = await generate_audio(ai_text, output_file=output_filename)

#         # 4. 파일 반환
#         return FileResponse(audio_path, media_type="audio/mpeg", filename="ai_response.mp3")

#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         db.close()

# # 6. [신규 추가] 면접 결과 리포트 생성 API
# @app.post("/report/{thread_id}")
# async def create_report_endpoint(thread_id: str):
#     """
#     특정 세션(thread_id)의 대화 기록을 분석하여 상세 평가 리포트를 생성합니다.
#     """
#     db = SessionLocal()
#     try:
#         # 1. 세션 조회
#         session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

#         # 2. 대화 기록 조회
#         transcripts = db.query(Transcript).filter(Transcript.session_id == session.id).order_by(Transcript.timestamp).all()
        
#         if not transcripts:
#             raise HTTPException(status_code=400, detail="대화 기록이 없습니다.")

#         print(f"📊 [리포트 생성 시작] 세션: {thread_id}, 대화 수: {len(transcripts)}건")

#         # 3. LLM 분석 실행 (Rubric 기반)
#         report_data = await generate_interview_report(transcripts)
        
#         if not report_data:
#             raise HTTPException(status_code=500, detail="리포트 생성 실패")

#         # 4. 결과 DB 저장
#         # Pydantic 모델의 필드들을 DB 테이블 컬럼에 매핑
#         report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session.id).first()
        
#         # 점수 형변환 (float -> int)
#         total_score_int = int(report_data.get("total_weighted_score", 0))
        
#         if not report:
#             report = EvaluationReport(
#                 session_id=session.id,
#                 total_score=total_score_int,
#                 technical_score=report_data["hard_skill"]["score"],
#                 communication_score=report_data["communication"]["score"],
#                 summary=report_data["overall_summary"],
#                 details=report_data # 전체 상세 데이터(JSON) 저장
#             )
#             db.add(report)
#         else:
#             # 기존 리포트 갱신
#             report.total_score = total_score_int
#             report.technical_score = report_data["hard_skill"]["score"]
#             report.communication_score = report_data["communication"]["score"]
#             report.summary = report_data["overall_summary"]
#             report.details = report_data
        
#         db.commit()
#         db.refresh(report)

#         print(f"✅ [리포트 저장 완료] ID: {report.id}, 점수: {total_score_int}점")
#         return {"status": "success", "report": report_data}

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         db.close()

# if __name__ == "__main__":
#     import uvicorn
#     # 모든 IP 허용, 포트 8001
#     uvicorn.run("YYR.main_yjh:app", host="0.0.0.0", port=8001, reload=True)



# # [신규] 비전(얼굴) 분석 엔드포인트
# @app.post("/analyze/face")
# async def analyze_face_endpoint(file: UploadFile = File(...)):
#     """
#     면접자의 스냅샷(이미지)을 받아 감정을 분석합니다. (DeepFace)
#     """
#     try:
#         image_bytes = await file.read()
#         result = analyze_face_emotion(image_bytes)
        
#         print(f"👁️ [Vision 분석 결과]: {result.get('dominant_emotion')}")
        
#         return {
#             "status": "success", 
#             "analysis": result
#         }
#     except Exception as e:
#         return {"status": "error", "message": str(e)}



# # [신규] 이력서 PDF 업로드 API
# @app.post("/upload/resume")
# async def upload_resume(
#     file: UploadFile = File(...), 
#     thread_id: str = "voice_session_final_test"
# ):
#     """
#     PDF 이력서를 업로드하고 RAG용 벡터 DB를 생성합니다.
#     """
#     try:
#         # 1. 파일 임시 저장
#         upload_dir = "uploads"
#         os.makedirs(upload_dir, exist_ok=True)
#         file_path = os.path.join(upload_dir, f"{thread_id}_{file.filename}")
        
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
            
#         # 2. RAG 처리 (텍스트 추출 및 임베딩)
#         success = process_resume_pdf(thread_id, file_path)
        
#         if not success:
#             raise HTTPException(status_code=500, detail="이력서 처리 중 오류 발생")
            
#         return {"status": "success", "message": "이력서 분석 완료! 이제 맞춤형 질문이 가능합니다."}

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # [ 이전 세션이 준 새로운 코드 ] ============================
# @app.get("/report/{thread_id}/result")
# async def get_report_result(thread_id: str):
#     db = SessionLocal()
#     try:
#         session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
#         if not session:
#             raise HTTPException(status_code=404, detail="세션 없음")

#         report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session.id).first()
#         if not report:
#             raise HTTPException(status_code=404, detail="리포트 없음")

#         d = report.details  # JSON

#         return {
#             "session_id": session.id,
#             "total_score": report.total_score,
#             "final_result": d.get("final_result"),
#             "summary": d.get("overall_summary"),
#             "radar": [
#                 {"axis": "hard_skill", "label": "기술 역량", "score": d["hard_skill"]["score"]},
#                 {"axis": "problem_solving", "label": "문제 해결", "score": d["problem_solving"]["score"]},
#                 {"axis": "communication", "label": "커뮤니케이션", "score": d["communication"]["score"]},
#                 {"axis": "attitude", "label": "태도", "score": d["attitude"]["score"]},
#             ],
#             "feedback": {
#                 "hard_skill": d["hard_skill"],
#                 "problem_solving": d["problem_solving"],
#                 "communication": d["communication"],
#                 "attitude": d["attitude"]
#             },
#             "created_at": report.created_at
#         }
#     finally:
#         db.close()

# @app.get("/debug/db")
# async def debug_db():
#     db = SessionLocal()
#     try:
#         row = db.execute(
#             text("SELECT current_database() AS db, current_schema() AS schema")
#         ).fetchone()
#         return {"db": row[0], "schema": row[1]}
#     finally:
#         db.close()

# # 다시 새로운 추가
# @app.get("/report/session/{session_id}/result")
# async def get_report_result_by_session_id(session_id: int):
#     db = SessionLocal()
#     try:
#         report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session_id).first()
#         if not report:
#             raise HTTPException(status_code=404, detail="리포트 없음")

#         d = report.details  # JSON

#         return {
#             "session_id": session_id,
#             "total_score": report.total_score,
#             "final_result": d.get("final_result"),
#             "summary": d.get("overall_summary"),
#             "radar": [
#                 {"axis": "hard_skill", "label": "기술 역량", "score": d["hard_skill"]["score"]},
#                 {"axis": "problem_solving", "label": "문제 해결", "score": d["problem_solving"]["score"]},
#                 {"axis": "communication", "label": "커뮤니케이션", "score": d["communication"]["score"]},
#                 {"axis": "attitude", "label": "태도", "score": d["attitude"]["score"]},
#             ],
#             "feedback": {
#                 "hard_skill": d["hard_skill"],
#                 "problem_solving": d["problem_solving"],
#                 "communication": d["communication"],
#                 "attitude": d["attitude"]
#             },
#             "created_at": report.created_at
#         }
#     finally:
#         db.close()