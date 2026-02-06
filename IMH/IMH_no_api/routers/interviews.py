from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.IMH_no_api.IMH_no_api.core.deps import get_current_user
from IMH.IMH_no_api.IMH_no_api.core.exceptions import NotFoundError, PermissionDeniedError
from IMH.IMH_no_api.IMH_no_api.db.session import get_db
from IMH.IMH_no_api.IMH_no_api.models.candidate_profile import CandidateProfile
from IMH.IMH_no_api.IMH_no_api.models.event_log import EventLog, EventType
from IMH.IMH_no_api.IMH_no_api.models.interview import Interview
from IMH.IMH_no_api.IMH_no_api.models.user import User, UserRole
from IMH.IMH_no_api.IMH_no_api.schemas.interview import InterviewCreateIn, InterviewOut, InterviewQuestionOut
from IMH.IMH_no_api.IMH_no_api.services.interview_engine import interview_engine
from IMH.IMH_no_api.IMH_no_api.services.persona_service import persona_service
from IMH.IMH_no_api.IMH_no_api.services.evaluation_service import evaluation_service
from IMH.IMH_no_api.IMH_no_api.schemas.rubric import EvaluationRubric
from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory

router: APIRouter = APIRouter()
logger = logging.getLogger("IMH.IMH_no_api.IMH_no_api.interviews")


@router.post("", response_model=InterviewOut)
async def create_interview(
    payload: InterviewCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewOut:
    """면접 세션 생성(프로필 연결).

    정책:
      - candidate: 본인 profile로만 생성 가능
      - admin: 모든 profile 가능

    Args:
        payload: profile_id 포함.
        user: 인증된 사용자.
        db: DB 세션.

    Returns:
        InterviewOut: 생성된 면접.

    Raises:
        HTTPException: 프로필 없음(404), 권한 없음(403).
    """
    profile: CandidateProfile | None = await db.get(CandidateProfile, payload.profile_id)
    if profile is None:
        raise NotFoundError(message="Profile not found")

    if user.role == UserRole.candidate and profile.user_id != user.id:
        raise PermissionDeniedError(message="Cannot create interview for other user's profile")

    interview = Interview(profile_id=profile.id, persona=payload.persona)
    db.add(interview)
    await db.flush()  # interview.id 확보

    db.add(
        EventLog(
            interview_id=interview.id,
            type=EventType.status_change,
            payload={"from": None, "to": "created"},
        )
    )

    await db.commit()
    await db.refresh(interview)
    logger.info(f"Interview created: {interview.id} for user: {user.id} (profile: {profile.id})")
    return interview


@router.post("/{interview_id}/start", response_model=InterviewQuestionOut)
async def start_interview(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewQuestionOut:
    """면접 시작 및 첫 질문 생성."""
    interview: Interview | None = await db.get(Interview, interview_id)
    if not interview:
        raise NotFoundError("Interview not found")
    
    profile: CandidateProfile = await db.get(CandidateProfile, interview.profile_id)
    
    # 1. Tavily 초기 기업 조사
    research_context = await interview_engine.get_initial_research(
        profile.target_company, profile.target_job
    )
    
    # 2. 시스템 프롬프트 생성 (연구 결과 포함)
    system_prompt = persona_service.get_system_prompt(
        persona=interview.persona,
        target_company=profile.target_company,
        target_job=profile.target_job,
        resume_summary=profile.resume_text[:500],  # 요약본 (가정)
        skills=profile.skills
    )
    
    # 3. 메모리 설정 (Redis 연동)
    message_history = RedisChatMessageHistory(
        url=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        session_id=f"interview_{interview_id}"
    )
    memory = ConversationSummaryBufferMemory(
        llm=ollama_service.get_llm(),
        chat_memory=message_history,
        max_token_limit=1000,
        return_messages=True
    )
    
    # 4. 첫 질문 생성
    # 첫 질문이므로 사용자 입력은 "면접을 시작하겠습니다."로 가정
    question_out = await interview_engine.generate_question(
        session_id=str(interview_id),
        user_input=f"안녕하세요. {profile.target_company}의 {profile.target_job} 직원에 지원한 면접자입니다. 면접을 시작하겠습니다. 다음은 참고할 기업 뉴스 정보입니다: {research_context}",
        system_prompt=system_prompt,
        memory=memory
    )
    
    # 상태 변경
    interview.status = "live"
    interview.started_at = utc_now()
    await db.commit()
    
    return question_out


@router.post("/{interview_id}/answer", response_model=InterviewQuestionOut)
async def submit_answer(
    interview_id: int,
    answer: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewQuestionOut:
    """사용자 답변 제출 및 다음 '꼬리 질문' 생성."""
    interview: Interview | None = await db.get(Interview, interview_id)
    if not interview or interview.status != "live":
        raise NotFoundError("Live interview session not found")
    
    profile: CandidateProfile = await db.get(CandidateProfile, interview.profile_id)
    
    # 1. 시스템 프롬프트 재구성
    system_prompt = persona_service.get_system_prompt(
        persona=interview.persona,
        target_company=profile.target_company,
        target_job=profile.target_job,
        resume_summary=profile.resume_text[:500],
        skills=profile.skills
    )
    
    # 2. 메모리 로드 (Redis)
    message_history = RedisChatMessageHistory(
        url=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        session_id=f"interview_{interview_id}"
    )
    memory = ConversationSummaryBufferMemory(
        llm=ollama_service.get_llm(),
        chat_memory=message_history,
        max_token_limit=1000,
        return_messages=True
    )
    
    # 3. 답변을 기반으로 다음 질문 생성
    question_out = await interview_engine.generate_question(
        session_id=str(interview_id),
        user_input=answer,
        system_prompt=system_prompt,
        memory=memory
    )
    
    return question_out


@router.post("/{interview_id}/evaluate", response_model=EvaluationRubric)
async def evaluate_interview(
    interview_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationRubric:
    """면접 종료 및 최종 평가 수행."""
    interview: Interview | None = await db.get(Interview, interview_id)
    if not interview:
        raise NotFoundError("Interview not found")
    
    from IMH.IMH_no_api.IMH_no_api.core.exceptions import IMHError
    from IMH.IMH_no_api.IMH_no_api.common.time import utc_now

    # 메모리에서 대화 이력 가져오기
    message_history = RedisChatMessageHistory(
        url=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        session_id=f"interview_{interview_id}"
    )
    
    # 메시지를 텍스트 형태로 병합
    history_text = ""
    for idx, msg in enumerate(message_history.messages):
        role = "지원자" if msg.type == "human" else "면접관"
        history_text += f"Turn {idx//2 + 1} - {role}: {msg.content}\n"
    
    if not history_text:
        raise IMHError("대화 이력이 없어 평가를 진행할 수 없습니다.")

    # 평가 수행
    evaluation = await evaluation_service.evaluate_interview(history_text)
    
    # 상태 업데이트
    interview.status = "finished"
    interview.finished_at = utc_now()
    await db.commit()
    
    return evaluation
