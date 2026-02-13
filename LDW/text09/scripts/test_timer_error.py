import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import os
import uuid

BASE_URL = "http://localhost:5000"

def test_empty_answer_submission():
    print("--- 타이머 종료(빈 답변) 시나리오 테스트 시작 ---")
    
    # 1. 테스트용 더미 오디오 파일 생성 (매우 작은 크기)
    dummy_audio = "test_empty.webm"
    with open(dummy_audio, "wb") as f:
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x44\xac\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00")
    
    try:
        # 실제 DB에 존재하는 데이터가 필요하므로, 최근 면접 번호를 가져오거나 새로 시작해야 함
        # 여기서는 API가 500 오류를 뱉지 않고 200 응답(성공 혹은 논리적 오류 메시지)을 주는지 확인
        
        with open(dummy_audio, 'rb') as audio_file:
            files = {
                'audio': (dummy_audio, audio_file, 'audio/webm')
            }
            data = {
                'interview_number': str(uuid.uuid4()), # 랜덤 번호로 에러 핸들링 확인
                'applicant_name': '테스트 지원자',
                'job_title': '백엔드 개발자',
                'answer_time': '90초'
            }
            
            print(f"2. 빈 답변 데이터 전송 중... (Interview: {data['interview_number']})")
            resp = requests.post(f"{BASE_URL}/api/interview/answer", data=data, files=files)
            
        print(f"3. 응답 상태 코드: {resp.status_code}")
        result = resp.json()
        print(f"4. 응답 본문: {result}")
        
        if resp.status_code == 200:
            if not result.get('success') and "진행 중인 면접을 찾을 수 없습니다" in result.get('message', ''):
                print("SUCCESS: 서버가 예외 상황을 인식하고 안전하게 오류 메시지를 반환함.")
            elif result.get('success'):
                print("SUCCESS: 답변 제출이 정상적으로 수락됨.")
            else:
                print(f"WARNING: 의도치 않은 결과 - {result}")
        else:
            print(f"FAILURE: 서버 오류 발생 (Status {resp.status_code})")
            
    except Exception as e:
        print(f"EXCEPTION: 테스트 중 오류 발생 - {e}")
    finally:
        if os.path.exists(dummy_audio):
            os.remove(dummy_audio)

if __name__ == "__main__":
    test_empty_answer_submission()
