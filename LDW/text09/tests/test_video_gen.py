"""
비디오 생성 서비스 단위 테스트
- config.py의 비디오 관련 경로 설정 검증
- 필수 파일(inference.py, wav2lip_gan.pth, man.png) 존재 여부 확인
- tts_service.py의 반환값 형태 검증
"""
import os
import sys

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def test_config_video_paths():
    """config.py에 비디오 관련 경로 설정이 올바르게 정의되어 있는지 검증"""
    print("=" * 60)
    print("  [테스트 1] config.py 비디오 경로 설정 검증")
    print("=" * 60)

    try:
        from app.config import (
            WAV2LIP_OUTPUT_FOLDER,
            WAV2LIP_DIR,
            WAV2LIP_INFERENCE_SCRIPT,
            WAV2LIP_CHECKPOINT,
            WAV2LIP_FACE_IMAGE,
            BASE_DIR,
        )
        print(f"  [OK] BASE_DIR: {BASE_DIR}")
        print(f"  [OK] WAV2LIP_OUTPUT_FOLDER: {WAV2LIP_OUTPUT_FOLDER}")
        print(f"  [OK] WAV2LIP_DIR: {WAV2LIP_DIR}")
        print(f"  [OK] WAV2LIP_INFERENCE_SCRIPT: {WAV2LIP_INFERENCE_SCRIPT}")
        print(f"  [OK] WAV2LIP_CHECKPOINT: {WAV2LIP_CHECKPOINT}")
        print(f"  [OK] WAV2LIP_FACE_IMAGE: {WAV2LIP_FACE_IMAGE}")
        print("  ✅ config.py 경로 설정 로드 성공")
        return True
    except ImportError as e:
        print(f"  ❌ config.py 임포트 실패: {e}")
        return False


def test_wav2lip_required_files():
    """Wav2Lip 비디오 생성에 필요한 파일들이 존재하는지 확인"""
    print("\n" + "=" * 60)
    print("  [테스트 2] Wav2Lip 필수 파일 존재 여부 확인")
    print("=" * 60)

    try:
        from app.config import (
            WAV2LIP_DIR,
            WAV2LIP_INFERENCE_SCRIPT,
            WAV2LIP_CHECKPOINT,
            WAV2LIP_FACE_IMAGE,
        )
    except ImportError:
        print("  ❌ config.py 임포트 실패 - 이 테스트를 건너뜁니다.")
        return False

    all_ok = True
    checks = [
        ("Wav2Lip 디렉토리", WAV2LIP_DIR, True),
        ("추론 스크립트 (inference.py)", WAV2LIP_INFERENCE_SCRIPT, False),
        ("GAN 가중치 (wav2lip_gan.pth)", WAV2LIP_CHECKPOINT, False),
        ("면접관 얼굴 이미지 (man.png)", WAV2LIP_FACE_IMAGE, False),
    ]

    for name, path, is_dir in checks:
        abs_path = os.path.abspath(path)
        exists = os.path.isdir(abs_path) if is_dir else os.path.isfile(abs_path)
        status = "OK" if exists else "MISSING"
        icon = "✅" if exists else "⚠️"
        print(f"  [{status}] {name}: {abs_path} {icon}")
        if not exists:
            all_ok = False

    if all_ok:
        print("  ✅ 모든 필수 파일이 존재합니다. 비디오 생성이 가능합니다.")
    else:
        print("  ⚠️ 일부 파일이 누락되었습니다. 비디오 생성 시 오디오 폴백이 사용됩니다.")

    return all_ok


def test_output_directory_creation():
    """WAV2LIP_OUTPUT_FOLDER 디렉토리가 자동 생성되는지 확인"""
    print("\n" + "=" * 60)
    print("  [테스트 3] 비디오 출력 디렉토리 자동 생성 확인")
    print("=" * 60)

    try:
        from app.config import WAV2LIP_OUTPUT_FOLDER
    except ImportError:
        print("  ❌ config.py 임포트 실패")
        return False

    abs_path = os.path.abspath(WAV2LIP_OUTPUT_FOLDER)
    exists = os.path.isdir(abs_path)

    if exists:
        print(f"  [OK] 출력 디렉토리가 존재합니다: {abs_path} ✅")
        return True
    else:
        print(f"  [FAIL] 출력 디렉토리가 생성되지 않았습니다: {abs_path} ❌")
        return False


