from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from db.database import engine
from api import auth, interview, feedback

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could check DB connection here
    yield
    # Shutdown: close DB connection
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="AI Interview Simulation")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(interview.router, prefix="/api/interview", tags=["Interview"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])

from fastapi import Request
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/interview.html", response_class=HTMLResponse)
async def read_interview(request: Request):
    return templates.TemplateResponse("interview.html", {"request": request})

@app.get("/feedback.html", response_class=HTMLResponse)
async def read_feedback(request: Request):
    return templates.TemplateResponse("feedback.html", {"request": request})
