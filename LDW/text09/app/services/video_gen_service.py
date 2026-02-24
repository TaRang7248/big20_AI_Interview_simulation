import os
import subprocess
import uuid
import logging
import shutil
import sys
from ..config import BASE_DIR, WAV2LIP_OUTPUT_FOLDER, WAV2LIP_DIR, WAV2LIP_INFERENCE_SCRIPT, WAV2LIP_CHECKPOINT, WAV2LIP_FACE_IMAGE, logger

import asyncio

async def generate_wav2lip_video(audio_filepath: str) -> str:
    """
    Wav2Lip-GAN을 사용하여 정지 이미지(data/man.png)와 입력 오디오로 립싱크 비디오를 생성합니다.
    비동기 subprocess를 사용하여 서버의 블로킹을 최소화합니다.

    Args:
        audio_filepath: TTS로 생성된 오디오 파일 경로

    Returns:
        성공 시 비디오 파일의 웹 접근 경로, 실패 시 None
    """
    # 기본 경로 설정 (config.py에서 정의된 절대 경로 사용)
    base_dir = os.path.abspath(BASE_DIR)
    wav2lip_dir = os.path.abspath(WAV2LIP_DIR)
    inference_script = os.path.abspath(WAV2LIP_INFERENCE_SCRIPT)
    checkpoint_path = os.path.abspath(WAV2LIP_CHECKPOINT)
    face_image = os.path.abspath(WAV2LIP_FACE_IMAGE)
    
    # 출력 디렉토리 설정 (config.py에서 정의된 경로 사용)
    output_dir = os.path.abspath(WAV2LIP_OUTPUT_FOLDER)
    os.makedirs(output_dir, exist_ok=True)
    
    # 1차 생성 비디오 경로 (Wav2Lip 결과 - 임시 파일)
    temp_filename = f"temp_wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    temp_filepath = os.path.join(output_dir, temp_filename)
    
    # 최종 비디오 경로 (웹 재생 최적화된 파일)
    final_filename = f"wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    final_filepath = os.path.join(output_dir, final_filename)
    
    # 파이썬 실행 파일 경로 (가상환경 고려)
    python_exe = sys.executable
    
    # ── 필수 파일 존재 여부 사전 점검 ──
    if not os.path.exists(wav2lip_dir):
        logger.error(f"[비디오 생성] Wav2Lip 디렉토리가 존재하지 않습니다: {wav2lip_dir}")
        return None
    
    if not os.path.exists(inference_script):
        logger.error(f"[비디오 생성] Wav2Lip 추론 스크립트가 존재하지 않습니다: {inference_script}")
        return None

    if not os.path.exists(face_image):
        logger.error(f"[비디오 생성] 면접관 얼굴 이미지 파일이 없습니다: {face_image}")
        return None
        
    if not os.path.exists(checkpoint_path):
        logger.error(f"[비디오 생성] Wav2Lip GAN 가중치 파일이 없습니다: {checkpoint_path}")
        return None

    # Wav2Lip 실행 명령어 구성
    # (Windows에서는 따옴표로 감싸서 공백 경로 처리)
    wav2lip_cmd = (
        f'"{python_exe}" "{inference_script}" '
        f'--checkpoint_path "{checkpoint_path}" '
        f'--face "{face_image}" '
        f'--audio "{os.path.abspath(audio_filepath)}" '
        f'--outfile "{temp_filepath}" '
        f'--pads 0 20 0 0'
    )
    
    # 환경 변수 설정 (Wav2Lip 디렉토리를 PYTHONPATH에 추가)
    process_env = os.environ.copy()
    existing_pythonpath = process_env.get("PYTHONPATH", "")
    process_env["PYTHONPATH"] = wav2lip_dir + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    try:
        logger.info(f"[비디오 생성] Wav2Lip 립싱크 비디오 생성 시작... (입력 오디오: {audio_filepath})")
        logger.info(f"[비디오 생성] 실행 명령어: {wav2lip_cmd}")
        
        # Wav2Lip 디렉토리에서 비동기로 실행 (서버 블로킹 방지)
        process = await asyncio.create_subprocess_shell(
            wav2lip_cmd,
            cwd=wav2lip_dir,
            env=process_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"[비디오 생성] Wav2Lip 실행 오류 (종료 코드: {process.returncode})")
            logger.error(f"[비디오 생성] 표준 출력: {stdout.decode('utf-8', errors='replace')}")
            logger.error(f"[비디오 생성] 오류 출력: {stderr.decode('utf-8', errors='replace')}")
            return None
            
        if not os.path.exists(temp_filepath):
            logger.error(f"[비디오 생성] Wav2Lip 실행은 성공했으나 결과 파일이 생성되지 않았습니다: {temp_filepath}")
            return None

        logger.info("[비디오 생성] Wav2Lip 기본 비디오 생성 완료. 웹 재생 최적화 중...")
        
        # FFmpeg를 사용하여 웹에서 재생 가능한 포맷으로 변환 및 256x256 리사이즈 (비동기 처리)
        ffmpeg_cmd = (
            f'ffmpeg -y -i "{temp_filepath}" '
            f'-vf "scale=256:256,setsar=1:1" '
            f'-c:v libx264 -pix_fmt yuv420p '
            f'-c:a aac -strict experimental '
            f'"{final_filepath}"'
        )
        
        logger.info(f"[비디오 생성] FFmpeg 변환 명령어: {ffmpeg_cmd}")
        ffmpeg_process = await asyncio.create_subprocess_shell(
            ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await ffmpeg_process.wait()
        
        if ffmpeg_process.returncode != 0:
            logger.error("[비디오 생성] FFmpeg 변환 실패. 원본 파일을 그대로 사용합니다.")
            # 리사이즈 실패 시 원본이라도 사용하기 위해 이동
            shutil.move(temp_filepath, final_filepath)
        else:
            # 임시 파일 삭제
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
        logger.info(f"[비디오 생성] 립싱크 비디오 생성 최종 완료: {final_filepath}")
        return f"/uploads/Wav2Lip_mp4/{final_filename}"
        
    except Exception as e:
        logger.error(f"[비디오 생성] 비디오 생성 중 예외 발생: {e}")
        return None
