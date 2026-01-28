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
def get_question(type: str = "llm"):
    """
    Get a question. 
    - if type=json, it will try to load from LDW/data/interview_lsj.json
    - if type=llm, it uses OpenAI
    """
    try:
        data_file = os.path.join(os.path.dirname(__file__), "data", "interview_lsj.json")
        use_json = (type == "json")
        
        question = llm_service.get_interview_question(use_json=use_json, file_path=data_file)
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
        
        return {
            "id": db_result.id,
            "evaluation": evaluation
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files AFTER routes to avoid conflict with /
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
