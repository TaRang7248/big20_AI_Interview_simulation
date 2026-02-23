from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .config import logger, UPLOAD_FOLDER, AUDIO_FOLDER, TTS_FOLDER
from .routers import auth, user, job, interview, admin, video_router

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(job.router)
app.include_router(interview.router)
app.include_router(admin.router)
app.include_router(video_router.router)

# Static Files
# Mount 'uploads' to serve uploaded files (resumes, audio, images)
# The directory setup is relative to where uvicorn is run (server.py root)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mount 'data' to serve static assets like interviewer face image
app.mount("/data", StaticFiles(directory="data"), name="data")

# Mount root static files (index.html, styles.css, app.js)
# We serve index.html as the default for root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

logger.info("Application initialized with routers and static files.")
