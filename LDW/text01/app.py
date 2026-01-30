from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
import database
import models
import llm_service
from pydantic import BaseModel
import webbrowser
import threading
import time
import uvicorn

app = FastAPI()

# Ensure tables exist
models.Base.metadata.create_all(bind=database.engine)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class StartSessionRequest(BaseModel):
    user_name: str

class QuestionRequest(BaseModel):
    session_id: int

class AnswerRequest(BaseModel):
    session_id: int
    question: str
    answer: str
    is_followup: bool = False

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/start_session")
async def start_session(req: StartSessionRequest, db: Session = Depends(database.get_db)):
    session = models.InterviewSession(user_name=req.user_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "message": "Session started"}

@app.post("/api/get_question")
async def get_question(req: QuestionRequest, db: Session = Depends(database.get_db)):
    # Get a random question from DB
    question_db = db.query(models.Question).order_by(func.random()).first()
    if not question_db:
        # Fallback if DB is empty
        raise HTTPException(status_code=404, detail="No questions found in DB. Please run import_data.py first.")
    
    # Generate a proper interview question using LLM
    final_question = llm_service.generate_interview_question(question_db.question_text)
    
    return {"question": final_question, "original_id": question_db.id}

@app.post("/api/submit_answer")
async def submit_answer(req: AnswerRequest, db: Session = Depends(database.get_db)):
    # 1. Evaluate the answer
    eval_result = llm_service.evaluate_answer(req.question, req.answer)
    
    # 2. Check for follow-up condition
    # If LLM says it needs follow-up AND this hasn't been a follow-up chain yet (simple logic)
    if eval_result.get('needs_followup') and not req.is_followup:
        tail_question = llm_service.generate_tail_question(req.question, req.answer)
        
        # Save the interaction so far
        interaction = models.InterviewInteraction(
            session_id=req.session_id,
            bot_question=req.question,
            user_answer=req.answer,
            llm_evaluation=str(eval_result),
            interaction_type="initial_needs_followup"
        )
        db.add(interaction)
        db.commit()
        
        return {
            "status": "followup",
            "question": tail_question,
            "feedback": eval_result.get('feedback')
        }
    
    # 3. Finalize interaction
    interaction = models.InterviewInteraction(
        session_id=req.session_id,
        bot_question=req.question,
        user_answer=req.answer,
        llm_evaluation=str(eval_result),
        interaction_type="followup" if req.is_followup else "initial_completed"
    )
    db.add(interaction)
    db.commit()
    
    return {
        "status": "completed",
        "evaluation": eval_result
    }

def open_browser():
    """Wait a moment for the server to start, then open the browser."""
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # Start the browser opener in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run the server
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
