from typing import Any


class BaseException(Exception):
    """Базовий клас для всіх кастомних винятків застосунку."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        payload: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.payload = payload
        super().__init__(message)


class NotFoundError(BaseException):
    """Resource not found (404)."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(message=detail, status_code=404)


class BadRequestError(BaseException):
    """Invalid request (400)."""

    def __init__(self, detail: str = "Bad request"):
        super().__init__(message=detail, status_code=400)


class ValidationError(BaseException):
    """Data validation error (422)."""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(message=detail, status_code=422)


class ServiceUnavailableError(BaseException):
    """External service unavailable or broker error (503)."""

    def __init__(self, detail: str = "Service unavailable"):
        super().__init__(message=detail, status_code=503)


class AuthError(BaseException):
    """Authorization error (401/403)."""

    def __init__(self, detail: str = "Authentication failed", status_code: int = 401):
        super().__init__(message=detail, status_code=status_code)
