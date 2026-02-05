"""
D-ID AI 아바타 서비스
=====================
D-ID API를 사용하여 실시간 AI 면접관 영상을 생성합니다.

기능:
- Talks API: 텍스트를 입력받아 말하는 아바타 영상 생성 (느림, 10-30초)
- Streams API: 실시간 스트리밍 아바타 (WebRTC, 빠름, 1-3초)

사용법:
    1. https://www.d-id.com 에서 가입
    2. API Key 발급
    3. .env 파일에 DID_API_KEY 설정
    
Streaming API 흐름:
    1. /talks/streams 로 스트림 생성 → SDP Offer, ICE 서버 정보 반환
    2. 클라이언트에서 WebRTC PeerConnection 생성
    3. SDP Answer를 /talks/streams/{id}/sdp 로 전송
    4. ICE Candidate를 /talks/streams/{id}/ice 로 전송
    5. /talks/streams/{id} 로 텍스트 전송 → 실시간 비디오 스트리밍
"""

import os
import asyncio
import aiohttp
import base64
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# D-ID API 설정
DID_API_KEY = os.getenv("DID_API_KEY", "")
DID_API_URL = "https://api.d-id.com"

# 기본 아바타 이미지 (D-ID 제공 또는 커스텀)
DEFAULT_PRESENTER_IMAGE = "https://create-images-results.d-id.com/api_docs/assets/noelle.jpeg"

# 한국어 TTS 설정 (D-ID 내장 TTS 사용)
DEFAULT_VOICE = {
    "type": "microsoft",
    "voice_id": "ko-KR-SunHiNeural",  # 한국어 여성 음성
    "style": "friendly"
}

# 남성 음성 옵션
MALE_VOICE = {
    "type": "microsoft",
    "voice_id": "ko-KR-InJoonNeural",  # 한국어 남성 음성
    "style": "professional"
}

# 스트리밍 설정
STREAM_WARMUP = True  # 스트림 워밍업 활성화 (연결 유지)


