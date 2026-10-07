"""Python client for the ByteDance Seedance 2.5 video API (standard library only)."""
from .client import DEFAULT_BASE_URL, Seedance
from .errors import (
    AccessDeniedError,
    AuthenticationError,
    BadRequestError,
    JobFailedError,
    JobTimeoutError,
    NotFoundError,
    RateLimitError,
    RequestValidationError,
    SeedanceError,
    ServiceUnavailableError,
    VideoNotReadyError,
)
from .jobs import Job, Usage
from .limits import problems
from .pricing import Estimate, estimate

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_BASE_URL", "Seedance", "Job", "Usage", "Estimate", "estimate", "problems",
    "SeedanceError", "RequestValidationError", "BadRequestError", "AuthenticationError",
    "AccessDeniedError", "NotFoundError", "VideoNotReadyError", "RateLimitError",
    "ServiceUnavailableError", "JobFailedError", "JobTimeoutError",
]
