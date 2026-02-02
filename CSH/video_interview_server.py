import asyncio # 파이썬에서 비동기(Async) 작업을 처리하기 위한 도구
import time # 프레임 샘플링(초당 1프레임) 제어를 위한 시간 측정 도구
import os # 컴퓨터 시스템의 환경(파일 경로, 환경 변수 등)에 접근할 때 사용
from typing import Set, Optional, Dict 

from fastapi import FastAPI, Request # FastAPI 웹 프레임워크에서 핵심 기능을 가져오기
from fastapi.responses import HTMLResponse # 서버가 답변을 줄 때 'HTML 웹페이지' 형태로 응답하기 위해 사용
from fastapi.staticfiles import StaticFiles # 이미지나 CSS 같은 변하지 않는 정적 파일을 서빙하기 위한 도구
from pydantic import BaseModel # 데이터의 형식을 미리 정해두고 검사하는 도구

# WebRTC(실시간 통신) 관련 도구
from aiortc import RTCPeerConnection # WebRTC의 핵심으로, 내 컴퓨터와 상대방 컴퓨터를 직접 연결하는 '통로'
from aiortc.contrib.media import MediaBlackhole # 들어오는 미디어(영상/음성) 데이터를 기록하지 않고 그냥 '블랙홀'처럼 흡수해버리는 도구
import numpy as np
from deepface import DeepFace

# app이라는 이름으로 FastAPI 서버 객체를 생성
app = FastAPI(title="AI Interview - Video Server")

# 내 컴퓨터 안에서 '정적 파일(이미지, CSS, 자바스크립트 등)이 담긴 폴더'의 위치를 찾는 줄
static_dir = os.path.join(os.path.dirname(__file__), "static")
# 방금 찾은 폴더를 외부에서 접속할 수 있게 연결해주는 설정
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 현재 서버에 연결된 '실시간 영상 통로(Peer Connection)'들을 담아두는 바구니를 만드는 줄
pcs: Set[RTCPeerConnection] = set()

# 최신 감정 분석 결과 캐시 (간단 구현)
last_emotion: Optional[Dict] = None
_emotion_lock = asyncio.Lock()

# 사용자(클라이언트)가 서버에 보낼 'SDP offer' 형식을 미리 정의
# SDP(Session Description Protocol): 통신 사양
class Offer(BaseModel):
    sdp: str
    type: str

# 상태 페이지
# 사용자가 웹 브라우저 주소창에 내 서버 주소를 입력하고 들어왔을 때, 가장 처음 보여줄 페이지(메인 화면)를 정의하는 부분
# @app.get("/"): 사용자가 주소 뒤에 아무것도 붙이지 않은 기본 경로(/)로 접속했을 때 이 함수를 실행하라는 뜻
# response_class=HTMLResponse: 서버가 보내주는 응답이 단순한 글자가 아니라, 브라우저가 해석해야 할 'HTML 문서'임을 미리 알려주는 설정
@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (
        "<html><head><meta charset='utf-8'><title>Video Interview</title></head>"
        "<body>"
        "<h2>Video Interview</h2>"
        "<p>Open <a href='/static/video.html'>/static/video.html</a> to start.</p>"
        "</body></html>"
    )

# 브라우저로부터 SDP offer를 받아 answer 생성
@app.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state_change():
        if pc.iceConnectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)

# 서버가 사용자의 영상/음성 신호를 받아서 어떻게 처리할지 결정하고, 최종적으로 연결을 확정 짓는 가장 중요한 로직
    @pc.on("track")
    async def on_track(track):
        # Echo back only video to avoid audio feedback
        if track.kind == "video":
            pc.addTrack(track)
            # 병렬로 감정 분석 태스크 실행
            asyncio.create_task(_analyze_emotions(track))
        else:
            # Consume audio to keep the pipeline alive without echoing
            bh = MediaBlackhole()
            asyncio.create_task(_consume_audio(track, bh))

    await pc.setRemoteDescription({"sdp": offer.sdp, "type": offer.type})
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


async def _consume_audio(track, sink: MediaBlackhole):
    try:
        while True:
            frame = await track.recv()
            sink.write(frame)
    except Exception:
        pass

async def _analyze_emotions(track):
    """영상 프레임을 주기적으로 받아 DeepFace로 감정 분석을 수행하고 캐시에 저장."""
    # 분석 샘플링 주기(초): 초당 1프레임(FPS)
    sample_period = 1.0
    last_ts = 0.0
    try:
        while True:
            frame = await track.recv()
            now = time.monotonic()
            # 샘플링 간격을 만족할 때만 분석 수행 (1 FPS)
            if now - last_ts < sample_period:
                continue
            last_ts = now
            # VideoFrame을 OpenCV BGR 이미지로 변환 (분석 시점에만 변환)
            try:
                img = frame.to_ndarray(format="bgr24")
            except Exception:
                continue

            # 선택적으로 리사이즈로 속도 최적화
            h, w = img.shape[:2]
            if max(h, w) > 720:
                scale = 720 / max(h, w)
                img = np.ascontiguousarray(
                    cv2.resize(img, (int(w * scale), int(h * scale)))
                ) if 'cv2' in globals() else img

            # DeepFace 감정 분석
            try:
                res = DeepFace.analyze(img, actions=["emotion"], enforce_detection=False)
                # 결과 정규화
                item = res[0] if isinstance(res, list) and res else res
                data = {
                    "dominant_emotion": item.get("dominant_emotion"),
                    "scores": item.get("emotion"),
                }
                async with _emotion_lock:
                    global last_emotion
                    last_emotion = data
            except Exception:
                # 분석 실패는 조용히 넘기고 다음 프레임에서 재시도
                pass

    except Exception:
        # 트랙 종료 등
        pass

# FastAPI 서버가 종료될 때 이 함수를 자동으로 실행하라는 명령
@app.on_event("shutdown")
async def on_shutdown():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros, return_exceptions=True)
    pcs.clear()

# 최신 감정 분석 결과를 제공하는 간단한 엔드포인트
@app.get("/emotion")
async def emotion():
    async with _emotion_lock:
        if last_emotion is None:
            return {"status": "no_data"}
        return last_emotion
