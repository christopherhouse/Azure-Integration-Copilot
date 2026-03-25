class AppError(Exception):
    """Base application error with structured error information."""

    def __init__(
        self,
        status_code: int = 500,
        code: str = "INTERNAL_ERROR",
        message: str = "An internal error occurred.",
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    """Resource not found (404)."""

    def __init__(self, message: str = "The requested resource was not found.", detail: dict | None = None) -> None:
        super().__init__(status_code=404, code="RESOURCE_NOT_FOUND", message=message, detail=detail)


class QuotaExceededError(AppError):
    """Quota exceeded (429)."""

    def __init__(self, message: str = "Quota has been exceeded.", detail: dict | None = None) -> None:
        super().__init__(status_code=429, code="QUOTA_EXCEEDED", message=message, detail=detail)


class ValidationError(AppError):
    """Validation error (422)."""

    def __init__(self, message: str = "Validation failed.", detail: dict | None = None) -> None:
        super().__init__(status_code=422, code="VALIDATION_ERROR", message=message, detail=detail)


class ForbiddenError(AppError):
    """Forbidden access (403)."""

    def __init__(self, message: str = "Access to this resource is forbidden.", detail: dict | None = None) -> None:
        super().__init__(status_code=403, code="FORBIDDEN", message=message, detail=detail)


class UnauthorizedError(AppError):
    """Unauthorized access (401)."""

    def __init__(self, message: str = "Authentication is required.", detail: dict | None = None) -> None:
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message, detail=detail)
