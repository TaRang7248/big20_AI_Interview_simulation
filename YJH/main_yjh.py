# YJH 개인 작업용 FastAPI 엔트리포인트 (임시)


import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가하여 모듈 import 에러 방지
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from YJH.agents.interview_graph import app as interview_graph
from fastapi import UploadFile, File
from YJH.services.voice_service import transcribe_audio
from fastapi.responses import FileResponse
from YJH.services.tts_service import generate_audio
import uuid


# 1. FastAPI 앱 초기화
app = FastAPI(
    title="AI Interview Agent (YJH)",
    description="LangGraph와 RAG가 적용된 모의면접 에이전트 API",
    version="1.0.0"
)

# 2. 요청/응답 데이터 모델 정의 (Pydantic)
class ChatRequest(BaseModel):
    user_input: str
    thread_id: str = "session_1"  # 대화 맥락 유지를 위한 세션 ID

class ChatResponse(BaseModel):
    response: str
    current_phase: str
    question_count: int

# 3. 헬스 체크 엔드포인트
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "AI 면접관이 준비되었습니다."}

# 4. 면접 대화 엔드포인트 (핵심)
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    사용자의 답변을 받아 에이전트(LangGraph)를 실행하고,
    다음 질문이나 반응을 반환합니다.
    """
    try:
        # LangGraph에 전달할 초기 상태 구성
        # thread_id를 통해 이전 대화 기억(Memory)을 로드합니다.
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # 그래프 실행 (invoke)
        # messages 키에 사용자의 입력을 HumanMessage로 포장해서 넣습니다.
        # 주의: interview_graph.py의 State 정의에 따라 필요한 초기값을 넣어줍니다.
        inputs = {
            "messages": [HumanMessage(content=request.user_input)],
            # phase나 question_count는 그래프 내부 메모리에 있다면 생략 가능하지만,
            # 첫 시작일 경우를 대비해 기본값을 설정할 수도 있습니다.
            "phase": "technical_interview", 
            "question_count": 0
        }

        # 그래프 실행!
        # stream=False로 하여 결과를 한 번에 받습니다. (실제 서비스는 stream 권장)
        result = interview_graph.invoke(inputs, config=config)
        
        # 결과 파싱
        # LangGraph의 결과인 result['messages']의 마지막 메시지가 AI의 응답입니다.
        last_message = result["messages"][-1]
        
        return ChatResponse(
            response=last_message.content,
            current_phase=result.get("phase", "unknown"),
            question_count=result.get("question_count", 0)
        )

    except Exception as e:
        # 에러 발생 시 상세 로그 출력 (개발용)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # 로컬 개발용 서버 실행
    uvicorn.run("YJH.main_yjh:app", host="0.0.0.0", port=8000, reload=True)



# [신규 추가 26.02.02] 음성 대화 엔드포인트
@app.post("/chat/voice", response_model=ChatResponse)
async def chat_voice_endpoint(
    file: UploadFile = File(...), 
    thread_id: str = "voice_session_1"
):
    """
    사용자의 음성 파일(.wav, .m4a, .mp3, .webm 등)을 받아
    STT -> LangGraph(Agent) -> 텍스트 응답을 반환합니다.
    """
    try:
        # 1. 업로드된 오디오 파일 읽기
        audio_bytes = await file.read()
        
        # 2. STT 변환 (Deepgram)
        # 파일의 content_type(예: audio/mpeg)을 그대로 전달
        user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
        
        if not user_text.strip():
            return ChatResponse(
                response="음성이 명확하지 않습니다. 다시 말씀해 주시겠어요?",
                current_phase="error",
                question_count=0
            )

        print(f"🎤 [STT 인식 결과]: {user_text}") # 로그 확인용

        # 3. LangGraph 실행 (기존 로직 재사용)
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [HumanMessage(content=user_text)],
            "phase": "technical_interview",
            "question_count": 0 # 실제로는 DB에서 불러와야 함
        }
        
        result = interview_graph.invoke(inputs, config=config)
        last_message = result["messages"][-1]
        
        return ChatResponse(
            response=last_message.content,
            current_phase=result.get("phase", "unknown"),
            question_count=result.get("question_count", 0)
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# [신규 추가 26.02.02] 생성된 오디오 파일 자체를 반환
@app.post("/chat/voice/audio") # 기존 /chat/voice 와 구분하기 위해 경로 변경 가능
async def chat_voice_audio_endpoint(
    file: UploadFile = File(...), 
    thread_id: str = "voice_session_1"
):
    """
    [NEW] 음성 -> STT -> LLM -> TTS -> 음성 파일 반환 (Full Duplex)
    """
    try:
        # 1. STT 변환
        audio_bytes = await file.read()
        user_text = await transcribe_audio(audio_bytes, mimetype=file.content_type)
        print(f"🎤 User: {user_text}")

        if not user_text.strip():
            raise HTTPException(status_code=400, detail="음성이 인식되지 않았습니다.")

        # 2. LangGraph 추론
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [HumanMessage(content=user_text)],
            # 계속 동일한 자기소개 질문이 반복되어 주석처리
            # "phase": "intro", # 수정, intro 자연스러운 라포(26.02.02) [압박 면접 모드, 코딩 테스트 모드, 피드백 모드] 에이전트 인격 교체 가능
            # "question_count": 0 
        }
        
        result = interview_graph.invoke(inputs, config=config)
        ai_text = result["messages"][-1].content
        print(f"🤖 AI: {ai_text}")

        # 3. TTS 변환 (텍스트 -> 오디오)
        # 파일명이 겹치지 않게 UUID 사용
        output_filename = f"response_{uuid.uuid4()}.mp3"
        audio_path = await generate_audio(ai_text, output_file=output_filename)

        # 4. 오디오 파일 반환 (브라우저에서 바로 재생 가능)
        return FileResponse(audio_path, media_type="audio/mpeg", filename="ai_response.mp3")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))