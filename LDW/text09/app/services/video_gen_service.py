import os
import uuid
import shutil
import sys
import asyncio

from ..config import (
    WAV2LIP_OUTPUT_FOLDER,
    WAV2LIP_DIR,
    WAV2LIP_INFERENCE_SCRIPT,
    WAV2LIP_CHECKPOINT,
    WAV2LIP_FACE_IMAGE,
    FFMPEG_EXE,
    logger,
)

async def _run_process_exec(cmd_list: list[str], cwd: str | None = None, env: dict | None = None) -> tuple[int, str, str]:
    """
    비동기 subprocess 실행 유틸리티
    - Windows에서 따옴표/공백 문제를 줄이기 위해 shell=False(exec)를 사용합니다.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd_list,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")

async def _convert_audio_to_wav_16k_mono(input_audio_path: str, output_wav_path: str) -> bool:
    """
    Wav2Lip 입력 안정화를 위해 mp3 등 입력 오디오를 wav(16k, mono, pcm_s16le)로 변환합니다.
    """
    if not FFMPEG_EXE:
        logger.error("[비디오 생성] FFmpeg 실행 파일을 찾지 못해 오디오 변환을 할 수 없습니다.")
        return False

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", input_audio_path,
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        output_wav_path,
    ]
    rc, out, err = await _run_process_exec(cmd)
    if rc != 0 or not os.path.exists(output_wav_path):
        logger.error("[비디오 생성] 오디오 wav 변환 실패")
        logger.error(f"[비디오 생성] FFmpeg stdout: {out}")
        logger.error(f"[비디오 생성] FFmpeg stderr: {err}")
        return False
    return True

async def generate_wav2lip_video(audio_filepath: str) -> str | None:
    """
    Wav2Lip-GAN을 사용하여 정지 이미지(data/man.png)와 입력 오디오로 립싱크 비디오를 생성합니다.

    Returns:
        성공 시 비디오 파일의 웹 접근 경로(/uploads/Wav2Lip_mp4/xxx.mp4),
        실패 시 None 반환
    """
    wav2lip_dir = os.path.abspath(WAV2LIP_DIR)
    inference_script = os.path.abspath(WAV2LIP_INFERENCE_SCRIPT)
    checkpoint_path = os.path.abspath(WAV2LIP_CHECKPOINT)
    face_image = os.path.abspath(WAV2LIP_FACE_IMAGE)

    # 출력 디렉토리 (config에서 절대경로로 통일됨)
    output_dir = os.path.abspath(WAV2LIP_OUTPUT_FOLDER)
    os.makedirs(output_dir, exist_ok=True)

    # 파일명 생성
    temp_filename = f"temp_wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    temp_filepath = os.path.join(output_dir, temp_filename)

    final_filename = f"wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    final_filepath = os.path.join(output_dir, final_filename)

    python_exe = sys.executable

    # ── 필수 파일 존재 여부 점검 ──
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

    if not os.path.exists(audio_filepath):
        logger.error(f"[비디오 생성] 입력 오디오 파일이 없습니다: {audio_filepath}")
        return None

    # ── 오디오를 wav로 변환 (안정화) ──
    wav_audio_path = os.path.join(output_dir, f"tts_{uuid.uuid4().hex[:8]}.wav")
    logger.info(f"[비디오 생성] 오디오 변환 시작: {audio_filepath} -> {wav_audio_path}")
    ok = await _convert_audio_to_wav_16k_mono(os.path.abspath(audio_filepath), wav_audio_path)
    if not ok:
        return None

    # 환경 변수(PYTHONPATH)에 Wav2Lip 경로 추가
    process_env = os.environ.copy()
    existing_pythonpath = process_env.get("PYTHONPATH", "")
    process_env["PYTHONPATH"] = wav2lip_dir + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    # ── Wav2Lip 실행 ──
    wav2lip_cmd = [
        python_exe,
        inference_script,
        "--checkpoint_path", checkpoint_path,
        "--face", face_image,
        "--audio", wav_audio_path,
        "--outfile", temp_filepath,
        "--pads", "0", "20", "0", "0",
    ]

    try:
        logger.info(f"[비디오 생성] Wav2Lip 실행 시작 (cwd={wav2lip_dir})")
        logger.info(f"[비디오 생성] 실행 명령: {' '.join(wav2lip_cmd)}")

        rc, out, err = await _run_process_exec(wav2lip_cmd, cwd=wav2lip_dir, env=process_env)

        if rc != 0:
            logger.error(f"[비디오 생성] Wav2Lip 실행 오류 (종료 코드: {rc})")
            logger.error(f"[비디오 생성] stdout: {out}")
            logger.error(f"[비디오 생성] stderr: {err}")
            return None

        if not os.path.exists(temp_filepath):
            logger.error(f"[비디오 생성] Wav2Lip 실행은 성공했으나 결과 파일이 생성되지 않았습니다: {temp_filepath}")
            logger.error(f"[비디오 생성] stdout: {out}")
            logger.error(f"[비디오 생성] stderr: {err}")
            return None

        logger.info("[비디오 생성] Wav2Lip 기본 비디오 생성 완료. 웹 재생 최적화 시작...")

        # ── FFmpeg로 웹 재생 친화 포맷으로 변환 ──
        if not FFMPEG_EXE:
            logger.warning("[비디오 생성] FFmpeg를 찾지 못해 최적화를 건너뜁니다. 원본을 그대로 사용합니다.")
            shutil.move(temp_filepath, final_filepath)
        else:
            ffmpeg_cmd = [
                FFMPEG_EXE,
                "-y",
                "-i", temp_filepath,
                "-vf", "scale=256:256,setsar=1:1",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                final_filepath,
            ]
            logger.info(f"[비디오 생성] FFmpeg 실행: {' '.join(ffmpeg_cmd)}")
            frc, fout, ferr = await _run_process_exec(ffmpeg_cmd)

            if frc != 0 or not os.path.exists(final_filepath):
                logger.error("[비디오 생성] FFmpeg 변환 실패. 원본 파일을 그대로 사용합니다.")
                logger.error(f"[비디오 생성] ffmpeg stdout: {fout}")
                logger.error(f"[비디오 생성] ffmpeg stderr: {ferr}")
                shutil.move(temp_filepath, final_filepath)
            else:
                # 변환 성공 시 임시 파일 삭제
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)

        # 오디오 임시 wav 삭제
        if os.path.exists(wav_audio_path):
            os.remove(wav_audio_path)

        logger.info(f"[비디오 생성] 최종 비디오 생성 완료: {final_filepath}")

        # 웹 접근 경로 반환
        return f"/uploads/Wav2Lip_mp4/{final_filename}"

    except Exception as e:
        logger.error(f"[비디오 생성] 비디오 생성 중 예외 발생: {e}")

        # 예외 시 임시 파일 정리
        for p in [temp_filepath, final_filepath, wav_audio_path]:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        return None