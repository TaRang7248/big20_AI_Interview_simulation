import asyncio
import os
from typing import Set

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaBlackhole


app = FastAPI(title="AI Interview - Video Server")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


pcs: Set[RTCPeerConnection] = set()


class Offer(BaseModel):
    sdp: str
    type: str


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (
        "<html><head><meta charset='utf-8'><title>Video Interview</title></head>"
        "<body>"
        "<h2>Video Interview</h2>"
        "<p>Open <a href='/static/video.html'>/static/video.html</a> to start.</p>"
        "</body></html>"
    )


@app.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state_change():
        if pc.iceConnectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    async def on_track(track):
        # Echo back only video to avoid audio feedback
        if track.kind == "video":
            pc.addTrack(track)
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


@app.on_event("shutdown")
async def on_shutdown():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros, return_exceptions=True)
    pcs.clear()
