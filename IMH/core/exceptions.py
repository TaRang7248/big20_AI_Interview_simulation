from __future__ import annotations

from typing import Any


class IMHError(Exception):
    """IMH 모듈의 베이스 예외 클래스."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(IMHError):
    """인증 실패 예외."""

    def __init__(self, message: str = "Invalid credentials", detail: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="AUTH_INVALID_CREDENTIALS",
            status_code=401,
            detail=detail,
        )


class PermissionDeniedError(IMHError):
    """권한 부족 예외."""

    def __init__(self, message: str = "Permission denied", detail: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403,
            detail=detail,
        )


class NotFoundError(IMHError):
    """리소스를 찾을 수 없음 예외."""

    def __init__(self, message: str = "Resource not found", detail: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            detail=detail,
        )


class ConflictError(IMHError):
    """데이터 충돌 예외."""

    def __init__(self, message: str = "Conflict occurred", detail: Any | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            detail=detail,
        )
