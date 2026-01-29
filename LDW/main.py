from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from . import models, database, llm_service
from .database import engine, get_db

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Text Interview Pipeline - LDW")

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Routes
@app.get("/")
async def read_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/interview/question")
def get_question(last_answer: str = None):
    """
    Get a new question. If last_answer is provided, it generates a follow-up.
    """
    try:
        # Note: In a real-world app, we should use a session ID to keep memory separate per user.
        # For this standalone slice, we use the singleton memory in llm_service.
        question = llm_service.get_interview_question(last_answer=last_answer)
        return {"question": question}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interview/answer")
def post_answer(data: dict, db: Session = Depends(get_db)):
    question = data.get("question")
    answer = data.get("answer")
    
    if not question or not answer:
        raise HTTPException(status_code=400, detail="Missing question or answer")
    
    try:
        # LLM Evaluation
        evaluation = llm_service.evaluate_answer(question, answer)
        
        # Save to DB
        db_result = models.InterviewResult(
            question=question,
            answer=answer,
            evaluation=evaluation
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        
        # We return the evaluation and optionally prompt for a follow-up in the frontend
        return {
            "id": db_result.id,
            "evaluation": evaluation
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files AFTER routes to avoid conflict with /
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
