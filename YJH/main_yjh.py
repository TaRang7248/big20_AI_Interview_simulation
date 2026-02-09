import sys
import os
import uuid
import traceback
import shutil # 파일 저장용

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from collections import Counter
import json

# 프로젝트 모듈 임포트
from YJH.agents.interview_graph import app as interview_graph
from YJH.services.voice_service import transcribe_audio
from YJH.services.tts_service import generate_audio
from YJH.database import get_db, SessionLocal, engine   # <--- engine 추가!
from YJH import models                                 # <--- models 통째로 추가!
# [수정] EvaluationReport 모델 추가 임포트
from YJH.models import InterviewSession, Transcript, EvaluationReport, User # User 추가 확인!
# [수정] 리포트 생성 서비스 추가 임포트
from YJH.services.report_service import generate_interview_report
# [추가] 비디오 면접(Video Interview)
from YJH.services.vision_service import analyze_face_emotion
# [추가] 업로드 API 추가 및 RAG 연동 임포트
from YJH.services.rag_service import process_resume_pdf, get_relevant_context
from YJH.services.transcript_service import save_transcript # [★추가] 방금 만든 서비스 가져오기

# ==========================================================
# [★핵심] 서버가 켜질 때, DB에 없던 테이블(Users 등)을 자동 생성합니다.
# ==========================================================
models.Base.metadata.create_all(bind=engine)

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
    thread_id: str = "voice_session_final_test", 
    current_emotion: str = Form("neutral") 
):
    """
    [Full Duplex] 음성 파일 업로드 -> STT -> RAG(강제 주입) -> LangGraph -> TTS -> 음성 파일 반환
    """
    db = SessionLocal()
    try:
        # 1. STT 변환
        audio_bytes = await file.read()
        user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
        print(f"🎤 User(STT): {user_text} [Emotion: {current_emotion}]")

        if not user_text.strip():
            raise HTTPException(status_code=400, detail="음성이 인식되지 않았습니다.")

        # [저장] 사용자 입력
        save_transcript(db, thread_id, "human", user_text, emotion=current_emotion)

        # ---------------------------------------------------------
        # [★핵심 수정] RAG 검색어 전략: "User Input" + "Fixed Keywords"
        # 사용자가 "안녕하세요"라고만 해도, 뒤에 "기술 스택 프로젝트 경험"을 붙여서
        # 이력서의 핵심 내용을 강제로 긁어오게 만듭니다.
        # ---------------------------------------------------------
        rag_query = f"{user_text} technical skills project experience strength main stack"
        retrieved_context = get_relevant_context(thread_id, rag_query)
        
        # 만약 그래도 검색이 안 되면, '요약(summary)'이라도 가져오라고 한 번 더 시도 (안전장치)
        if not retrieved_context:
             retrieved_context = get_relevant_context(thread_id, "summary of candidate resume")

        final_input_text = user_text
        
        if retrieved_context:
            print(f"📚 [RAG 검색 성공] 이력서 내용 추출됨 (길이: {len(retrieved_context)})")
            
            # [프롬프트 강화] 이력서 내용을 바탕으로 질문하도록 강력하게 지시
            final_input_text = f"""
            [System Instruction]
            You are a strict technical interviewer. 
            The user just said: "{user_text}"
            
            [Resume Context - VERY IMPORTANT]
            Use the following details from the candidate's resume to generate a relevant follow-up question.
            Focus on their specific projects and tech stack mentioned below:
            {retrieved_context}
            
            [User Emotion]
            Current emotion: '{current_emotion}' (If fear/sad, be encouraging. If happy, be professional.)
            """
        else:
            print("⚠️ [RAG 검색 실패] 관련 이력서 내용 없음 (일반 질문 진행)")
            # 이력서가 정말 없을 때를 대비한 기본 프롬프트
            final_input_text = f"""
            User Answer: "{user_text}"
            You are a technical interviewer. The user introduced themselves as a Backend Developer.
            Ask a standard backend question about Database, API design, or System Architecture.
            """
        # ---------------------------------------------------------

        # 2. LangGraph 실행
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [HumanMessage(content=final_input_text)]}
        
        result = interview_graph.invoke(inputs, config=config)
        ai_text = result["messages"][-1].content
        print(f"🤖 AI(Logic): {ai_text}")

        # [저장] AI 응답
        save_transcript(db, thread_id, "ai", ai_text)

        # 3. TTS 변환 (함수명이 프로젝트마다 다를 수 있으니 확인 필요)
        # 만약 에러가 난다면 generate_audio 대신 text_to_speech_file 로 바꿔보세요.
        try:
            # 기존 코드에 있던 함수 사용 (generate_audio 라고 가정)
            output_filename = f"response_{uuid.uuid4()}.mp3"
            audio_path = await generate_audio(ai_text, output_file=output_filename)
        except NameError:
            # 만약 generate_audio가 없으면 text_to_speech_file 시도 (안전장치)
            audio_path = await text_to_speech_file(ai_text)

        # 4. 파일 반환
        return FileResponse(audio_path, media_type="audio/mpeg", filename="ai_response.mp3")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# 6. [업그레이드] 면접 결과 리포트 생성 API (엄격한 평가 모드)
