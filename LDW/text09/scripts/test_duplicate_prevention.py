import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.llm_service import evaluate_answer

def test_duplicate_prevention():
    print("=== 중복 질문 방지 로직 테스트 시작 ===")
    
    # 가상의 상황 설정
    job_title = "Python Developer"
    applicant_name = "테스트 지원자"
    current_q_count = 2
    prev_question = "Python에서 리스트와 튜플의 차이점은 무엇인가요?"
    applicant_answer = "리스트는 수정 가능하고 튜플은 수정 불가능합니다."
    next_phase = "직무 기술(Technical Skill)"
    
    # 이력서 요약 (없음)
    resume_summary = "Python, Django 경험 있음."
    
    # 중요: 이미 질문한 목록 (중복 유도)
    # 여기에 'GIL' 관련 질문을 추가하고, LLM이 또 GIL을 묻는지 확인
    history_questions = [
        "간단히 자기소개를 해주세요.",
        "Python의 GIL(Global Interpreter Lock)에 대해 설명해주세요.",
        "Python에서 리스트와 튜플의 차이점은 무엇인가요?"
    ]
    
    print(f"\n[이전 질문 목록]:")
    for q in history_questions:
        print(f"- {q}")
        
    print(f"\n[예상 시나리오]: LLM은 'GIL'이나 '리스트/튜플' 관련 질문을 피하고 다른 질문(예: GC, Decorator 등)을 해야 합니다.")
    
    try:
        evaluation, next_question = evaluate_answer(
            job_title, 
            applicant_name, 
            current_q_count, 
            prev_question, 
            applicant_answer, 
            next_phase, 
            resume_summary=resume_summary, 
            ref_questions=None,
            history_questions=history_questions
        )
        
        print(f"\n[생성된 다음 질문]: {next_question}")
        
        # 간단한 검증
        if "GIL" in next_question or "리스트" in next_question:
            print(">>> 경고: 중복 유사 질문이 감지되었습니다! (실패 가능성)")
        else:
            print(">>> 성공: 중복된 질문을 피한 것으로 보입니다.")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    test_duplicate_prevention()
