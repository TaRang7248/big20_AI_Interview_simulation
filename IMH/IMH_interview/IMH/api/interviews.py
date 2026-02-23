"""
Interviews API - 면접 세션 관리 라우터 (TASK-UI)

Endpoints:
- GET  /api/v1/interviews                       - user's interview history
- POST /api/v1/interviews                       - create interview session
- GET  /api/v1/interviews/{interview_id}        - get session state
- POST /api/v1/interviews/{interview_id}/chat   - submit answer turn
- GET  /api/v1/interviews/{interview_id}/chat   - get chat history
- GET  /api/v1/interviews/{interview_id}/result - get evaluation result
"""

import re
import random
import logging
from datetime import datetime
from typing import Optional

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from IMH.api.auth import require_user

logger = logging.getLogger("imh.interviews")
router = APIRouter(prefix="/interviews", tags=["Interviews"])

INTERVIEW_PHASES = ["자기소개", "지원동기", "직무역량", "경험/사례", "문제해결", "마무리"]

PHASE_QUESTIONS = {
    "자기소개": ["자기소개를 해주세요.", "간단하게 본인에 대해 소개해 주세요."],
    "지원동기": ["저희 회사에 지원하게 된 동기를 말씀해 주세요.", "이 직무에 관심을 갖게 된 계기가 무엇인가요?"],
    "직무역량": ["본인의 가장 큰 강점은 무엇인가요?", "이 직무와 관련된 경험이나 역량을 설명해 주세요."],
    "경험/사례": ["팀에서 어려운 상황을 겪었던 경험과 어떻게 해결했는지 말씀해 주세요.", "프로젝트에서 주도적으로 역할을 한 경험이 있으면 소개해 주세요."],
    "문제해결": ["예상치 못한 문제에 직면했을 때 어떻게 대처하시나요?", "업무 중 갈등이 발생했을 때 어떻게 해결하셨나요?"],
    "마무리": ["마지막으로 하고 싶은 말씀이 있으신가요?", "입사 후 어떤 목표를 갖고 계신가요?"],
}


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


def _get_next_question(phase: str) -> str:
    questions = PHASE_QUESTIONS.get(phase, ["다음 질문입니다. 답변해 주세요."])
    return random.choice(questions)


# --- Schemas ---

class CreateInterviewRequest(BaseModel):
    job_id: str


class ChatMessageRequest(BaseModel):
    content: str


# --- Routes ---

