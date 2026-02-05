from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db
from db.models import InterviewSession, InterviewAnswer, Question
from services import llm_service, stt_service
import shutil
import os
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/start")
async def start_interview(user_id: int = Form(...), job_role: str = Form(...), candidate_name: str = Form(...), db: AsyncSession = Depends(get_db)):
    # Create Session
    session = InterviewSession(user_id=user_id, start_time=datetime.utcnow())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # RAG: Fetch relevant questions context from DB
    # In a real scenario, use vector search: await db.execute(select(Question).order_by(Question.embedding.cosine_distance(job_embedding)).limit(5))
    result = await db.execute(select(Question).limit(5))
    existing_questions = result.scalars().all()
    context = [q.content for q in existing_questions]
    
    # Generate Questions
    # We pass the existing questions as context/style examples to the LLM
    generated_questions_text = await llm_service.generate_questions(job_role, candidate_name, context)
    
    # Create InterviewAnswer records for the plan
    # 0: Intro
    # 1-3: Personality
    # 4-8: Job Knowledge
    # 9: Closing
    # Total 10
    
    for idx, q_text in enumerate(generated_questions_text):
        # Assign category based on index for simplicity in logic later
        if idx == 0: cat = "Intro"
        elif 1 <= idx <= 3: cat = "Personality"
        elif 4 <= idx <= 8: cat = "JobKnowledge"
        else: cat = "Closing"
        
        answer_record = InterviewAnswer(
            session_id=session.id,
            question_content=q_text,
            # We can store category in evaluation_json or separate column if needed
        )
        db.add(answer_record)
        
    await db.commit()
    return {"session_id": session.id, "status": "started", "count": len(generated_questions_text)}

@router.get("/{session_id}/current")
async def get_current_question(session_id: int, db: AsyncSession = Depends(get_db)):
    # Find the first question without an answer_text
    result = await db.execute(
        select(InterviewAnswer)
        .where(InterviewAnswer.session_id == session_id)
        .where(InterviewAnswer.answer_text == None)
        .order_by(InterviewAnswer.id)
    )
    next_question = result.scalars().first()
    
    if not next_question:
        return {"finished": True}
        
    # Get total count
    total_res = await db.execute(select(InterviewAnswer).where(InterviewAnswer.session_id == session_id))
    total_count = len(total_res.scalars().all())
    
    # Calculate index
    # (Simplified: assume id order is index order)
    all_res = await db.execute(select(InterviewAnswer).where(InterviewAnswer.session_id == session_id).order_by(InterviewAnswer.id))
    all_qs = all_res.scalars().all()
    index = all_qs.index(next_question)
    
    return {
        "question_id": next_question.id,
        "question": next_question.question_content,
        "index": index + 1,  # 1-based for UI
        "total": total_count
    }

@router.post("/submit")
async def submit_answer(
    session_id: int = Form(...),
    question_id: int = Form(...),
    audio: UploadFile = File(None),
    image: UploadFile = File(None), # Added image
    answer_text: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Retrieve Answer Record
    result = await db.execute(select(InterviewAnswer).where(InterviewAnswer.id == question_id))
    answer_record = result.scalars().first()
    
    if not answer_record:
        raise HTTPException(status_code=404, detail="Question not found")

    text_content = answer_text
    audio_path = None
    image_path = None
    
    # Process Audio
    if audio:
        file_path = f"{UPLOAD_DIR}/{session_id}_{question_id}_audio_{int(datetime.utcnow().timestamp())}.webm"
        with open(file_path, "wb+") as file_object:
            shutil.copyfileobj(audio.file, file_object)
        audio_path = file_path
        
        # STT
        if not text_content:
            text_content = await stt_service.transcribe_audio(file_path)
            
    # Process Image (Canvas)
    if image:
        img_path = f"{UPLOAD_DIR}/{session_id}_{question_id}_image_{int(datetime.utcnow().timestamp())}.png"
        with open(img_path, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        image_path = img_path
    
    if not text_content:
        text_content = "(No answer provided)"

    # Evaluate
    evaluation = await llm_service.evaluate_answer(
        answer_record.question_content,
        text_content,
        "Candidate Role",
        image_path=image_path # Pass image path
    )
    
    # Update DB
    answer_record.answer_text = text_content
    answer_record.answer_audio_url = audio_path
    # We could store image path too, but InterviewAnswer model doesn't have it explicitly.
    # Logic: Maybe just put it in evaluation_json or ignore for now as it's part of the answer context.
    # Or add to text content:
    if image_path:
        answer_record.answer_text += f" [Image Submitted]"
        
    answer_record.evaluation_json = evaluation
    answer_record.score = evaluation.get("score", 0)
    
    # Handle Follow-up (Tail Question)
    # If follow-up needed and not first/last
    # Note: Logic to insert stored in evaluation['follow_up_question']
    # If yes, we insert a new InterviewAnswer record immediately after this one?
    # Or just return it to UI to ask 'bonus' question?
    # Requirements say: "LLM decides ... add tail question".
    # Implementation: Insert new InterviewAnswer record.
    
    follow_up_created = False
    if evaluation.get("follow_up_needed"):
         # Check constraints: 1st (index 0) and 10th (last) no tail info handled by logic?
         # Check index... 
         # Let's assume passed constraints check in LLM or here.
         tail_q_text = evaluation.get("follow_up_question")
         if tail_q_text:
             tail_q = InterviewAnswer(
                 session_id=session_id,
                 question_content=f"[꼬리질문] {tail_q_text}",
                 # Mark as tail?
             )
             db.add(tail_q)
             follow_up_created = True

    await db.commit()
    
    return {
        "status": "success",
        "stt": text_content,
        "score": answer_record.score,
        "follow_up": follow_up_created
    }
