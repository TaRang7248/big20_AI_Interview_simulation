import sys
import os
import uuid
import traceback
import shutil # 파일 저장용

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware # <--- 이거 추가!
from fastapi import Form  # [필수] Form 데이터 수신용
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import json

# 프로젝트 모듈 임포트
from YJH.agents.interview_graph import app as interview_graph
from YJH.services.voice_service import transcribe_audio
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
from YJH.services.transcript_service import save_transcript # [★추가] 방금 만든 서비스 가져오기

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



# 3. 헬스 체크
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "AI 면접관(Voice+DB+Report) 준비 완료."}

# 4. 텍스트 대화 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """텍스트로 대화하고 DB에 저장합니다."""
    db = SessionLocal() # DB 세션 열기
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
        db.close() # DB 세션 닫기

# 5. 음성 대화 (Audio -> Audio) 엔드포인트
@app.post("/chat/voice/audio")
async def chat_voice_audio_endpoint(
    file: UploadFile = File(...), 
    thread_id: str = "voice_session_final_test", # # 기본값 통일
    current_emotion: str = Form("neutral") # [신규] 프론트에서 보낸 감정 받기
):
    """
    [Full Duplex] 음성 파일 업로드 -> STT -> LangGraph -> TTS -> 음성 파일 반환
    """
    db = SessionLocal()
    try:
        # 1. STT 변환 (Deepgram)
        audio_bytes = await file.read()
        user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
        print(f"🎤 User(STT): {user_text}")

        if not user_text.strip():
            raise HTTPException(status_code=400, detail="음성이 인식되지 않았습니다.")

        # [저장] 사용자 입력
        save_transcript(db, thread_id, "human", user_text, emotion=current_emotion)

        # ---------------------------------------------------------
        # [RAG 핵심 로직] 이력서에서 관련 내용 검색
        # 사용자의 발언(user_text)과 관련된 이력서 내용을 찾아옵니다.
        # 예: 사용자가 "프로젝트 경험 말해볼게" -> 프로젝트 관련 이력서 내용 검색
        retrieved_context = get_relevant_context(thread_id, user_text)
        
        final_input_text = user_text
        if retrieved_context:
            print(f"📚 [RAG 검색 성공] 이력서 내용 참고함 (길이: {len(retrieved_context)})")
            
            # [수정] 프롬프트를 훨씬 강력하게(Strict) 변경합니다.
            final_input_text = f"""
            [System Instruction]
            You are a strict technical interviewer evaluating a candidate based on their Resume.
            
            ⚠️ CRITICAL RULES:
            1. You MUST generate a follow-up question based **ONLY** on the [Resume Context] provided below.
            2. DO NOT ask generic questions or questions about topics not mentioned in the resume (e.g., Do NOT ask about NLP, AI, or Deep Learning unless the resume explicitly lists them).
            3. The candidate is a **Backend Developer** (Java, Python, FastAPI, Redis, AWS). Ask specifically about these technologies.
            4. If the candidate mentioned "Migration from Java to Python", ask about the challenges or trade-offs of that specific experience.

            [Resume Context]
            {retrieved_context}

            [User Emotion]
            The candidate is currently feeling: '{current_emotion}'.
            (If the emotion is 'fear' or 'sad', be a bit more encouraging. If 'happy', keep the momentum.)
            
            [Candidate's Last Response]
            "{user_text}"
            
            Based on the context above, ask a deep technical question related to their project experience.
            """
        else:
            print("⚠️ [RAG 검색 실패] 관련 이력서 내용 없음")
            # 이력서 내용이 없을 때도 대비
            final_input_text = f"""
            User Answer: "{user_text}"
            
            You are a technical interviewer. The user introduced themselves as a Backend Developer.
            Ask a standard backend question about Database, API design, or System Architecture.
            """
        # ---------------------------------------------------------

        # 2. LangGraph 실행 (주입된 텍스트 전달)
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [HumanMessage(content=final_input_text)] # 수정된 입력 사용
        }
        
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


# 6. [수정됨] 면접 결과 리포트 생성 API (ID 타입 에러 해결 버전)
@app.post("/report/{thread_id}")
async def create_report_endpoint(thread_id: str):
    """
    thread_id(문자열)로 session_id(숫자)를 찾은 뒤, 대화 내용을 조회합니다.
    """
    print(f"📊 [리포트 생성 요청] Thread ID: {thread_id}")
    
    db = SessionLocal()
    try:
        # 1. [핵심 수정] 문자열 ID(thread_id)로 DB의 숫자 ID(session.id)를 먼저 찾습니다.
        session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
        
        if not session:
            print("⚠️ 해당 thread_id를 가진 세션이 없습니다.")
            return {
                "total_score": 0,
                "feedback_summary": "저장된 세션 정보가 없습니다. (면접이 시작되지 않았을 수 있습니다)",
                "details": []
            }

        # 2. 찾은 숫자 ID (session.id)로 대화 내용 조회
        transcripts = db.query(Transcript).filter(Transcript.session_id == session.id).order_by(Transcript.id).all()
        
        if not transcripts:
            print("⚠️ 대화 기록 없음")
            return {
                "total_score": 0,
                "feedback_summary": "대화 기록이 없습니다.",
                "details": []
            }

        # 3. 대화 내용을 텍스트로 변환
        full_conversation = ""
        for t in transcripts:
            role = "면접관(AI)" if t.sender == "ai" else "지원자"
            full_conversation += f"[{role}]: {t.content}\n"

        print(f"📝 분석 대상 텍스트 길이: {len(full_conversation)}자")
        
        if len(full_conversation) < 50:
             return {
                "total_score": 0,
                "feedback_summary": "면접 데이터가 너무 부족하여 분석할 수 없습니다.",
                "details": []
            }

        # 4. LLM에게 채점 요청 (GPT-4o)
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        system_prompt = """
        당신은 20년 경력의 베테랑 기술 면접관입니다.
        아래 [대화 기록]을 분석하여 면접 결과 리포트를 JSON 형식으로 작성하십시오.
        
        [필수 출력 형식]
        반드시 아래 JSON 구조를 그대로 따르세요. (Markdown backticks 없이 순수 JSON만 출력)
        {
            "total_score": 85,
            "feedback_summary": "지원자는 ... 점이 훌륭했으나, ... 에 대한 설명이 부족했습니다. (전반적인 총평을 3~4문장으로 서술)",
            "details": [
                {"category": "직무 역량(Hard Skill)", "score": 80, "comment": "Redis 캐싱 전략에 대한 설명이 논리적임"},
                {"category": "의사소통(Soft Skill)", "score": 90, "comment": "질문의 요지를 잘 파악하고 두괄식으로 답변함"},
                {"category": "문제 해결력", "score": 85, "comment": "마이그레이션 과정의 트러블 슈팅 경험이 구체적임"}
            ]
        }
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"[대화 기록]\n{full_conversation}")
        ]

        response = llm.invoke(messages)
        
        # 5. JSON 파싱 및 반환
        content = response.content.replace("```json", "").replace("```", "").strip()
        try:
            report_json = json.loads(content)
            print("✅ 리포트 생성 성공!")
            return report_json
        except json.JSONDecodeError:
            print("❌ LLM 응답 파싱 실패")
            return {
                "total_score": 0,
                "feedback_summary": "분석 결과 파싱 중 오류가 발생했습니다.",
                "details": []
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "total_score": 0,
            "feedback_summary": f"서버 에러 발생: {str(e)}",
            "details": []
        }
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))