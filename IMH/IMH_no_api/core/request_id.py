from __future__ import annotations

import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# 전역적으로 request_id를 추적하기 위한 ContextVar
_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """현재 컨텍스트의 request_id를 반환함."""
    return _request_id_ctx_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """요청마다 고유한 request_id를 부여하고 컨텍스트에 저장하는 미들웨어."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 헤더에 X-Request-ID가 있으면 사용, 없으면 새로 생성
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # ContextVar에 설정 (해당 요청의 비동기 태스크 내에서 유효)
        token = _request_id_ctx_var.set(request_id)
        
        try:
            response = await call_next(request)
            # 응답 헤더에도 request_id 추가 (추적 용이성)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 컨텍스트 복구
            _request_id_ctx_var.reset(token)
