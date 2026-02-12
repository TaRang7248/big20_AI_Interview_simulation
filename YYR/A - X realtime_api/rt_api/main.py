# [2, 1] import json
# import uuid
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# from .ws_protocol import ClientEvent, ServerEvent

# app = FastAPI()

# async def send_event(ws: WebSocket, session_id: str, type_: str, payload: dict):
#     evt = ServerEvent(type=type_, session_id=session_id, payload=payload)
#     await ws.send_text(evt.model_dump_json())

# @app.get("/")
# def root():
#     return {"message": "realtime_api is alive"}

# @app.websocket("/ws")
# async def ws_endpoint(ws: WebSocket):
#     await ws.accept()

#     # session_id = str(uuid.uuid4())
#     # await send_event(ws, session_id, "session.ready", {"message": "ws connected"})

#     # try:
#     #     while True:
#     #         msg = await ws.receive()

#     #         if "text" in msg and msg["text"] is not None:
#     #             data = json.loads(msg["text"])
#     #             evt = ClientEvent(**data)
#     #             await send_event(ws, session_id, "status", {"received": evt.type})

#     #         else:
#     #             await send_event(ws, session_id, "error", {"message": "only text supported in this step"})
#     # except WebSocketDisconnect:
#     #     pass

#     session_id = str(uuid.uuid4())
#     await send_event(ws, session_id, "session.ready", {"message": "ws connected"})

#     try:
#         while True:
#             try:
#                 msg = await ws.receive()
#             except WebSocketDisconnect:
#                 # 클라이언트가 끊으면 루프 종료
#                 break

#             # 클라이언트가 정상 close 보내는 경우도 안전하게 종료
#             if msg.get("type") == "websocket.disconnect":
#                 break

#             if "text" in msg and msg["text"] is not None:
#                 data = json.loads(msg["text"])
#                 evt = ClientEvent(**data)
#                 await send_event(ws, session_id, "status", {"received": evt.type})

#             elif "bytes" in msg and msg["bytes"] is not None:
#                 # 아직 bytes 단계가 아니면 그냥 무시(에러 보내지 않음)
#                 # 에러를 보내려다 연결이 닫히면 지금처럼 터질 수 있어서 안전하게 패스
#                 pass

#             else:
#                 # 지원 안 하는 메시지도 그냥 무시
#                 pass

#     except Exception as e:
#         # 예기치 못한 에러는 로그만 남기고 종료 (닫힌 ws에 send하지 않음)
#         print("WS ERROR:", repr(e))

# 3번째 코드 ?
# import json
# import uuid
# from typing import Any, Dict

# from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# from .ws_protocol import ClientEvent, ServerEvent
# from core.interview_engine import InterviewEngine

# app = FastAPI()

# SESSIONS: Dict[str, Dict[str, Any]] = {}

# async def send_event(ws: WebSocket, session_id: str, type_: str, payload: dict):
#     evt = ServerEvent(type=type_, session_id=session_id, payload=payload)
#     await ws.send_text(evt.model_dump_json())

# @app.get("/")
# def root():
#     return {"message": "realtime_api is alive"}

# @app.websocket("/ws")
# async def ws_endpoint(ws: WebSocket):
#     await ws.accept()

#     session_id = str(uuid.uuid4())
#     await send_event(ws, session_id, "session.ready", {"message": "ws connected"})

#     try:
#         while True:
#             try:
#                 msg = await ws.receive()
#             except WebSocketDisconnect:
#                 break

#             if msg.get("type") == "websocket.disconnect":
#                 break

#             if "text" not in msg or msg["text"] is None:
#                 continue

#             try:
#                 evt = ClientEvent(**json.loads(msg["text"]))
#             except Exception as e:
#                 await send_event(ws, session_id, "error", {"message": f"invalid event: {e}"})
#                 continue

#             if evt.type == "session.start":
#                 first_q = str(evt.payload.get("first_question", "")).strip()
#                 use_llm = bool(evt.payload.get("use_llm", False))

#                 if not first_q:
#                     await send_event(ws, session_id, "error", {"message": "first_question is required"})
#                     continue

#                 engine = InterviewEngine(use_llm=use_llm)
#                 q1 = engine.start(first_q)
#                 t1 = engine.add_question(q1)

#                 SESSIONS[session_id] = {"engine": engine}

#                 await send_event(ws, session_id, "question", {"turn": t1.turn, "text": t1.question})
#                 await send_event(ws, session_id, "debug", {"q_type": t1.q_type, "llm_active": engine.llm is not None})

