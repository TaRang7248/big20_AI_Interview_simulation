from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db
from db.models import User
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/login")
async def login(username: str = Form(...), job_role: str = Form(...), db: AsyncSession = Depends(get_db)):
    """
    Login or Register a user.
    Returns user_id.
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if not user:
        # Register new user
        user = User(username=username, job_role=job_role)
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating user: {e}")
            raise HTTPException(status_code=500, detail="Registration failed")
    
    # Update job role if changed? Optional.
    # For now just return user info
    return {"user_id": user.id, "username": user.username, "job_role": user.job_role}