@router.get("")
async def list_interviews(user_id: str = Depends(require_user)):
    """Get current user's interview history."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        rows = await conn.fetch(
            """
            SELECT i.session_id, i.job_id, i.status, i.created_at, i.completed_at,
                   j.title as job_title,
                   ie.decision, ie.summary, ie.tech_score, ie.problem_score, ie.comm_score, ie.nonverbal_score
            FROM interviews i
            LEFT JOIN jobs j ON j.job_id = i.job_id
            LEFT JOIN interview_evaluations ie ON ie.session_id = i.session_id
            WHERE i.user_id=$1
            ORDER BY i.created_at DESC
            """,
            user_id
        )
        return [
            {
                "session_id": r["session_id"],
                "job_id": r["job_id"],
                "job_title": r["job_title"],
                "status": r["status"],
                "decision": r["decision"],
                "summary": r["summary"],
                "tech_score": r["tech_score"],
                "problem_score": r["problem_score"],
                "comm_score": r["comm_score"],
                "nonverbal_score": r["nonverbal_score"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    finally:
        await conn.close()


@router.post("", status_code=201)
async def create_interview(
    req: CreateInterviewRequest,
    user_id: str = Depends(require_user),
):
    """Create a new interview session for a job."""
    import uuid
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        job = await conn.fetchrow("SELECT job_id, status FROM jobs WHERE job_id=$1", req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "PUBLISHED":
            raise HTTPException(status_code=400, detail="Job is not currently accepting applications")

        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        await conn.execute(
            """
            INSERT INTO interviews
                (session_id, user_id, job_id, status, mode, created_at, updated_at, applied_at, started_at)
            VALUES ($1,$2,$3,'IN_PROGRESS'::session_status,'ACTUAL'::interview_mode,$4,$4,$4,$4)
            """,
            session_id, user_id, req.job_id, now
        )

        first_phase = INTERVIEW_PHASES[0]
        greeting = f"안녕하세요. 면접을 시작하겠습니다. [{first_phase}] 단계입니다.\n{_get_next_question(first_phase)}"
        await conn.execute(
            "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'ai',$2,$3,$4)",
            session_id, greeting, first_phase, now
        )

        return {"session_id": session_id, "message": "Interview started"}
    finally:
        await conn.close()


@router.get("/{interview_id}")
async def get_interview(
    interview_id: str,
    user_id: str = Depends(require_user),
):
    """Get interview session state."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            """
            SELECT i.session_id, i.job_id, i.status, i.created_at, i.started_at, i.completed_at,
                   j.title as job_title
            FROM interviews i
            LEFT JOIN jobs j ON j.job_id = i.job_id
            WHERE i.session_id=$1
            """,
            interview_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Interview not found")

        turns = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_history WHERE session_id=$1 AND role='user'",
            interview_id
        )
        phase_idx = min(int(turns), len(INTERVIEW_PHASES) - 1)
        current_phase = INTERVIEW_PHASES[phase_idx]

        return {
            "session_id": row["session_id"],
            "job_id": row["job_id"],
            "job_title": row["job_title"],
            "status": row["status"],
            "current_phase": current_phase,
            "phase_index": phase_idx,
            "total_phases": len(INTERVIEW_PHASES),
            "turn_count": turns,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        }
    finally:
        await conn.close()


@router.get("/{interview_id}/chat")
async def get_chat_history(
    interview_id: str,
    user_id: str = Depends(require_user),
):
    """Get full chat history for interview."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        rows = await conn.fetch(
            "SELECT role, content, phase, created_at FROM chat_history WHERE session_id=$1 ORDER BY created_at",
            interview_id
        )
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "phase": r["phase"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    finally:
        await conn.close()


@router.post("/{interview_id}/chat")
async def submit_chat(
    interview_id: str,
    req: ChatMessageRequest,
    user_id: str = Depends(require_user),
):
    """Submit an answer turn. Returns AI's next question or completion."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT status, user_id FROM interviews WHERE session_id=$1",
            interview_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Interview not found")
        if row["status"] not in ("IN_PROGRESS", "APPLIED"):
            raise HTTPException(status_code=400, detail="Interview is not in progress")

        now = datetime.now()

        turns = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_history WHERE session_id=$1 AND role='user'",
            interview_id
        )
        phase_idx = min(int(turns), len(INTERVIEW_PHASES) - 1)
        current_phase = INTERVIEW_PHASES[phase_idx]

        await conn.execute(
            "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'user',$2,$3,$4)",
            interview_id, req.content, current_phase, now
        )

        new_turns = turns + 1

        if new_turns >= len(INTERVIEW_PHASES):
            await conn.execute(
                "UPDATE interviews SET status='COMPLETED'::session_status, completed_at=$1, updated_at=$1 WHERE session_id=$2",
                now, interview_id
            )

            tech = round(random.uniform(60, 95), 1)
            prob = round(random.uniform(60, 95), 1)
            comm = round(random.uniform(60, 95), 1)
            nonv = round(random.uniform(60, 95), 1)
            avg = (tech + prob + comm + nonv) / 4
            decision = "PASS" if avg >= 70 else "FAIL"
            summary = (
                f"기술 역량({tech}점)과 문제해결 능력({prob}점)이 " +
                ("우수합니다." if avg >= 75 else "개선이 필요합니다.")
            )

            await conn.execute(
                """
                INSERT INTO interview_evaluations
                    (session_id, decision, summary, tech_score, problem_score, comm_score, nonverbal_score)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                interview_id, decision, summary, tech, prob, comm, nonv
            )

            await conn.execute(
                "UPDATE interviews SET status='EVALUATED'::session_status, evaluated_at=$1, updated_at=$1 WHERE session_id=$2",
                now, interview_id
            )

            farewell = "면접이 종료되었습니다. 수고하셨습니다. 결과는 추후 안내드리겠습니다."
            await conn.execute(
                "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'ai',$2,'마무리',$3)",
                interview_id, farewell, now
            )

            return {
                "status": "COMPLETED",
                "ai_message": farewell,
                "current_phase": "마무리",
                "is_done": True,
            }
        else:
            next_phase_idx = min(int(new_turns), len(INTERVIEW_PHASES) - 1)
            next_phase = INTERVIEW_PHASES[next_phase_idx]
            if next_phase_idx > phase_idx:
                ai_msg = f"[{next_phase}] 단계로 넘어가겠습니다.\n{_get_next_question(next_phase)}"
            else:
                ai_msg = _get_next_question(next_phase)

            await conn.execute(
                "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'ai',$2,$3,$4)",
                interview_id, ai_msg, next_phase, now
            )

            return {
                "status": "IN_PROGRESS",
                "ai_message": ai_msg,
                "current_phase": next_phase,
                "is_done": False,
                "turn": new_turns,
            }
    finally:
        await conn.close()


@router.get("/{interview_id}/result")
async def get_result(
    interview_id: str,
    user_id: str = Depends(require_user),
):
    """Get interview evaluation result."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            """
            SELECT ie.decision, ie.summary, ie.tech_score, ie.problem_score, ie.comm_score, ie.nonverbal_score,
                   i.status, j.title as job_title
            FROM interview_evaluations ie
            JOIN interviews i ON i.session_id = ie.session_id
            LEFT JOIN jobs j ON j.job_id = i.job_id
            WHERE ie.session_id=$1
            """,
            interview_id
        )
        if not row:
            intvw = await conn.fetchrow(
                "SELECT status FROM interviews WHERE session_id=$1", interview_id
            )
            if not intvw:
                raise HTTPException(status_code=404, detail="Interview not found")
            return {"status": intvw["status"], "evaluation": None}

        return {
            "status": row["status"],
            "job_title": row["job_title"],
            "evaluation": {
                "decision": row["decision"],
                "summary": row["summary"],
                "scores": {
                    "tech": row["tech_score"],
                    "problem": row["problem_score"],
                    "comm": row["comm_score"],
                    "nonverbal": row["nonverbal_score"],
                }
            }
        }
    finally:
        await conn.close()
