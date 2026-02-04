import uvicorn
import webbrowser
import threading
import time
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from api.interview import router as interview_router
from db.postgres import init_db
from db.sqlite import init_sqlite

app = FastAPI(title="AI Interview Simulation")

# Initialize Databases
@app.on_event("startup")
def startup_event():
    print("🚀 Initializing databases...")
    try:
        init_db()
        print("✅ PostgreSQL (pgvector) initialized.")
    except Exception as e:
        print(f"❌ Postgres init error: {e}")
    
    try:
        init_sqlite()
        print("✅ SQLite (interview_save.db) initialized.")
    except Exception as e:
        print(f"❌ SQLite init error: {e}")

# Routes
app.include_router(interview_router, prefix="/api")

# Static files & Templates
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def open_browser():
    """Automatically opens matching URL in default browser after server starts."""
    time.sleep(2)  # Wait for uvicorn to bind
    print("🌐 Opening browser at http://127.0.0.1:8000...")
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # Start browser auto-open in a daemon thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=8000)