def test_tts_service_return_format():
    """tts_service.py의 generate_tts_audio()가 dict 형태를 반환하는지 소스코드 검증"""
    print("\n" + "=" * 60)
    print("  [테스트 4] TTS 서비스 반환값 형식 검증 (소스코드 분석)")
    print("=" * 60)

    tts_service_path = os.path.join(PROJECT_ROOT, "app", "services", "tts_service.py")
    if not os.path.exists(tts_service_path):
        print(f"  ❌ tts_service.py 파일을 찾을 수 없습니다: {tts_service_path}")
        return False

    with open(tts_service_path, "r", encoding="utf-8") as f:
        content = f.read()

    # dict 반환 패턴 확인
    has_video_return = '"type": "video"' in content
    has_audio_return = '"type": "audio"' in content
    has_url_key = '"url":' in content

    if has_video_return and has_audio_return and has_url_key:
        print("  [OK] 비디오 성공 시 dict 반환: {'url': ..., 'type': 'video'} ✅")
        print("  [OK] 비디오 실패 시 dict 반환: {'url': ..., 'type': 'audio'} ✅")
        return True
    else:
        print("  ❌ TTS 서비스 반환 형식이 올바르지 않습니다.")
        if not has_url_key:
            print("    - 'url' 키가 반환값에 없습니다.")
        if not has_video_return:
            print("    - 'type': 'video' 반환 패턴이 없습니다.")
        if not has_audio_return:
            print("    - 'type': 'audio' 반환 패턴이 없습니다.")
        return False


def test_playaudio_video_audio_branching():
    """app.js의 playAudio() 함수가 mp4/mp3를 분기 처리하는지 소스코드 검증"""
    print("\n" + "=" * 60)
    print("  [테스트 5] 프론트엔드 playAudio() 비디오/오디오 분기 검증")
    print("=" * 60)

    appjs_path = os.path.join(PROJECT_ROOT, "static", "app.js")
    if not os.path.exists(appjs_path):
        print(f"  ❌ app.js 파일을 찾을 수 없습니다: {appjs_path}")
        return False

    with open(appjs_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_mp4_check = ".endsWith('.mp4')" in content
    has_audio_element = "new Audio(url)" in content
    has_video_element = "document.getElementById('ai-video')" in content

    all_ok = has_mp4_check and has_audio_element and has_video_element

    if has_mp4_check:
        print("  [OK] mp4 확장자 분기 로직 존재 ✅")
    else:
        print("  ❌ mp4 확장자 분기 로직이 없습니다.")

    if has_video_element:
        print("  [OK] <video> 태그 재생 로직 존재 (비디오용) ✅")
    else:
        print("  ❌ <video> 태그 재생 로직이 없습니다.")

    if has_audio_element:
        print("  [OK] <audio> 요소 재생 로직 존재 (오디오 폴백용) ✅")
    else:
        print("  ❌ <audio> 요소 재생 로직이 없습니다.")

    if all_ok:
        print("  ✅ playAudio() 함수가 비디오/오디오를 올바르게 분기 처리합니다.")

    return all_ok


def test_interview_router_audio_type():
    """interview.py 라우터가 audio_type 필드를 반환하는지 소스코드 검증"""
    print("\n" + "=" * 60)
    print("  [테스트 6] 인터뷰 라우터 audio_type 필드 검증")
    print("=" * 60)

    router_path = os.path.join(PROJECT_ROOT, "app", "routers", "interview.py")
    if not os.path.exists(router_path):
        print(f"  ❌ interview.py 파일을 찾을 수 없습니다: {router_path}")
        return False

    with open(router_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_audio_type = '"audio_type": audio_type' in content
    has_tts_result = "tts_result" in content

    if has_audio_type and has_tts_result:
        print("  [OK] audio_type 필드가 응답에 포함됨 ✅")
        print("  [OK] tts_result dict 처리 로직 존재 ✅")
        print("  ✅ 인터뷰 라우터가 비디오/오디오 타입을 올바르게 반환합니다.")
        return True
    else:
        print("  ❌ audio_type 필드 또는 tts_result 처리 로직이 없습니다.")
        return False


if __name__ == "__main__":
    print("\n🔍 AI 면접 시뮬레이션 - 비디오 생성 수정사항 검증 테스트\n")

    results = []
    results.append(("config.py 경로 설정", test_config_video_paths()))
    results.append(("Wav2Lip 필수 파일", test_wav2lip_required_files()))
    results.append(("출력 디렉토리 생성", test_output_directory_creation()))
    results.append(("TTS 반환값 형식", test_tts_service_return_format()))
    results.append(("playAudio() 분기", test_playaudio_video_audio_branching()))
    results.append(("인터뷰 라우터", test_interview_router_audio_type()))

    print("\n" + "=" * 60)
    print("  📊 테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)

    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")

    print(f"\n  합계: {passed} 통과 / {failed} 실패 (전체 {len(results)}개)")
    print("=" * 60)
