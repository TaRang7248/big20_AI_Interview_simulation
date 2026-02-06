from __future__ import annotations

from fastapi import FastAPI

from IMH.IMH_no_api.IMH_no_api.core.error_handler import imh_exception_handler
from IMH.IMH_no_api.IMH_no_api.core.exceptions import IMHError
from IMH.IMH_no_api.IMH_no_api.core.logging_config import setup_logging
from IMH.IMH_no_api.IMH_no_api.core.request_id import RequestIdMiddleware
from IMH.IMH_no_api.IMH_no_api.routers import auth, candidate_profiles, health, interviews


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리.

    Returns:
        FastAPI: 라우터가 등록된 애플리케이션 인스턴스.
    """
    # 로깅 초기화
    setup_logging()

    f_app = FastAPI(title="AI Interview API")

    # 예외 핸들러 등록
    f_app.add_exception_handler(IMHError, imh_exception_handler)

    # 미들웨어 추가
    f_app.add_middleware(RequestIdMiddleware)

    f_app.include_router(health.router)
    f_app.include_router(auth.router, prefix="/auth", tags=["auth"])
    f_app.include_router(candidate_profiles.router, prefix="/candidate-profiles", tags=["candidate_profiles"])
    f_app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
    return f_app


app: FastAPI = create_app()