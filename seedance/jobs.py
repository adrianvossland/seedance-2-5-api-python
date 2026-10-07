"""Typed views of the job object returned by GET /v1/videos/{request_id}."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

PENDING, DONE, FAILED, EXPIRED = "pending", "done", "failed", "expired"


@dataclass(frozen=True)
class Usage:
    """What a finished job is billed for: billed_seconds = output + reference video seconds."""

    output_seconds: int
    reference_video_seconds: int
    billed_seconds: int

    @classmethod
    def from_api(cls, payload: Optional[Dict[str, Any]]) -> Optional["Usage"]:
        if not payload:
            return None
        return cls(
            output_seconds=int(payload.get("output_seconds", 0)),
            reference_video_seconds=int(payload.get("reference_video_seconds", 0)),
            billed_seconds=int(payload.get("billed_seconds", 0)),
        )


@dataclass(frozen=True)
class Job:
    request_id: str
    status: str
    model: Optional[str] = None
    created_at: Optional[int] = None
    progress: Optional[int] = None
    eta_seconds: Optional[int] = None
    video_url: Optional[str] = None
    video_duration: Optional[float] = None
    usage: Optional[Usage] = None
    error: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, payload: Dict[str, Any]) -> "Job":
        video = payload.get("video") or {}
        return cls(
            request_id=payload["request_id"],
            status=payload.get("status", PENDING),
            model=payload.get("model"),
            created_at=payload.get("created_at"),
            progress=payload.get("progress"),
            eta_seconds=payload.get("estimated_seconds_remaining"),
            video_url=video.get("url"),
            video_duration=video.get("duration"),
            usage=Usage.from_api(payload.get("usage")),
            error=payload.get("error"),
            raw=dict(payload),
        )

    @property
    def is_pending(self) -> bool:
        return self.status == PENDING

    @property
    def is_done(self) -> bool:
        return self.status == DONE

    @property
    def is_finished(self) -> bool:
        """True for done, failed and expired: the status will not change any more."""
        return self.status in (DONE, FAILED, EXPIRED)
