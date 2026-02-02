import json
import os
from database import engine, SessionLocal
from models import Base, Question

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

def import_questions():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "interview_lsj.json")
    print(f"Reading data from {json_path}")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {json_path}")
        return

    db = SessionLocal()
    
    # Check if data already exists to avoid duplicates
    count = db.query(Question).count()
    if count > 0:
        print(f"Database already has {count} questions. Skipping import.")
        db.close()
        return

    print(f"Importing {len(data)} questions...")
    for item in data:
        q_text = item.get("질문")
        a_text = item.get("답변")
        
        if q_text:
            question = Question(question_text=q_text, original_answer=a_text)
            db.add(question)
    
    db.commit()
    print("Import completed.")
    db.close()

if __name__ == "__main__":
    init_db()
    import_questions()
