import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import logger, BASE_DIR, UPLOADS_DIR, DATA_DIR, STATIC_DIR
from .routers import auth, user, job, interview, admin, video_router

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 포함
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(job.router)
app.include_router(interview.router)
app.include_router(admin.router)
app.include_router(video_router.router)

# ---------------------------------------------------------
# Static Files (절대경로로 마운트)
#   - 저장되는 uploads 경로와
#   - /uploads로 서빙되는 경로가
#     항상 동일하게 유지되도록 함
# ---------------------------------------------------------
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

logger.info(f"Application initialized. BASE_DIR={BASE_DIR}")
logger.info(f"Static mounts: /uploads -> {UPLOADS_DIR}, /data -> {DATA_DIR}, / -> {STATIC_DIR}")