"""
미디어 녹화/트랜스코딩 서비스 (하이브리드 아키텍처)
====================================================
aiortc + GStreamer 하이브리드 구조:

  ┌──────────────────────────────────────────────────────────────┐
  │                    WebRTC Track (aiortc)                      │
  │  video_track ──┬──▶ DeepFace 감정분석  (기존)                 │
  │                ├──▶ GStreamer 비디오 녹화 파이프라인             │
  │                └──▶ 시선 추적  (기존)                          │
  │                                                              │
  │  audio_track ──┬──▶ STT  (Deepgram / Whisper)  (기존)         │
  │                └──▶ GStreamer 오디오 녹화 파이프라인             │
  └──────────────────────────────────────────────────────────────┘

  면접 종료 후:
  ┌──────────────────────────────────────────────────────────────┐
  │  Celery Worker (비동기)                                       │
  │   1) GStreamer로 비디오+오디오 먹싱 (Muxing)                   │
  │   2) H.264/AAC 트랜스코딩 + 웹 최적화                         │
  │   3) 썸네일 생성                                              │
  │   4) 메타데이터 저장                                           │
  └──────────────────────────────────────────────────────────────┘

기술 선택 근거:
- aiortc: WebRTC 트랙 수신 및 raw 프레임 디코딩 담당 (기존 인프라 활용)
- GStreamer (via subprocess): 고성능 미디어 인코딩/먹싱/트랜스코딩 담당
  · aiortc의 MediaRecorder보다 코덱/포맷 유연성이 높음
  · CPU 사용량 효율적 (하드웨어 가속 가능)
  · Python GI 바인딩 없이 CLI 파이프라인으로 안정적 운용
"""

import os
import sys
import time
import asyncio
import uuid
import json
import subprocess
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ========== 설정 ==========

# 녹화 저장 디렉토리
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# 트랜스코딩 출력 디렉토리
TRANSCODED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "transcoded")
os.makedirs(TRANSCODED_DIR, exist_ok=True)

# 썸네일 디렉토리
THUMBNAILS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)


class RecordingStatus(str, Enum):
    """녹화 상태"""
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSCODING = "transcoding"
    READY = "ready"  # 트랜스코딩 완료, 다운로드 가능


@dataclass
class RecordingMetadata:
    """녹화 메타데이터"""
    session_id: str
    recording_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: RecordingStatus = RecordingStatus.IDLE
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    duration_sec: float = 0.0
    # 파일 경로
    raw_video_path: Optional[str] = None
    raw_audio_path: Optional[str] = None
    muxed_path: Optional[str] = None       # 오디오+비디오 합성
    transcoded_path: Optional[str] = None  # 웹 최적화 파일
    thumbnail_path: Optional[str] = None
    # 파일 크기
    file_size_bytes: int = 0
    # 코덱 정보
    video_codec: str = "rawvideo"
    audio_codec: str = "pcm_s16le"
    output_codec: str = "h264"
    # 해상도
    width: int = 640
    height: int = 480
    fps: int = 15
    # 오류
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "recording_id": self.recording_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "duration_sec": round(self.duration_sec, 2),
            "transcoded_path": self.transcoded_path,
            "thumbnail_path": self.thumbnail_path,
            "file_size_bytes": self.file_size_bytes,
            "output_codec": self.output_codec,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "error": self.error,
        }


# ========== GStreamer 유틸리티 ==========

def _check_gstreamer() -> bool:
    """GStreamer CLI (gst-launch-1.0) 사용 가능 여부 확인"""
    return shutil.which("gst-launch-1.0") is not None


def _check_ffmpeg() -> bool:
    """FFmpeg CLI 사용 가능 여부 확인 (GStreamer 폴백)"""
    return shutil.which("ffmpeg") is not None


