"""
TASK-M Sprint 4: Multimodal API Router (plan §5, §10, §4.4)

Endpoints:
  POST /api/v1/sessions/{session_id}/multimodal/webrtc/offer
       Accepts SDP offer → returns SDP answer (Full SDP Exchange, plan §4.4).
       MVP: Trickle ICE disabled. TURN server not supported (Phase 2).
       Returns HTTP 429 if concurrent session limit exceeded.
       Returns HTTP 503 if aiortc not available.

  GET  /api/v1/sessions/{session_id}/multimodal/projection
       Polling-based Read-only Projection snapshot (plan §10).

  GET  /api/v1/sessions/{session_id}/multimodal/stream
       SSE push endpoint. Publishes from Redis Pub/Sub (plan §10).

  GET  /api/v1/sessions/{session_id}/multimodal/tts?turn_index={n}
       Returns MP3 bytes from gTTS cache or live generation (plan §5).

Design constraints (plan §4.4 MVP):
  - No Trickle ICE.
  - No TURN server.
  - Max concurrent sessions: MMFlags.MM_WEBRTC_MAX_SESSIONS (5).
  - WebRTC session is strictly optional: mm_flags.webrtc_active() → False skips.
  - Isolation: this router MUST NOT access jobs, interviews, or evaluation_scores
    tables directly. Read-only Projection via Redis only.
"""
from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from packages.imh_multimodal.mm_flags import MMFlags
from packages.imh_multimodal.redis_streams import (
    projection_key,
    ACTIVE_SESSIONS_KEY,
    GPU_MUTEX_KEY,
)

logger = logging.getLogger("imh.multimodal.api")

router = APIRouter(
    prefix="/sessions",
    tags=["Multimodal"],
)


# ------------------------------------------------------------------ #
# Pydantic schemas                                                     #
# ------------------------------------------------------------------ #

class WebRTCOfferRequest(BaseModel):
    sdp: str
    type: str   # "offer"


class WebRTCAnswerResponse(BaseModel):
    sdp: str
    type: str   # "answer"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _get_redis():
    from packages.imh_core.infra.redis import RedisClient
    return RedisClient.get_instance()


# ------------------------------------------------------------------ #
# POST /sessions/{session_id}/multimodal/webrtc/offer                 #
# ------------------------------------------------------------------ #

@router.post("/{session_id}/multimodal/webrtc/offer", response_model=WebRTCAnswerResponse)
async def webrtc_offer(session_id: str, req: WebRTCOfferRequest):
    """
    WebRTC Signaling: Full SDP Exchange (plan §4.4).

    MVP constraints:
      - Trickle ICE not supported.
      - TURN server not provided (Phase 2 scope).
      - NAT Traversal may fail in restrictive environments.

    If MM_ENABLE_WEBRTC=False, returns 503 (feature disabled).
    If active session count ≥ MM_WEBRTC_MAX_SESSIONS, returns 429.
    """
    if not MMFlags.webrtc_active():
        raise HTTPException(
            status_code=503,
            detail="WebRTC not enabled. Set MM_ENABLE=true and MM_ENABLE_WEBRTC=true.",
        )

    # Session concurrency gate (plan §11)
    r = _get_redis()
    active = int(r.get(ACTIVE_SESSIONS_KEY) or 0)
    if active >= MMFlags.MM_WEBRTC_MAX_SESSIONS:
        raise HTTPException(
            status_code=429,
            detail=f"WebRTC session limit reached ({MMFlags.MM_WEBRTC_MAX_SESSIONS} max). "
                   "Retry when a session slot is free.",
        )

    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="aiortc not installed. WebRTC unavailable.",
        )

    pc = RTCPeerConnection()
    offer = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Increment active session counter
    r.incr(ACTIVE_SESSIONS_KEY)

    # Register cleanup on ICE disconnection
    @pc.on("connectionstatechange")
    async def on_state_change():
        if pc.connectionState in ("failed", "closed", "disconnected"):
            r.decr(ACTIVE_SESSIONS_KEY)
            logger.info("WebRTC session closed for session_id=%s state=%s",
                        session_id, pc.connectionState)
            await pc.close()

    logger.info("WebRTC offer processed for session_id=%s", session_id)
    return WebRTCAnswerResponse(
        sdp=pc.localDescription.sdp,
        type=pc.localDescription.type,
    )


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/projection                     #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/projection")
def get_projection(session_id: str):
    """
    Read-only Projection Cache snapshot (plan §10).

    Returns the current multimodal state for the session.
    Non-authoritative: for UI display only.
    Authority = PostgreSQL.
    """
    r = _get_redis()
    key = projection_key(session_id)
    data = r.hgetall(key)

    if not data:
        return {
            "session_id": session_id,
            "inactive": True,
            "metrics": {},
            "note": "No active projection data. Session may be inactive.",
        }

    # Parse metric fields: "{MODALITY}:{metric_key}:{turn_index}" -> value
    metrics: dict = {}
    for field, value in data.items():
        parts = field.split(":", 2)
        if len(parts) == 3:
            modality, metric_key, turn = parts
            metrics.setdefault(modality, {})[f"{metric_key}@turn{turn}"] = float(value)

    return {
        "session_id": session_id,
        "inactive": False,
        "metrics": metrics,
    }


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/stream   (SSE)                #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/stream")
async def projection_stream(session_id: str):
    """
    Server-Sent Events push for real-time multimodal updates (plan §10).

    Uses Redis Pub/Sub channel: mm:pubsub:{session_id}
    On reconnect, client should include Last-Event-ID header.
    On unrecoverable gap, client should fallback to GET /projection.
    """
    r = _get_redis()
    channel = f"mm:pubsub:{session_id}"
    pubsub = r.pubsub()
    pubsub.subscribe(channel)

    async def event_generator() -> AsyncGenerator[str, None]:
        event_id = 0
        try:
            for message in pubsub.listen():
                if message["type"] == "message":
                    event_id += 1
                    data = message["data"]
                    yield f"id: {event_id}\ndata: {data}\n\n"
        except GeneratorExit:
            pass
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/tts                            #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/tts")
def get_tts(
    session_id: str,
    turn_index: int = Query(0, description="Turn index for cache key disambiguation"),
    text: str = Query("", description="Question text to synthesize"),
):
    """
    gTTS endpoint (plan §5).

    Returns MP3 binary on success.
    Returns 204 (No Content) if TTS is disabled or generation failed.
    This endpoint MUST NOT block the WebRTC main flow.
    """
    if not MMFlags.tts_active():
        return Response(status_code=204)

    if not text:
        return Response(status_code=400)

    from packages.imh_multimodal.tts_facade import tts_generate
    mp3_bytes = tts_generate(text)

    if mp3_bytes is None:
        return Response(status_code=204)

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                f'attachment; filename="question_{session_id}_t{turn_index}.mp3"'
            )
        },
    )
