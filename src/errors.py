from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not-found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate-limit"
    EXTERNAL_SERVICE = "external-service"
    INTERNAL = "internal"


class ErrorCode(str, Enum):
    VALIDATION_FAILED = "validation-failed"
    MISSING_REQUIRED_FIELD = "missing-required-field"
    INVALID_FORMAT = "invalid-format"
    INVALID_DATE_FORMAT = "invalid-date-format"
    INVALID_RANGE = "invalid-range"

    INVALID_CREDENTIALS = "invalid-credentials"
    TOKEN_EXPIRED = "token-expired"  # nosec B105 - error code, not password
    NOT_AUTHENTICATED = "not-authenticated"

    INSUFFICIENT_PERMISSIONS = "insufficient-permissions"
    RESOURCE_FORBIDDEN = "resource-forbidden"

    USER_NOT_FOUND = "user-not-found"
    RESOURCE_NOT_FOUND = "resource-not-found"
    CREDENTIALS_NOT_FOUND = "credentials-not-found"

    DUPLICATE_ENTRY = "duplicate-entry"

    RATE_LIMIT_EXCEEDED = "rate-limit-exceeded"

    EXTERNAL_API_ERROR = "external-api-error"
    SYNC_FAILED = "sync-failed"
    SERVICE_UNAVAILABLE = "service-unavailable"

    DATABASE_ERROR = "database-error"
    INTERNAL_ERROR = "internal-error"


@dataclass
class APIError(Exception):
    code: ErrorCode
    category: ErrorCategory
    status: int
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__init__(self.detail or self.code.value)

    @property
    def title(self) -> str:
        return self.code.value.replace("-", " ").title()

    def to_problem_detail(self, instance: str | None = None) -> dict[str, Any]:
        problem = {
            "type": f"https://api.life-as-code/problems/{self.code.value}",
            "title": self.title,
            "status": self.status,
            "code": self.code.value,
            "category": self.category.value,
        }
        if self.detail:
            problem["detail"] = self.detail
        if instance:
            problem["instance"] = instance
        if self.extra:
            problem.update(self.extra)
        return problem


class ValidationError(APIError):
    def __init__(self, detail: str, **extra: Any):
        super().__init__(
            code=ErrorCode.VALIDATION_FAILED,
            category=ErrorCategory.VALIDATION,
            status=400,
            detail=detail,
            extra=extra,
        )


class InvalidDateFormatError(APIError):
    def __init__(self, provided_value: str):
        super().__init__(
            code=ErrorCode.INVALID_DATE_FORMAT,
            category=ErrorCategory.VALIDATION,
            status=400,
            detail=f"Invalid date format: '{provided_value}'. Expected YYYY-MM-DD",
            extra={"provided_value": provided_value},
        )


class InvalidCredentialsError(APIError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.INVALID_CREDENTIALS,
            category=ErrorCategory.AUTHENTICATION,
            status=401,
            detail="Invalid username or password",
        )