#             elif evt.type == "answer":
#                 session = SESSIONS.get(session_id)
#                 if not session:
#                     await send_event(ws, session_id, "error", {"message": "session not started. send session.start first"})
#                     continue

#                 engine: InterviewEngine = session["engine"]
#                 answer_text = str(evt.payload.get("text", "")).strip()

#                 if not answer_text:
#                     await send_event(ws, session_id, "error", {"message": "answer text is required"})
#                     continue

#                 engine.turns[-1].user_answer = answer_text

#                 next_q, debug = engine.step(answer_text)
#                 t_next = engine.add_question(next_q)

#                 await send_event(ws, session_id, "question", {"turn": t_next.turn, "text": t_next.question})
#                 await send_event(ws, session_id, "debug", {"q_type": t_next.q_type, **debug})

#             elif evt.type == "session.stop":
#                 SESSIONS.pop(session_id, None)

#     except Exception as e:
#         print("WS ERROR:", repr(e))

# [4] =====================

import json
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from .ws_protocol import ClientEvent, ServerEvent
from core.interview_engine import InterviewEngine

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> {"engine": InterviewEngine}
SESSIONS: Dict[str, Dict[str, Any]] = {}


async def send_event(ws: WebSocket, session_id: str, type_: str, payload: dict):
    evt = ServerEvent(type=type_, session_id=session_id, payload=payload)
    await ws.send_text(evt.model_dump_json())


@app.get("/")
def root():
    return {"message": "realtime_api is alive"}


# ---------- REST (세션 생성/시작) ----------
class StartSessionReq(BaseModel):
    first_question: str
    use_llm: bool = False

class StartSessionRes(BaseModel):
    session_id: str
    question: str
    turn: int
    debug: Dict[str, Any]

@app.post("/session/start", response_model=StartSessionRes)
def start_session(req: StartSessionReq):
    first_q = req.first_question.strip()
    if not first_q:
        raise HTTPException(status_code=400, detail="first_question is required")

    session_id = str(uuid.uuid4())
    engine = InterviewEngine(use_llm=req.use_llm)

    q1 = engine.start(first_q)
    t1 = engine.add_question(q1)

    SESSIONS[session_id] = {"engine": engine}

    return StartSessionRes(
        session_id=session_id,
        question=t1.question,
        turn=t1.turn,
        debug={"q_type": t1.q_type, "llm_active": engine.llm is not None},
    )


# ---------- WS (실시간 대화 이벤트) ----------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, session_id: Optional[str] = None):
    """
    ws://127.0.0.1:8000/ws?session_id=...
    - session_id가 오면 그 세션에 붙음
    - 없으면 임시로 새 세션을 만들어도 되지만, B 방향에서는 보통 '필수'로 둠
    """
    await ws.accept()

    # B 방향: session_id 없으면 에러(프론트가 REST로 먼저 세션 만든 뒤 접속)
    if not session_id:
        tmp = str(uuid.uuid4())
        await send_event(ws, tmp, "error", {"message": "session_id query param is required. Call POST /session/start first."})
        await ws.close()
        return

    session = SESSIONS.get(session_id)
    if not session:
        await send_event(ws, session_id, "error", {"message": "invalid session_id. Call POST /session/start first."})
        await ws.close()
        return

    await send_event(ws, session_id, "session.ready", {"message": "ws connected"})

    try:
        while True:
            try:
                msg = await ws.receive()
            except WebSocketDisconnect:
                break

            if msg.get("type") == "websocket.disconnect":
                break

            if "text" not in msg or msg["text"] is None:
                continue

            try:
                evt = ClientEvent(**json.loads(msg["text"]))
            except Exception as e:
                await send_event(ws, session_id, "error", {"message": f"invalid event: {e}"})
                continue

            # WS에서는 이제 session.start를 굳이 안 써도 됨(REST에서 이미 시작함)
            if evt.type == "answer":
                engine: InterviewEngine = session["engine"]

                answer_text = str(evt.payload.get("text", "")).strip()
                if not answer_text:
                    await send_event(ws, session_id, "error", {"message": "answer text is required"})
                    continue

                engine.turns[-1].user_answer = answer_text
                next_q, debug = engine.step(answer_text)
                t_next = engine.add_question(next_q)

                await send_event(ws, session_id, "question", {"turn": t_next.turn, "text": t_next.question})
                await send_event(ws, session_id, "debug", {"q_type": t_next.q_type, **debug})

            elif evt.type == "session.stop":
                SESSIONS.pop(session_id, None)
                break

    except Exception as e:
        print("WS ERROR:", repr(e))
