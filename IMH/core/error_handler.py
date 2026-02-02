from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from IMH.common.time import utc_now
from IMH.core.exceptions import IMHError
from IMH.core.request_id import get_request_id

logger = logging.getLogger("IMH.error_handler")


async def imh_exception_handler(request: Request, exc: IMHError) -> JSONResponse:
    """IMHError를 처리하여 표준화된 에러 응답을 반환함."""
    
    # 5xx 에러는 로그에 예외 정보를 포함함
    if exc.status_code >= 500:
        logger.exception(f"Unhandled IMHError: {exc.message}", exc_info=exc)
    else:
        logger.warning(f"IMHError ({exc.code}): {exc.message}")

    content = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
        },
        "request_id": get_request_id(),
        "timestamp": utc_now().isoformat(),
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )
