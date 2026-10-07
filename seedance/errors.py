"""Exceptions raised by the client.

Every exception carries what the API said: the HTTP status, and from the error
body {"error": {"type", "code", "param", "message"}} the type, the stable code
and the field at fault. A job that ends without a video raises JobFailedError,
whose ``retryable`` flag says whether submitting the same request again is safe.
"""
from __future__ import annotations

from typing import Any, Optional


class SeedanceError(Exception):
    """Base class for everything this package raises."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        type: Optional[str] = None,  # noqa: A002 - mirrors the API field name
        code: Optional[str] = None,
        param: Optional[str] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.type = type
        self.code = code
        self.param = param
        self.body = body


class RequestValidationError(SeedanceError, ValueError):
    """The request breaks a documented limit; caught locally, nothing was sent."""

    def __init__(self, problems: list) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class BadRequestError(SeedanceError):
    """400: malformed body (field_invalid, json_invalid) or a combination the model
    does not take (request_unsupported). Nothing is charged."""


class AuthenticationError(SeedanceError):
    """401: missing or invalid API key."""


class AccessDeniedError(SeedanceError):
    """402 or 403: insufficient balance, or the key's group may not use video models."""


class NotFoundError(SeedanceError):
    """404 video_request_not_found: unknown request_id, or a key of another user."""


class VideoNotReadyError(SeedanceError):
    """409 job_video_not_ready: the video was requested before the job was done."""


class RateLimitError(SeedanceError):
    """429: the account's concurrency or rate limit was reached."""


class ServiceUnavailableError(SeedanceError):
    """503: no capacity right now (no_capacity) or a temporary outage. Not charged."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class JobFailedError(SeedanceError):
    """The job ended as failed or expired (or its download answered 424).

    ``code`` is the stable failure code (invalid_input, content_policy_violation,
    copyright_violation, generation_failed, generation_timeout,
    capacity_unavailable, internal_error, cancelled); ``retryable`` is True when the
    same request can simply be submitted again; ``field`` names the input at fault.
    """

    def __init__(self, message: str, *, job: Any = None, retryable: Optional[bool] = None,
                 field: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.job = job
        self.retryable = retryable
        self.field = field


class JobTimeoutError(SeedanceError):
    """wait() gave up locally; the job itself may still finish. Keep its request_id."""

    def __init__(self, message: str, *, job: Any = None) -> None:
        super().__init__(message)
        self.job = job


STATUS_ERRORS = {
    400: BadRequestError,
    401: AuthenticationError,
    402: AccessDeniedError,
    403: AccessDeniedError,
    404: NotFoundError,
    409: VideoNotReadyError,
    424: JobFailedError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}