class DIDStreamingService:
    """D-ID Streaming API를 사용한 실시간 아바타 서비스 (WebRTC)
    
    Talks API 대비 장점:
    - 영상 생성 지연 없음 (1-3초 vs 10-30초)
    - 실시간 스트리밍으로 즉각 응답
    - WebRTC 기반으로 안정적인 스트리밍
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or DID_API_KEY
        self.session_id: Optional[str] = None
        self.stream_id: Optional[str] = None
        self.ice_servers: list = []
        self.offer: Optional[Dict] = None
        self.is_connected: bool = False
        self.pending_messages: List[str] = []
        
    def _get_headers(self) -> Dict[str, str]:
        """API 헤더 생성"""
        # D-ID는 API 키를 Base64 인코딩해서 Basic Auth로 사용
        auth_string = f"{self.api_key}:"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        return {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/json"
        }
    
    async def create_stream(self, source_url: str = None) -> Dict[str, Any]:
        """스트림 세션 생성 - WebRTC Offer 반환"""
        if not self.api_key or self.api_key == "your_did_api_key_here":
            return {"error": "D-ID API 키가 설정되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks/streams"
        payload = {
            "source_url": source_url or DEFAULT_PRESENTER_IMAGE,
            "driver_url": "bank://lively",
            "config": {
                "stitch": True,
                "fluent": True,  # 더 부드러운 립싱크
                "pad_audio": 0.5  # 오디오 패딩
            }
        }
        
        # 워밍업 활성화
        if STREAM_WARMUP:
            payload["config"]["auto_start"] = True
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        self.stream_id = data.get("id")
                        self.session_id = data.get("session_id")
                        self.ice_servers = data.get("ice_servers", [])
                        self.offer = data.get("offer")
                        
                        print(f"✅ D-ID 스트림 생성: stream_id={self.stream_id}")
                        
                        return {
                            "success": True,
                            "stream_id": self.stream_id,
                            "session_id": self.session_id,
                            "ice_servers": self.ice_servers,
                            "offer": self.offer  # SDP Offer
                        }
                    else:
                        error = await resp.text()
                        print(f"❌ D-ID 스트림 생성 실패: {error}")
                        return {"error": f"스트림 생성 실패: {error}"}
        except Exception as e:
            print(f"❌ D-ID 스트림 생성 오류: {e}")
            return {"error": f"스트림 생성 오류: {str(e)}"}
    
    async def start_stream(self) -> Dict[str, Any]:
        """스트림 시작 (SDP 교환 후 호출)"""
        if not self.stream_id:
            return {"error": "스트림이 생성되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks/streams/{self.stream_id}/start"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"session_id": self.session_id}, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        self.is_connected = True
                        print("✅ D-ID 스트림 시작됨")
                        return {"success": True, "message": "스트림 시작됨"}
                    else:
                        error = await resp.text()
                        return {"error": f"스트림 시작 실패: {error}"}
        except Exception as e:
            return {"error": f"스트림 시작 오류: {str(e)}"}
    
    async def send_sdp_answer(self, answer: Dict) -> Dict[str, Any]:
        """SDP Answer 전송"""
        if not self.stream_id:
            return {"error": "스트림이 생성되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks/streams/{self.stream_id}/sdp"
        payload = {
            "answer": answer,
            "session_id": self.session_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        print("✅ D-ID SDP Answer 전송 완료")
                        return {"success": True}
                    else:
                        error = await resp.text()
                        return {"error": f"SDP 전송 실패: {error}"}
        except Exception as e:
            return {"error": f"SDP 전송 오류: {str(e)}"}
    
    async def send_ice_candidate(self, candidate: Dict, sdp_mid: str = None, sdp_mline_index: int = None) -> Dict[str, Any]:
        """ICE Candidate 전송"""
        if not self.stream_id:
            return {"error": "스트림이 생성되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks/streams/{self.stream_id}/ice"
        payload = {
            "candidate": candidate.get("candidate") if isinstance(candidate, dict) else candidate,
            "sdpMid": sdp_mid or candidate.get("sdpMid", "0"),
            "sdpMLineIndex": sdp_mline_index if sdp_mline_index is not None else candidate.get("sdpMLineIndex", 0),
            "session_id": self.session_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        return {"success": True}
                    else:
                        error = await resp.text()
                        # ICE 후보 전송 실패는 치명적이지 않을 수 있음
                        print(f"⚠️ ICE 전송 경고: {error}")
                        return {"success": True, "warning": error}
        except Exception as e:
            return {"error": f"ICE 전송 오류: {str(e)}"}
    
    async def speak(self, text: str, voice: Dict = None) -> Dict[str, Any]:
        """아바타가 텍스트를 말하게 함 (실시간 스트리밍)"""
        if not self.stream_id:
            return {"error": "스트림이 생성되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks/streams/{self.stream_id}"
        payload = {
            "script": {
                "type": "text",
                "input": text,
                "provider": voice or DEFAULT_VOICE
            },
            "driver_url": "bank://lively",
            "config": {
                "stitch": True,
                "fluent": True
            },
            "session_id": self.session_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        print(f"✅ D-ID 스트리밍 발화 요청 완료")
                        return {
                            "success": True, 
                            "message": "음성 스트리밍 시작",
                            "duration": result.get("duration")
                        }
                    else:
                        error = await resp.text()
                        print(f"❌ D-ID 스트리밍 발화 실패: {error}")
                        return {"error": f"음성 생성 실패: {error}"}
        except Exception as e:
            return {"error": f"음성 생성 오류: {str(e)}"}
    
    async def close_stream(self) -> Dict[str, Any]:
        """스트림 종료"""
        if not self.stream_id:
            return {"success": True, "message": "스트림이 없습니다."}
        
        url = f"{DID_API_URL}/talks/streams/{self.stream_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=self._get_headers()) as resp:
                    stream_id = self.stream_id
                    self.stream_id = None
                    self.session_id = None
                    self.is_connected = False
                    print(f"✅ D-ID 스트림 종료: {stream_id}")
                    return {"success": True, "message": "스트림 종료됨"}
        except Exception as e:
            return {"error": f"스트림 종료 오류: {str(e)}"}


class DIDTalksService:
    """D-ID Talks API를 사용한 아바타 영상 생성 (비동기)"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or DID_API_KEY
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_talk(
        self, 
        text: str, 
        source_url: str = None,
        voice: Dict = None
    ) -> Dict[str, Any]:
        """말하는 아바타 영상 생성 요청"""
        if not self.api_key or self.api_key == "your_did_api_key_here":
            return {"error": "D-ID API 키가 설정되지 않았습니다."}
        
        url = f"{DID_API_URL}/talks"
        payload = {
            "source_url": source_url or DEFAULT_PRESENTER_IMAGE,
            "script": {
                "type": "text",
                "input": text,
                "provider": voice or DEFAULT_VOICE
            },
            "config": {
                "stitch": True,
                "result_format": "mp4"
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        return {
                            "success": True,
                            "talk_id": data.get("id"),
                            "status": data.get("status")
                        }
                    else:
                        error = await resp.text()
                        return {"error": f"Talk 생성 실패: {error}"}
        except Exception as e:
            return {"error": f"Talk 생성 오류: {str(e)}"}
    
    async def get_talk_status(self, talk_id: str) -> Dict[str, Any]:
        """Talk 상태 확인"""
        url = f"{DID_API_URL}/talks/{talk_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "success": True,
                            "status": data.get("status"),
                            "result_url": data.get("result_url"),
                            "duration": data.get("duration")
                        }
                    else:
                        error = await resp.text()
                        return {"error": f"상태 확인 실패: {error}"}
        except Exception as e:
            return {"error": f"상태 확인 오류: {str(e)}"}
    
    async def wait_for_talk(self, talk_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Talk 완료까지 대기"""
        for _ in range(timeout):
            result = await self.get_talk_status(talk_id)
            if "error" in result:
                return result
            
            if result.get("status") == "done":
                return result
            elif result.get("status") == "error":
                return {"error": "영상 생성 실패"}
            
            await asyncio.sleep(1)
        
        return {"error": "영상 생성 시간 초과"}


# FastAPI 라우터 생성
def create_did_router():
    """D-ID API 라우터 생성"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    from typing import Optional
    
    router = APIRouter(prefix="/api/did", tags=["D-ID Avatar"])
    
    # 스트리밍 서비스 인스턴스 관리
    streaming_sessions: Dict[str, DIDStreamingService] = {}
    talks_service = DIDTalksService()
    
    class CreateStreamRequest(BaseModel):
        session_id: str
        source_url: Optional[str] = None
    
    class SpeakRequest(BaseModel):
        session_id: str
        text: str
        voice_type: Optional[str] = "female"  # female or male
    
    class SDPRequest(BaseModel):
        session_id: str
        answer: Dict
    
    class ICERequest(BaseModel):
        session_id: str
        candidate: Dict
    
    class TalkRequest(BaseModel):
        text: str
        source_url: Optional[str] = None
        voice_type: Optional[str] = "female"
    
    @router.get("/status")
    async def get_did_status():
        """D-ID API 상태 확인"""
        api_key = os.getenv("DID_API_KEY", "")
        is_configured = api_key and api_key != "your_did_api_key_here"
        return {
            "available": is_configured,
            "message": "D-ID API 사용 가능" if is_configured else "D-ID API 키가 설정되지 않았습니다."
        }
    
    @router.post("/stream/create")
    async def create_stream(request: CreateStreamRequest):
        """스트리밍 세션 생성 - WebRTC Offer 반환"""
        service = DIDStreamingService()
        result = await service.create_stream(request.source_url)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        streaming_sessions[request.session_id] = service
        return result
    
    @router.post("/stream/start")
    async def start_stream(request: CreateStreamRequest):
        """스트리밍 시작 (SDP 교환 후 호출)"""
        service = streaming_sessions.get(request.session_id)
        if not service:
            raise HTTPException(status_code=404, detail="스트리밍 세션을 찾을 수 없습니다.")
        
        result = await service.start_stream()
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.post("/stream/sdp")
    async def send_sdp(request: SDPRequest):
        """SDP Answer 전송"""
        service = streaming_sessions.get(request.session_id)
        if not service:
            raise HTTPException(status_code=404, detail="스트리밍 세션을 찾을 수 없습니다.")
        
        result = await service.send_sdp_answer(request.answer)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.post("/stream/ice")
    async def send_ice(request: ICERequest):
        """ICE Candidate 전송"""
        service = streaming_sessions.get(request.session_id)
        if not service:
            raise HTTPException(status_code=404, detail="스트리밍 세션을 찾을 수 없습니다.")
        
        result = await service.send_ice_candidate(request.candidate)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.post("/stream/speak")
    async def stream_speak(request: SpeakRequest):
        """아바타가 말하게 함"""
        service = streaming_sessions.get(request.session_id)
        if not service:
            raise HTTPException(status_code=404, detail="스트리밍 세션을 찾을 수 없습니다.")
        
        voice = MALE_VOICE if request.voice_type == "male" else DEFAULT_VOICE
        result = await service.speak(request.text, voice)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.delete("/stream/{session_id}")
    async def close_stream(session_id: str):
        """스트리밍 세션 종료"""
        service = streaming_sessions.pop(session_id, None)
        if service:
            await service.close_stream()
        return {"success": True, "message": "스트림 종료됨"}
    
    @router.post("/talk/create")
    async def create_talk(request: TalkRequest):
        """비동기 Talk 영상 생성"""
        voice = MALE_VOICE if request.voice_type == "male" else DEFAULT_VOICE
        result = await talks_service.create_talk(
            text=request.text,
            source_url=request.source_url,
            voice=voice
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.get("/talk/{talk_id}")
    async def get_talk_status(talk_id: str):
        """Talk 상태 확인"""
        result = await talks_service.get_talk_status(talk_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    @router.get("/talk/{talk_id}/wait")
    async def wait_for_talk(talk_id: str, timeout: int = 60):
        """Talk 완료까지 대기"""
        result = await talks_service.wait_for_talk(talk_id, timeout)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    
    return router


# D-ID 사용 가능 여부 확인
def is_did_available() -> bool:
    """D-ID API 사용 가능 여부"""
    api_key = os.getenv("DID_API_KEY", "")
    return bool(api_key) and api_key != "your_did_api_key_here"


if __name__ == "__main__":
    # 테스트
    import asyncio
    
    async def test():
        if not is_did_available():
            print("D-ID API 키가 설정되지 않았습니다.")
            return
        
        service = DIDTalksService()
        result = await service.create_talk("안녕하세요, 저는 AI 면접관입니다.")
        print(result)
    
    asyncio.run(test())