# 도구 가용성
GSTREAMER_AVAILABLE = _check_gstreamer()
FFMPEG_AVAILABLE = _check_ffmpeg()
MEDIA_TOOL = "gstreamer" if GSTREAMER_AVAILABLE else ("ffmpeg" if FFMPEG_AVAILABLE else None)


# ========== 녹화 세션 매니저 ==========

class MediaRecordingService:
    """
    aiortc + GStreamer 하이브리드 미디어 녹화 서비스
    
    역할 분담:
    - aiortc: WebRTC 트랙에서 raw 프레임 추출 (기존 on_track 핸들러에 통합)
    - GStreamer/FFmpeg: raw 프레임을 파이프라인으로 실시간 인코딩 → 파일 저장
    
    아키텍처:
    1. 비디오: aiortc frame → raw BGR24 → stdin pipe → GStreamer/FFmpeg → .mp4
    2. 오디오: aiortc frame → raw PCM s16le → stdin pipe → GStreamer/FFmpeg → .wav
    3. 면접 종료 → Celery 태스크: 먹싱 + 트랜스코딩 + 썸네일
    """

    def __init__(self):
        self._sessions: Dict[str, RecordingMetadata] = {}
        self._video_processes: Dict[str, subprocess.Popen] = {}
        self._audio_processes: Dict[str, subprocess.Popen] = {}
        self._frame_counts: Dict[str, int] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

        if MEDIA_TOOL:
            print(f"🎬 [MediaRecording] 미디어 도구: {MEDIA_TOOL.upper()} ✅")
        else:
            print("⚠️ [MediaRecording] GStreamer/FFmpeg 미설치 — 녹화 비활성화")

    @property
    def available(self) -> bool:
        return MEDIA_TOOL is not None

    # ── 녹화 시작 ──

    def start_recording(self, session_id: str, width: int = 640, height: int = 480, fps: int = 15) -> RecordingMetadata:
        """
        세션의 녹화를 시작합니다.
        GStreamer/FFmpeg 서브프로세스를 stdin pipe 모드로 생성합니다.
        """
        if not self.available:
            raise RuntimeError("GStreamer/FFmpeg가 설치되어 있지 않습니다.")

        if session_id in self._sessions and self._sessions[session_id].status == RecordingStatus.RECORDING:
            return self._sessions[session_id]

        meta = RecordingMetadata(
            session_id=session_id,
            status=RecordingStatus.RECORDING,
            started_at=datetime.now().isoformat(),
            width=width,
            height=height,
            fps=fps,
        )

        # 파일 경로 설정
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        meta.raw_video_path = os.path.join(RECORDINGS_DIR, f"{session_id}_{ts}_video.mp4")
        meta.raw_audio_path = os.path.join(RECORDINGS_DIR, f"{session_id}_{ts}_audio.wav")

        # ── 비디오 인코딩 파이프라인 ──
        if GSTREAMER_AVAILABLE:
            video_cmd = [
                "gst-launch-1.0", "-e",
                "fdsrc", "fd=0", "!",
                f"video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1", "!",
                "videoconvert", "!",
                "x264enc", "tune=zerolatency", "speed-preset=ultrafast", "bitrate=1500", "!",
                "h264parse", "!",
                "mp4mux", "!",
                "filesink", f"location={meta.raw_video_path}",
            ]
        else:
            video_cmd = [
                "ffmpeg", "-y",
                "-f", "rawvideo",
                "-pixel_format", "bgr24",
                "-video_size", f"{width}x{height}",
                "-framerate", str(fps),
                "-i", "pipe:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-b:v", "1500k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                meta.raw_video_path,
            ]

        # ── 오디오 인코딩 파이프라인 ──
        if GSTREAMER_AVAILABLE:
            audio_cmd = [
                "gst-launch-1.0", "-e",
                "fdsrc", "fd=0", "!",
                "audio/x-raw,format=S16LE,rate=48000,channels=1", "!",
                "audioconvert", "!",
                "wavenc", "!",
                "filesink", f"location={meta.raw_audio_path}",
            ]
        else:
            audio_cmd = [
                "ffmpeg", "-y",
                "-f", "s16le",
                "-ar", "48000",
                "-ac", "1",
                "-i", "pipe:0",
                meta.raw_audio_path,
            ]

        try:
            self._video_processes[session_id] = subprocess.Popen(
                video_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._audio_processes[session_id] = subprocess.Popen(
                audio_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._frame_counts[session_id] = 0
            self._locks[session_id] = asyncio.Lock()
            self._sessions[session_id] = meta
            print(f"🔴 [MediaRecording] 녹화 시작: {session_id[:8]}... ({MEDIA_TOOL})")
            return meta
        except Exception as e:
            meta.status = RecordingStatus.FAILED
            meta.error = str(e)
            self._sessions[session_id] = meta
            print(f"❌ [MediaRecording] 녹화 시작 실패: {e}")
            raise

    # ── 프레임 쓰기 ──

    async def write_video_frame(self, session_id: str, frame_bytes: bytes):
        """
        aiortc에서 추출한 raw BGR24 프레임을 GStreamer/FFmpeg 파이프에 씁니다.
        
        Usage (on_track 핸들러 내부):
            img = frame.to_ndarray(format="bgr24")
            await recording_service.write_video_frame(session_id, img.tobytes())
        """
        proc = self._video_processes.get(session_id)
        if not proc or proc.poll() is not None:
            return

        try:
            proc.stdin.write(frame_bytes)
            self._frame_counts[session_id] = self._frame_counts.get(session_id, 0) + 1
        except (BrokenPipeError, OSError):
            pass

    async def write_audio_frame(self, session_id: str, pcm_bytes: bytes):
        """
        aiortc에서 추출한 raw PCM s16le 오디오를 파이프에 씁니다.
        
        Usage (on_track 핸들러 내부):
            audio_data = frame.to_ndarray()
            await recording_service.write_audio_frame(session_id, audio_data.astype(np.int16).tobytes())
        """
        proc = self._audio_processes.get(session_id)
        if not proc or proc.poll() is not None:
            return

        try:
            proc.stdin.write(pcm_bytes)
        except (BrokenPipeError, OSError):
            pass

    # ── 녹화 중지 ──

    async def stop_recording(self, session_id: str) -> RecordingMetadata:
        """
        녹화를 중지하고 파이프를 닫습니다.
        GStreamer -e 플래그 또는 FFmpeg stdin EOF로 정상 종료됩니다.
        """
        meta = self._sessions.get(session_id)
        if not meta:
            raise ValueError(f"세션 {session_id}의 녹화가 없습니다.")

        if meta.status != RecordingStatus.RECORDING:
            return meta

        meta.status = RecordingStatus.STOPPING
        meta.stopped_at = datetime.now().isoformat()

        # 소요 시간 계산
        if meta.started_at:
            start_dt = datetime.fromisoformat(meta.started_at)
            stop_dt = datetime.fromisoformat(meta.stopped_at)
            meta.duration_sec = (stop_dt - start_dt).total_seconds()

        # 파이프 닫기 → 프로세스 정상 종료 대기
        for name, procs in [("video", self._video_processes), ("audio", self._audio_processes)]:
            proc = procs.pop(session_id, None)
            if proc and proc.poll() is None:
                try:
                    proc.stdin.close()
                    proc.wait(timeout=15)
                    print(f"⬛ [MediaRecording] {name} 프로세스 종료: {session_id[:8]}...")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print(f"⚠️ [MediaRecording] {name} 프로세스 강제 종료: {session_id[:8]}...")
                except Exception as e:
                    print(f"⚠️ [MediaRecording] {name} 종료 오류: {e}")

        self._frame_counts.pop(session_id, None)
        self._locks.pop(session_id, None)

        # 파일 크기 확인
        for path in [meta.raw_video_path, meta.raw_audio_path]:
            if path and os.path.exists(path):
                meta.file_size_bytes += os.path.getsize(path)

        meta.status = RecordingStatus.COMPLETED
        print(f"✅ [MediaRecording] 녹화 완료: {session_id[:8]}... "
              f"({meta.duration_sec:.1f}초, {meta.file_size_bytes / 1024 / 1024:.1f}MB)")
        return meta

    # ── 트랜스코딩 (GStreamer 활용) ──

    @staticmethod
    def transcode(
        session_id: str,
        video_path: str,
        audio_path: str,
        output_dir: str = TRANSCODED_DIR,
        target_codec: str = "h264",
        target_bitrate: int = 2000,
        target_audio_bitrate: int = 128,
    ) -> Dict[str, Any]:
        """
        비디오+오디오를 먹싱하고 웹 최적화 H.264/AAC MP4로 트랜스코딩합니다.
        GStreamer 우선, FFmpeg 폴백.
        
        이 메서드는 Celery 태스크에서 호출됩니다 (동기).
        
        Returns:
            {"output_path": str, "thumbnail_path": str, "duration_sec": float, "file_size_bytes": int}
        """
        output_filename = f"{session_id}_final.mp4"
        output_path = os.path.join(output_dir, output_filename)
        thumbnail_path = os.path.join(THUMBNAILS_DIR, f"{session_id}_thumb.jpg")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"비디오 파일 없음: {video_path}")

        # 오디오 파일이 없으면 비디오만 트랜스코딩
        has_audio = audio_path and os.path.exists(audio_path)

        # ── GStreamer 먹싱+트랜스코딩 파이프라인 ──
        if GSTREAMER_AVAILABLE:
            if has_audio:
                mux_cmd = [
                    "gst-launch-1.0", "-e",
                    # 비디오 소스
                    "filesrc", f"location={video_path}", "!",
                    "decodebin", "name=demux",
                    # 오디오 소스
                    "filesrc", f"location={audio_path}", "!",
                    "decodebin", "name=demux_audio",
                    # 비디오 트랜스코딩
                    "demux.", "!",
                    "queue", "!",
                    "videoconvert", "!",
                    "x264enc", f"bitrate={target_bitrate}", "speed-preset=medium",
                    "tune=zerolatency", "!",
                    "h264parse", "!",
                    "mux.video_0",
                    # 오디오 트랜스코딩
                    "demux_audio.", "!",
                    "queue", "!",
                    "audioconvert", "!",
                    "audioresample", "!",
                    "avenc_aac", f"bitrate={target_audio_bitrate * 1000}", "!",
                    "aacparse", "!",
                    "mux.audio_0",
                    # MP4 먹서
                    "mp4mux", "name=mux", "faststart=true", "!",
                    "filesink", f"location={output_path}",
                ]
            else:
                mux_cmd = [
                    "gst-launch-1.0", "-e",
                    "filesrc", f"location={video_path}", "!",
                    "decodebin", "!",
                    "videoconvert", "!",
                    "x264enc", f"bitrate={target_bitrate}", "speed-preset=medium", "!",
                    "h264parse", "!",
                    "mp4mux", "faststart=true", "!",
                    "filesink", f"location={output_path}",
                ]

        # ── FFmpeg 폴백 ──
        elif FFMPEG_AVAILABLE:
            if has_audio:
                mux_cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-b:v", f"{target_bitrate}k",
                    "-c:a", "aac",
                    "-b:a", f"{target_audio_bitrate}k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-shortest",
                    output_path,
                ]
            else:
                mux_cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-b:v", f"{target_bitrate}k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ]
        else:
            raise RuntimeError("GStreamer/FFmpeg 미설치")

        print(f"🔄 [Transcode] 트랜스코딩 시작: {session_id[:8]}...")
        result = subprocess.run(mux_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"트랜스코딩 실패: {result.stderr[:500]}")

        # ── 썸네일 생성 ──
        thumb_result = _generate_thumbnail(output_path, thumbnail_path)

        # ── 파일 크기 / 길이 ──
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        duration = _get_duration(output_path)

        # ── raw 파일 정리 ──
        for raw_path in [video_path, audio_path]:
            if raw_path and os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                    print(f"🗑️ [Transcode] 원본 제거: {os.path.basename(raw_path)}")
                except OSError:
                    pass

        print(f"✅ [Transcode] 완료: {session_id[:8]}... "
              f"({duration:.1f}초, {file_size / 1024 / 1024:.1f}MB)")

        return {
            "output_path": output_path,
            "thumbnail_path": thumbnail_path if thumb_result else None,
            "duration_sec": duration,
            "file_size_bytes": file_size,
        }

    # ── 녹화 정보 조회 ──

    def get_recording(self, session_id: str) -> Optional[RecordingMetadata]:
        return self._sessions.get(session_id)

    def get_all_recordings(self) -> List[Dict]:
        return [m.to_dict() for m in self._sessions.values()]

    # ── 파일 삭제 ──

    def delete_recording(self, session_id: str) -> bool:
        """녹화 관련 모든 파일 삭제"""
        meta = self._sessions.pop(session_id, None)
        if not meta:
            return False

        for path in [meta.raw_video_path, meta.raw_audio_path, meta.muxed_path,
                      meta.transcoded_path, meta.thumbnail_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        return True

    # ── 정리 ──

    async def cleanup(self):
        """모든 녹화 프로세스 정리 (서버 종료 시)"""
        for sid in list(self._video_processes.keys()):
            try:
                await self.stop_recording(sid)
            except Exception:
                pass


# ========== 헬퍼 함수 ==========

def _generate_thumbnail(video_path: str, thumb_path: str) -> bool:
    """비디오에서 첫 번째 키프레임 썸네일 추출"""
    try:
        if GSTREAMER_AVAILABLE:
            cmd = [
                "gst-launch-1.0", "-e",
                "filesrc", f"location={video_path}", "!",
                "decodebin", "!",
                "videoconvert", "!",
                "video/x-raw,format=RGB", "!",
                "pngenc", "snapshot=true", "!",
                "filesink", f"location={thumb_path.replace('.jpg', '.png')}",
            ]
            # GStreamer는 png 생성 후 변환
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0:
                png_path = thumb_path.replace('.jpg', '.png')
                if os.path.exists(png_path):
                    # FFmpeg로 PNG→JPG 변환 (있으면)
                    if FFMPEG_AVAILABLE:
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", png_path, "-q:v", "3", thumb_path],
                            capture_output=True, timeout=10,
                        )
                        os.remove(png_path)
                        return os.path.exists(thumb_path)
                    else:
                        # PNG 그대로 사용
                        os.rename(png_path, thumb_path)
                        return True
        elif FFMPEG_AVAILABLE:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-ss", "00:00:01",
                "-frames:v", "1",
                "-q:v", "3",
                thumb_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0
    except Exception as e:
        print(f"⚠️ [Thumbnail] 생성 실패: {e}")
    return False


def _get_duration(video_path: str) -> float:
    """비디오 길이(초) 조회"""
    try:
        if FFMPEG_AVAILABLE:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip()) if result.returncode == 0 else 0.0
        elif GSTREAMER_AVAILABLE:
            cmd = [
                "gst-discoverer-1.0", video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            # gst-discoverer 출력에서 Duration 파싱
            for line in result.stdout.split("\n"):
                if "Duration" in line:
                    import re
                    match = re.search(r"(\d+):(\d+):(\d+)\.(\d+)", line)
                    if match:
                        h, m, s, ms = match.groups()
                        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))
    except Exception:
        pass
    return 0.0


# ========== 싱글톤 인스턴스 ==========

recording_service = MediaRecordingService()
