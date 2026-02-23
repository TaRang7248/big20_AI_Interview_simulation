"""
Resume API - 이력서 업로드/조회 라우터 (TASK-UI)

Endpoints:
- POST /api/v1/resume/upload - upload resume file
- GET  /api/v1/resume        - get current user's resume info
"""

import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from IMH.api.auth import require_user

logger = logging.getLogger("imh.resume")
router = APIRouter(prefix="/resume", tags=["Resume"])

RESUME_DIR = Path(r"c:\big20\big20_AI_Interview_simulation\IMH\IMH_interview\data\resumes")
RESUME_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(require_user),
):
    """Upload resume file. Supported: PDF, DOC, DOCX, TXT."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = RESUME_DIR / unique_name
    content = await file.read()
    file_path.write_bytes(content)

    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        await conn.execute(
            """
            INSERT INTO resumes (user_id, file_name, file_path, file_size, uploaded_at)
            VALUES ($1,$2,$3,$4,$5)
            """,
            user_id, file.filename, str(file_path), len(content), datetime.now()
        )
    finally:
        await conn.close()

    return {
        "message": "Resume uploaded successfully",
        "file_name": file.filename,
        "file_size": len(content),
    }


@router.get("")
async def get_resume(user_id: str = Depends(require_user)):
    """Get current user's latest resume info."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT resume_id, file_name, file_path, file_size, uploaded_at FROM resumes WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT 1",
            user_id
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No resume found")

    data = dict(row)
    if data.get("uploaded_at"):
        data["uploaded_at"] = data["uploaded_at"].isoformat()
    return data
