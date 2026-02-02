from __future__ import annotations

from fastapi import FastAPI

from IMH.routers import auth, candidate_profiles, health, interviews


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리.

    Returns:
        FastAPI: 라우터가 등록된 애플리케이션 인스턴스.
    """
    app = FastAPI(title="AI Interview API")

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(candidate_profiles.router, prefix="/candidate-profiles", tags=["candidate_profiles"])
    app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
    return app


app: FastAPI = create_app()