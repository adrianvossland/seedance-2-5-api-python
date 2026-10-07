"""Seedance 2.5 client: one class, standard library only.

    from seedance import Seedance

    client = Seedance()                                  # SEEDANCE_API_KEY from the environment
    job = client.text_to_video("A red fox trots through fresh snow at dawn", duration=5)
    job = client.wait(job, on_progress=lambda j: print(j.progress))
    client.download(job, "fox.mp4")
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Union

from . import limits
from .errors import (
    STATUS_ERRORS,
    JobFailedError,
    JobTimeoutError,
    RateLimitError,
    RequestValidationError,
    SeedanceError,
    ServiceUnavailableError,
)
from .jobs import DONE, Job

DEFAULT_BASE_URL = "https://argolink.io/v1"
Media = Union[str, os.PathLike]
JobRef = Union[Job, str]
CHUNK = 1 << 20

# Upload ticket types and the formats Seedance 2.5 reads (JPEG/PNG, MP4/MOV, WAV/MP3).
CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".wav": "audio/wav",
}


def _request_id(job: JobRef) -> str:
    return job.request_id if isinstance(job, Job) else str(job)


class Seedance:
    """Client for the Seedance 2.5 video API (POST /videos/generations, GET /videos/{id}, /content)."""

    model = limits.MODEL

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 4,
        poll_interval: float = 10.0,
        validate: bool = True,
        opener: Optional[Callable[..., Any]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("SEEDANCE_API_KEY")
        if not self.api_key:
            raise SeedanceError("no API key: pass api_key or set SEEDANCE_API_KEY")
        self.base_url = (base_url or os.environ.get("SEEDANCE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.poll_interval = poll_interval
        self.validate = validate
        self._open = opener or urllib.request.urlopen
        self._sleep = sleep

    # -- HTTP ------------------------------------------------------------------------

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None, *, stream: bool = False):
        """Send one API request. 429 and 503 are retried (they are never charged),
        honouring Retry-After; every other error is raised as a typed exception."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(self.base_url + path, data=data, method=method)
            request.add_header("Authorization", f"Bearer {self.api_key}")
            if data is not None:
                request.add_header("Content-Type", "application/json")
            try:
                response = self._open(request, timeout=self.timeout)
            except urllib.error.HTTPError as http_error:
                error = self._to_error(method, path, http_error)
                if isinstance(error, (RateLimitError, ServiceUnavailableError)) and attempt < self.max_retries:
                    delay = getattr(error, "retry_after", None) or min(60.0, 2.0 * 2 ** attempt)
                    self._sleep(delay)
                    continue
                raise error from None
            if stream:
                return response
            with response:
                return json.loads(response.read().decode("utf-8"))
        raise AssertionError("unreachable")

    @staticmethod
    def _to_error(method: str, path: str, http_error: urllib.error.HTTPError) -> SeedanceError:
        text = http_error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
        except ValueError:
            payload = text
        detail = payload.get("error", {}) if isinstance(payload, dict) else {}
        if not isinstance(detail, dict):
            detail = {"message": str(detail)}
        message = detail.get("message") or text[:300] or http_error.reason
        kwargs = dict(status=http_error.code, type=detail.get("type"), code=detail.get("code"),
                      param=detail.get("param"), body=payload)
        cls = STATUS_ERRORS.get(http_error.code, SeedanceError)
        if cls is ServiceUnavailableError:
            header = http_error.headers.get("Retry-After") if http_error.headers else None
            try:
                retry_after = float(header) if header else None
            except ValueError:  # an HTTP date instead of seconds: fall back to backoff
                retry_after = None
            return cls(f"{method} {path}: {message}", retry_after=retry_after, **kwargs)
        return cls(f"{method} {path} -> {http_error.code}: {message}", **kwargs)

    # -- jobs ------------------------------------------------------------------------

    def submit(self, body: Dict[str, Any]) -> Job:
        """POST a raw request body (model is filled in) and return the pending job."""
        body = {"model": self.model, **body}
        if self.validate and body["model"] == limits.MODEL:
            found = limits.problems(body)
            if found:
                raise RequestValidationError(found)
        accepted = self._call("POST", "/videos/generations", body)
        return Job.from_api({"status": "pending", **accepted})

    def get(self, job: JobRef) -> Job:
        """Read the job once: status, progress, ETA, usage or error."""
        return Job.from_api(self._call("GET", f"/videos/{_request_id(job)}"))

    def wait(
        self,
        job: JobRef,
        *,
        poll_interval: Optional[float] = None,
        timeout: float = 1800.0,
        on_progress: Optional[Callable[[Job], None]] = None,
    ) -> Job:
        """Poll until the job is done. Raises JobFailedError when it fails or expires and
        JobTimeoutError after ``timeout`` seconds (the job keeps running server-side)."""
        interval = self.poll_interval if poll_interval is None else poll_interval
        deadline = time.monotonic() + timeout
        while True:
            current = self.get(job)
            if current.status == DONE:
                return current
            if current.is_finished:
                error = current.error or {}
                raise JobFailedError(
                    f"job {current.request_id} {current.status}: {error.get('message', 'no video was produced')}",
                    job=current, code=error.get("code"), retryable=error.get("retryable"),
                    field=error.get("field"), body=current.raw,
                )
            if on_progress:
                on_progress(current)
            if time.monotonic() + interval > deadline:
                raise JobTimeoutError(f"job {current.request_id} still {current.status} after {timeout:.0f}s", job=current)
            self._sleep(interval)

    def download(self, job: JobRef, path: Union[str, os.PathLike]) -> Path:
        """Stream the finished MP4 to ``path`` in 1 MiB chunks."""
        target = Path(path)
        response = self._call("GET", f"/videos/{_request_id(job)}/content", stream=True)
        with response, open(target, "wb") as handle:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
        return target

    def run(self, job: JobRef, path: Union[str, os.PathLike], **wait_options: Any) -> Job:
        """wait() then download(); returns the finished job (its usage holds the billed seconds)."""
        finished = self.wait(job, **wait_options)
        self.download(finished, path)
        return finished

    # -- media -----------------------------------------------------------------------

    def upload(self, path: Union[str, os.PathLike], content_type: Optional[str] = None) -> str:
        """Upload a local file and return its media_url (readable for seven days).

        Asks for a ticket, then PUTs the bytes to the presigned upload_url with the
        declared Content-Type. The API key is not sent to the storage host."""
        source = Path(path)
        content_type = content_type or CONTENT_TYPES.get(source.suffix.lower()) or mimetypes.guess_type(source.name)[0]
        if not content_type:
            raise SeedanceError(f"cannot tell the content type of {source.name}; pass content_type")
        kind = content_type.split("/", 1)[0]
        if kind not in ("image", "video", "audio"):
            raise SeedanceError(f"{source.name} is {content_type}; upload an image, video or audio file")
        ticket = self._call("POST", "/media/uploads", {
            "model": self.model, "type": kind, "content_type": content_type,
            "size_bytes": source.stat().st_size,
        })
        put = urllib.request.Request(ticket["upload_url"], data=source.read_bytes(), method="PUT")
        put.add_header("Content-Type", content_type)
        try:
            self._open(put, timeout=max(self.timeout, 300.0)).close()
        except urllib.error.HTTPError as error:
            raise SeedanceError(f"upload of {source.name} failed with {error.code}", status=error.code) from None
        return ticket["media_url"]

    def _media(self, value: Media) -> Dict[str, str]:
        """An https URL is used as it is; anything else must be a local file and is uploaded."""
        text = os.fspath(value)
        if text.startswith("https://"):
            return {"url": text}
        if text.startswith("http://"):
            raise SeedanceError(f"{text}: media URLs must use https")
        if not Path(text).is_file():
            raise SeedanceError(f"{text}: not an https URL and not a local file")
        return {"url": self.upload(text)}

    # -- modes -----------------------------------------------------------------------

    def text_to_video(self, prompt: str, *, duration: int = 5, resolution: str = "720p",
                      aspect_ratio: str = "16:9", generate_audio: bool = True) -> Job:
        return self.submit({"prompt": prompt, "duration": duration, "resolution": resolution,
                            "aspect_ratio": aspect_ratio, "generate_audio": generate_audio})

    def image_to_video(self, prompt: str, first_frame: Media, *, last_frame: Optional[Media] = None,
                       duration: int = 5, resolution: str = "720p", generate_audio: bool = True) -> Job:
        """First frame, or first + last frame. The ratio follows the first frame."""
        body = {"prompt": prompt, "duration": duration, "resolution": resolution,
                "aspect_ratio": "adaptive", "generate_audio": generate_audio,
                "start_image": self._media(first_frame)}
        if last_frame is not None:
            body["end_image"] = self._media(last_frame)
        return self.submit(body)

    def reference_to_video(self, prompt: str, *, images: Iterable[Media] = (), videos: Iterable[Media] = (),
                           audios: Iterable[Media] = (), duration: int = 5, resolution: str = "720p",
                           aspect_ratio: str = "16:9", generate_audio: bool = True) -> Job:
        """Up to 30 images, 10 videos and 10 audio clips; name them as @Image 1, @Video 1, @Audio 1."""
        body: Dict[str, Any] = {"prompt": prompt, "duration": duration, "resolution": resolution,
                                "aspect_ratio": aspect_ratio, "generate_audio": generate_audio}
        for name, items in (("reference_images", images), ("reference_videos", videos), ("reference_audios", audios)):
            items = list(items)
            if items:
                body[name] = [self._media(item) for item in items]
        return self.submit(body)

    def edit_video(self, prompt: str, video: Media, *, resolution: str = "720p",
                   generate_audio: Optional[bool] = None) -> Job:
        """Rewrite an existing 4-30 s clip; the result keeps its length and ratio.
        Billed as output and as a reference video, so a 5 s edit bills 10 s."""
        body: Dict[str, Any] = {"prompt": prompt, "omni_reference_task_type": "edit",
                                "resolution": resolution, "reference_videos": [self._media(video)]}
        if generate_audio is not None:
            body["generate_audio"] = generate_audio
        return self.submit(body)
