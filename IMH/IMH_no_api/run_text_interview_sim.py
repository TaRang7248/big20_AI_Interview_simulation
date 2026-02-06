import asyncio
import uuid
from IMH.IMH_no_api.services.interview_engine import interview_engine
from IMH.IMH_no_api.services.persona_service import persona_service
from IMH.IMH_no_api.services.evaluation_service import evaluation_service
from IMH.IMH_no_api.services.summary_service import summary_service
from IMH.IMH_no_api.schemas.interview_schemas import InterviewerPersona
# from langchain_classic.memory import ConversationSummaryBufferMemory (Unused)
from IMH.IMH_no_api.services.llm import ollama_service

async def run_interview_loop():
    print("=== [SIMULATION] AI Interviewer Text Session ===")
    
    # 1. 면접 설정 (가상 데이터)
    session_id = str(uuid.uuid4())
    persona = InterviewerPersona.PRESSURE # 압박 면접 테스트
    target_company = "BigTech AI"
    target_job = "Senior Backend Engineer"
    resume_summary = "8 years of experience in Python, distributed systems, and LLM ops."
    skills = "Python, FastAPI, Redis, Kubernetes, LangChain"

    # 모델 선택 UI (번호 기반 선택)
    from IMH.IMH_no_api.core.config import settings
    print("\n[AI 면접관 모델 선택]")
    model_keys = list(settings.SUPPORTED_MODELS.keys())
    for i, key in enumerate(model_keys, 1):
        info = settings.SUPPORTED_MODELS[key]
        print(f"{i}. {info['name']} ({key}) - {info['description']}")
    
    try:
        choice = input(f"\n원하는 모델 번호를 선택하세요 (1-{len(model_keys)}, 기본: 2): ")
        if not choice.strip():
            selected_tier = "QWEN3"
        elif choice.isdigit() and 1 <= int(choice) <= len(model_keys):
            selected_tier = model_keys[int(choice) - 1]
        else:
            selected_tier = "QWEN3"
    except Exception:
        selected_tier = "QWEN3"

    print(f"\n>> {selected_tier} 모델을 선택하셨습니다.\n")

    # 3. 메모리 및 상태 초기화
    from langchain_classic.memory import ConversationBufferWindowMemory
    memory = ConversationBufferWindowMemory(
        return_messages=True,
        memory_key="history",
        k=settings.MEMORY_WINDOW_K
    )

    print(f"\n[INFO] 페르소나: {persona.value} | 세션: {session_id}")
    print(f"[INFO] 직무: {target_job} | 지원회사: {target_company}")
    print("-" * 50)

    user_input = "면접을 시작하겠습니다. 인사해 주세요."
    turn_count = 0
    max_turns = 6 # 6턴 동안 심층 면접 진행
    summary_slot = "아직 요약된 내용이 없습니다."

    while turn_count < max_turns:
        # 매 3턴마다 대화 요약 업데이트 (컨텍스트 압축 및 중요 정보 보존)
        if turn_count > 0 and turn_count % 3 == 0:
            print(f"\n[시스템] 대화 이력을 요약 중입니다... (VRAM 최적화)")
            history_vars = memory.load_memory_variables({})
            full_history = str(history_vars.get("history", ""))
            summary_slot = await summary_service.summarize_history(full_history, model_name=selected_tier)

        # 시스템 프롬프트 준비 (최신 요약본 반영)
        system_prompt = persona_service.get_system_prompt(
            persona=persona,
            target_company=target_company,
            target_job=target_job,
            resume_summary=resume_summary,
            skills=skills,
            summary_slot=summary_slot
        )

        # 질문 생성
        try:
            print("\nAI 면접관이 생각 중입니다...")
            question_data = await interview_engine.generate_question(
                session_id=session_id,
                user_input=user_input,
                system_prompt=system_prompt,
                memory=memory,
                model_name=selected_tier
            )

            print(f"\n[AI 면접관]: {question_data.question}")
            print(f"(의도: {question_data.intent.type} - {question_data.intent.detail})")
            
            # 히스토리에 기록
            memory.save_context({"input": user_input}, {"output": question_data.question})

            # 사용자 답변 입력
            user_input = input("\n[지원자(나)]: ")
            if user_input.lower() in ["exit", "quit", "종료"]:
                break
            
            turn_count += 1

        except Exception as e:
            print(f"오류 발생: {e}")
            break

    print("\n" + "=" * 50)
    print("면접이 종료되었습니다. 평가를 진행합니다...")
    
    # 4. 평가 수행
    history_vars = memory.load_memory_variables({})
    full_history = str(history_vars.get("history", ""))
    
    evaluation = await evaluation_service.evaluate_interview(full_history, model_name=selected_tier)
    
    print("\n=== [FINAL EVALUATION REPORT] ===")
    print(f"1. 기술 역량: {evaluation.technical_skill.score}점 - {evaluation.technical_skill.justification}")
    print(f"2. 소통 역량: {evaluation.communication.score}점 - {evaluation.communication.justification}")
    print(f"3. 문제 해결: {evaluation.problem_solving.score}점 - {evaluation.problem_solving.justification}")
    print(f"\n[총평]\n{evaluation.overall_feedback}")
    
    # 5. 세션 정리
    await interview_engine.clear_session(session_id)
    print("\n[INFO] Redis 세션이 정리되었습니다.")

if __name__ == "__main__":
    try:
        asyncio.run(run_interview_loop())
    except KeyboardInterrupt:
        print("\n시뮬레이션을 종료합니다.")