@app.post("/report/{thread_id}")
async def create_report_endpoint(thread_id: str):
    print(f"📊 [리포트 생성 요청] Thread ID: {thread_id}")
    
    db = SessionLocal()
    try:
        # 1. 세션 조회
        session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
        if not session:
            return {"total_score": 0, "feedback_summary": "세션 정보가 없습니다.", "details": []}

        # 2. 대화 기록 조회
        transcripts = db.query(Transcript).filter(Transcript.session_id == session.id).order_by(Transcript.id).all()
        
        if not transcripts:
            return {"total_score": 0, "feedback_summary": "대화 기록이 없습니다.", "details": []}

        # 3. 대화 텍스트 & 감정 데이터 추출
        full_conversation = ""
        emotion_list = []
        user_speech_count = 0  # 지원자가 말한 횟수

        for t in transcripts:
            role = "면접관(AI)" if t.sender == "ai" else "지원자"
            full_conversation += f"[{role}]: {t.content}\n"
            
            if t.sender == "human":
                user_speech_count += 1
                if t.emotion:
                    emotion_list.append(t.emotion)

        # 4. 데이터 부족 시 조기 종료 (안전장치)
        if user_speech_count < 2:
             return {
                "total_score": 0, 
                "feedback_summary": "평가할 수 있는 대화가 부족합니다. (답변 횟수 부족)", 
                "details": []
            }

        # 감정 통계
        emotion_stats = Counter(emotion_list)
        dominant_emotion = emotion_stats.most_common(1)[0][0] if emotion_stats else "정보 없음"
        
        print(f"📝 분석 대상 텍스트 길이: {len(full_conversation)}자")
        print(f"👁️ 감정 통계: {dict(emotion_stats)}")

        # 5. LLM에게 채점 요청 (독한 면접관 모드)
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        system_prompt = f"""
        당신은 지원자를 냉정하게 평가하는 'Technical Interviewer'입니다.
        제공된 [대화 기록]만을 근거로 채점하십시오. 상상하거나 지어내지 마십시오.

        [⚠️ 감점(Fail) 기준 - 매우 중요]
        1. **회피형 답변**: 지원자가 "모르겠습니다", "죄송합니다", "준비가 안 됐습니다"라고 답변한 경우, 해당 항목은 **0점** 처리하십시오.
        2. **단답형 답변**: 기술적인 설명 없이 "네/아니오"로만 답하면 감점하십시오.
        3. **환각 금지**: 대화 기록에 없는 기술(Redis, Kafka 등)을 사용했다고 칭찬하지 마십시오. 오직 대화에 나온 내용만 평가하십시오.

        [평가 가중치]
        - 답변의 기술적 깊이 (80%)
        - 태도 및 의사소통 (20%)

        [비언어적 감정 데이터]
        - 주요 감정: {dominant_emotion} (참고용)

        [필수 출력 형식 (JSON)]
        {{
            "total_score": (정수 0~100),
            "feedback_summary": "(지원자의 실제 답변 태도와 지식 수준을 냉정하게 요약. 답변을 못했으면 솔직하게 못했다고 적을 것)",
            "details": [
                {{"category": "직무 지식", "score": (0~100), "comment": "(구체적인 근거)"}},
                {{"category": "의사소통", "score": (0~100), "comment": "(감정 상태 및 답변 태도 반영)"}},
                {{"category": "문제해결", "score": (0~100), "comment": "(트러블슈팅 답변 여부)"}}
            ]
        }}
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"[대화 기록]\n{full_conversation}")
        ]

        response = llm.invoke(messages)
        
        # 6. JSON 파싱
        content = response.content.replace("```json", "").replace("```", "").strip()
        report_json = json.loads(content)

        # ==========================================================
        # [★Final Complete] 상세 점수 추출 및 DB 저장
        # ==========================================================
        try:
            # 1. 상세 점수 추출하기 (JSON -> 변수)
            # 기본값은 0점으로 설정
            tech_score = 0      # 직무 역량
            soft_score = 0      # 의사소통/태도
            problem_score = 0   # 문제 해결력

            details_list = report_json.get("details", [])
            
            # 리스트를 돌면서 카테고리별 점수 찾기
            for item in details_list:
                category = item.get("category", "")
                score = item.get("score", 0)
                
                if "직무" in category or "Hard" in category:
                    tech_score = score
                elif "의사소통" in category or "Soft" in category or "태도" in category:
                    soft_score = score
                elif "문제" in category or "Solving" in category:
                    problem_score = score

            # 2. DB 중복 확인 및 저장
            existing_report = db.query(EvaluationReport).filter(EvaluationReport.session_id == session.id).first()
            
            if not existing_report:
                new_report = EvaluationReport(
                    session_id=session.id,
                    total_score=report_json.get("total_score", 0),
                    summary=report_json.get("feedback_summary", ""),
                    
                    # [핵심] 추출한 점수를 DB 컬럼에 매핑 (DB 컬럼명과 일치해야 함)
                    technical_score=tech_score,
                    communication_score=soft_score,
                    problem_solving_score=problem_score
                    
                    # 만약 DB에 json_details 같은 텍스트 컬럼을 따로 만드셨다면 아래 주석 해제
                    # details=json.dumps(details_list, ensure_ascii=False)
                )
                db.add(new_report)
                db.commit()
                print(f"💾 [DB] 리포트 저장 완료! (T:{tech_score}, C:{soft_score}, P:{problem_score})")
                
        except Exception as db_err:
            print(f"⚠️ 리포트 저장 중 오류 (컬럼명 확인 필요): {db_err}")
            # db.rollback()
        # ==========================================================

        return report_json

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"total_score": 0, "feedback_summary": f"에러 발생: {str(e)}", "details": []}
    finally:
        db.close()



# ==========================================================
# [신규 기능] 회원가입/로그인 & 마이페이지 API
# ==========================================================

# 1. 로그인 요청 데이터 구조
class LoginRequest(BaseModel):
    username: str

# 2. 간편 로그인 API (없으면 가입, 있으면 로그인)
@app.post("/login")
def login(req: LoginRequest):
    print(f"🔑 로그인 요청: {req.username}")
    db = SessionLocal()
    try:
        # 이미 있는 유저인지 확인
        user = db.query(User).filter(User.username == req.username).first()
        
        if not user:
            # 없으면 신규 가입
            user = User(username=req.username)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"🎉 [신규 회원 가입] {req.username} (ID: {user.id})")
        else:
            print(f"👋 [재방문] {req.username} (ID: {user.id})")
            
        # 프론트엔드에 user_id와 이름 반환
        return {"user_id": user.id, "username": user.username}
    except Exception as e:
        print(f"❌ 로그인 에러: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        db.close()

# 3. 마이 페이지 API (내 면접 기록 조회)
@app.get("/history/{user_id}")
def get_user_history(user_id: int):
    print(f"📂 기록 조회 요청: User ID {user_id}")
    db = SessionLocal()
    try:
        # 내 면접 세션들을 최신순으로 조회
        sessions = db.query(InterviewSession)\
            .filter(InterviewSession.user_id == user_id)\
            .order_by(InterviewSession.created_at.desc())\
            .all()
            
        history_list = []
        for s in sessions:
            # 리포트가 생성된(완료된) 면접만 리스트에 추가
            if s.report:
                history_list.append({
                    "session_id": s.id,
                    "date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                    "total_score": s.report.total_score,
                    "summary": s.report.summary[:60] + "..." if s.report.summary else "요약 없음", # 60자 미리보기
                    # 상세 점수도 같이 보내주면 리스트에서 바로 볼 수 있음
                    "scores": {
                        "tech": s.report.technical_score,
                        "comm": s.report.communication_score,
                        "prob": s.report.problem_solving_score
                    }
                })
        
        print(f"✅ 조회 완료: 총 {len(history_list)}건")
        return {"history": history_list}
    except Exception as e:
        print(f"❌ 기록 조회 에러: {e}")
        return {"history": []}
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



# [수정됨] 이력서 업로드 API (User ID 연결 포함)
@app.post("/upload/resume")
async def upload_resume(
    file: UploadFile = File(...), 
    thread_id: str = Form(...),  # [변경] 프론트엔드 FormData에서 받기 위해 Form(...) 사용
    user_id: int = Form(...)     # [신규] 로그인한 유저 ID 받기 (필수!)
):
    """
    PDF 이력서를 업로드하고 RAG용 벡터 DB를 생성하며, 
    DB에 면접 세션 정보(User ID 포함)를 기록합니다.
    """
    print(f"📂 [이력서 업로드] Thread: {thread_id}, User ID: {user_id}")

    try:
        # 1. 파일 임시 저장 (기존 로직 유지)
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{thread_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. RAG 처리 (텍스트 추출 및 임베딩)
        success = process_resume_pdf(thread_id, file_path)
        
        if not success:
            raise HTTPException(status_code=500, detail="이력서 RAG 처리 실패")

        # ==========================================================
        # 3. [핵심 추가] DB에 면접 세션 생성 (유저 연결)
        # ==========================================================
        db = SessionLocal()
        try:
            # 혹시 이미 등록된 세션인지 확인 (중복 방지)
            existing_session = db.query(InterviewSession).filter(InterviewSession.thread_id == thread_id).first()
            
            if not existing_session:
                new_session = InterviewSession(
                    thread_id=thread_id,
                    user_id=user_id,       # <--- 여기가 제일 중요합니다! (내 면접으로 등록)
                    candidate_name="지원자", # (나중에 로그인 정보에서 가져올 수도 있음)
                    status="in_progress"
                )
                db.add(new_session)
                db.commit()
                print(f"✅ [DB] 신규 면접 세션 생성 완료 (User: {user_id})")
            else:
                # 이미 있으면 user_id만 업데이트 (혹시 모르니)
                existing_session.user_id = user_id
                db.commit()
                print(f"✅ [DB] 기존 세션 유저 정보 업데이트 (User: {user_id})")
                
        except Exception as db_e:
            print(f"⚠️ DB 세션 저장 실패: {db_e}")
            # DB 저장이 실패해도 면접은 진행되도록 여기서 에러를 raise하지는 않음 (선택사항)
        finally:
            db.close()
        # ==========================================================
            
        return {"status": "success", "message": "이력서 분석 및 세션 등록 완료!"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))