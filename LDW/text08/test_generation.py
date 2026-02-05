import asyncio
from services.interview_service import InterviewService
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_question_generation():
    print("🧪 질문 생성 테스트 시작...")
    
    # 1. Initialize Service
    try:
        service = InterviewService()
        print("✅ InterviewService 초기화 완료")
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return

    # 2. Start Interview (First Question)
    print("\n[단계 1] 면접 시작 (첫 질문 생성)")
    try:
        # Mocking user input
        name = "테스트지원자"
        job_title = "백엔드 개발자"
        
        start_result = await service.start_interview(name, job_title)
        session_id = start_result["session_id"]
        first_question = start_result["question"]
        
        print(f"👉 Session ID: {session_id}")
        print(f"👉 첫 질문: {first_question}")
        
        if not first_question or len(first_question) < 5:
            print("❌ 첫 질문 생성 실패 또는 너무 짧음")
        else:
            print("✅ 첫 질문 생성 성공")
            
    except Exception as e:
        print(f"❌ 면접 시작 중 오류: {e}")
        return

    # 3. Process Answer (Follow-up or Next Question)
    print("\n[단계 2] 답변 제출 및 다음 질문 생성")
    try:
        # Mocking user answer
        user_answer = "저는 Python과 Django를 사용하여 RESTful API를 설계하고 개발한 경험이 있습니다. 대규모 트래픽 처리를 위해 Redis 캐싱을 도입하기도 했습니다."
        print(f"📝 사용자 답변: {user_answer}")
        
        result = await service.process_answer(session_id, first_question, user_answer)
        
        evaluation = result["evaluation"]
        next_question = result["next_question"]
        is_follow_up = result["is_follow_up"]
        
        print(f"📊 평가 점수: {evaluation.get('score')}")
        print(f"💡 피드백: {evaluation.get('feedback')}")
        print(f"🔄 꼬리 질문 여부: {is_follow_up}")
        print(f"👉 다음 질문: {next_question}")
        
        if not next_question:
            print("❌ 다음 질문 생성 실패")
        else:
            print("✅ 다음 질문 생성 성공")
            
    except Exception as e:
        print(f"❌ 답변 처리 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(test_question_generation())
