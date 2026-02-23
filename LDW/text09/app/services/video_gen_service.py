import os
import subprocess
import uuid
import logging
import shutil
import sys
from ..config import BASE_DIR, logger

def generate_wav2lip_video(audio_filepath: str) -> str:
    """
    Wav2Lip-GAN을 사용하여 정지 이미지(data/man.png)와 입력 오디오로 립싱크 비디오를 생성합니다.
    출력 결과는 지정된 폴더에 저장됩니다.
    """
    # 기본 경로 설정 (절대 경로 보장)
    base_dir = os.path.abspath(BASE_DIR)
    wav2lip_dir = os.path.join(base_dir, "Wav2Lip")
    inference_script = os.path.join(wav2lip_dir, "inference.py")
    checkpoint_path = os.path.join(wav2lip_dir, "checkpoints", "wav2lip_gan.pth")
    face_image = os.path.join(base_dir, "data", "man.png")
    
    # 출력 디렉토리 설정
    output_dir = os.path.join(base_dir, "uploads", "Wav2Lip_mp4")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1차 생성 비디오 경로 (Wav2Lip 결과)
    temp_filename = f"temp_wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    temp_filepath = os.path.join(output_dir, temp_filename)
    
    # 최종 비디오 경로
    final_filename = f"wav2lip_{uuid.uuid4().hex[:8]}.mp4"
    final_filepath = os.path.join(output_dir, final_filename)
    
    # OS별 파이썬 명령어 처리 (가상환경 고려하여 sys.executable 사용 권장)
    python_exe = sys.executable
    
    if not os.path.exists(wav2lip_dir):
        logger.error(f"Wav2Lip 디렉토리가 존재하지 않습니다: {wav2lip_dir}")
        return None

    # Wav2Lip 실행 명령어 구성 (Windows에서는 리스트보다 공백으로 구분된 문자열이 shell=True에서 안정적임)
    wav2lip_cmd = f'"{python_exe}" "{inference_script}" --checkpoint_path "{checkpoint_path}" --face "{face_image}" --audio "{audio_filepath}" --outfile "{temp_filepath}" --pads 0 20 0 0'
    
    # 환경 변수 설정 (Wav2Lip 디렉토리를 PYTHONPATH에 추가)
    process_env = os.environ.copy()
    process_env["PYTHONPATH"] = wav2lip_dir + (os.pathsep + process_env.get("PYTHONPATH", "") if process_env.get("PYTHONPATH") else "")

    try:
        # 파일 존재 여부 확인
        if not os.path.exists(face_image):
            logger.error(f"이미지 파일 없음: {face_image}")
            return None
        if not os.path.exists(checkpoint_path):
            logger.error(f"체크포인트 파일 없음: {checkpoint_path}")
            return None

        logger.info(f"Wav2Lip 립싱크 비디오 생성 시작... (입력 오디오: {audio_filepath})")
        
        # 입력 오디오 경로 절대 경로로 보장
        abs_audio_path = os.path.abspath(audio_filepath)
        # 명령어에서 상대 경로를 절대 경로로 교체 (인자가 따옴표로 감싸져 있으므로 주의)
        actual_wav2lip_cmd = wav2lip_cmd.replace(f'"{audio_filepath}"', f'"{abs_audio_path}"')
        
        logger.info(f"실행 명령어: {actual_wav2lip_cmd}")
        
        # Wav2Lip 디렉토리에서 실행
        result = subprocess.run(actual_wav2lip_cmd, cwd=wav2lip_dir, env=process_env, capture_output=True, encoding='utf-8', errors='replace', shell=True)
        
        if result.returncode != 0:
            logger.error(f"Wav2Lip 실행 오류 (코드 {result.returncode})")
            logger.error(f"Stdout: {result.stdout}")
            logger.error(f"Stderr: {result.stderr}")
            return None
            
        if not os.path.exists(temp_filepath):
            logger.error(f"Wav2Lip 실행은 성공했으나 결과 파일이 생성되지 않았습니다: {temp_filepath}")
            return None

        logger.info("Wav2Lip 기본 비디오 생성 완료. 웹 재생 최적화 중...")
        
        # FFmpeg를 사용하여 웹에서 재생 가능한 포맷으로 변환 및 256x256 리사이즈
        ffmpeg_cmd = f'ffmpeg -y -i "{temp_filepath}" -vf "scale=256:256,setsar=1:1" -c:v libx264 -pix_fmt yuv420p -c:a aac -strict experimental "{final_filepath}"'
        
        logger.info(f"FFmpeg 실행 명령어: {ffmpeg_cmd}")
        resize_result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, shell=True)
        
        if resize_result.returncode != 0:
            logger.error(f"FFmpeg 변환 오류: {resize_result.stderr}")
            # 리사이즈 실패 시 원본이라도 사용하기 위해 이동
            shutil.move(temp_filepath, final_filepath)
        else:
            # 임시 파일 삭제
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
        logger.info(f"립싱크 비디오 생성 최종 완료: {final_filepath}")
        return f"/uploads/Wav2Lip_mp4/{final_filename}"
        
    except Exception as e:
        logger.error(f"비디오 생성 중 예외 발생: {e}")
        return None
