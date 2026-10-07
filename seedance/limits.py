"""Seedance 2.5 request limits, checked locally before anything is sent.

The API rejects these requests too (with HTTP 400, or as a failed job), but a
local check gives a clearer message and costs no round trip. The numbers come
from the model page and API guide as they read on 2026-10-07:
https://argolink.io/en/models/seedance-2.5 and https://argolink.io/en/docs#/seedance
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

MODEL = "seedance-2.5"
MIN_DURATION, MAX_DURATION, DEFAULT_DURATION = 4, 30, 5
RESOLUTIONS = ("480p", "720p", "1080p")
DEFAULT_RESOLUTION = "720p"
FIXED_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
MAX_IMAGES, MAX_VIDEOS, MAX_AUDIOS, MAX_ASSETS = 30, 10, 10, 50
MAX_PROMPT_BYTES = 40_000
MAX_BODY_BYTES = 1024 * 1024
REFERENCE_LISTS = ("reference_images", "reference_videos", "reference_audios")


def _urls(value: Any) -> List[str]:
    items = value if isinstance(value, list) else [value]
    return [item.get("url", "") if isinstance(item, dict) else str(item) for item in items]


def problems(body: Dict[str, Any]) -> List[str]:
    """Return every documented rule the request body breaks (an empty list if none)."""
    found: List[str] = []
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        found.append("prompt is required in every mode")
    elif len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        found.append(f"prompt is {len(prompt.encode('utf-8'))} bytes; the limit is {MAX_PROMPT_BYTES}")

    is_edit = body.get("omni_reference_task_type") == "edit"
    has_frames = "start_image" in body or "end_image" in body
    references = {name: body.get(name) or [] for name in REFERENCE_LISTS}

    task_type = body.get("omni_reference_task_type")
    if task_type not in (None, "edit", "auto", "reference"):
        found.append(f"omni_reference_task_type {task_type!r} is not supported (extend is not available)")

    duration = body.get("duration")
    if is_edit:
        if duration not in (None, -1):
            found.append("an edit keeps the length of its video: leave duration out")
    elif duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, int)
        or not MIN_DURATION <= duration <= MAX_DURATION
    ):
        found.append(f"duration must be a whole number of seconds from {MIN_DURATION} to {MAX_DURATION}")

    resolution = body.get("resolution")
    if resolution is not None and resolution not in RESOLUTIONS:
        found.append(f"resolution must be one of {', '.join(RESOLUTIONS)} (4K is a Seedance 2.0 tier)")

    ratio = body.get("aspect_ratio")
    if ratio is not None:
        if has_frames or is_edit:
            if ratio != "adaptive":
                found.append("frame and edit requests take aspect_ratio 'adaptive' only (or leave it out)")
        elif ratio not in FIXED_RATIOS:
            found.append(f"aspect_ratio must be one of {', '.join(FIXED_RATIOS)} for text and reference requests")

    if "end_image" in body and "start_image" not in body:
        found.append("end_image needs a start_image")
    if has_frames and any(references.values()):
        found.append("start_image/end_image cannot be combined with reference lists")

    images, videos, audios = (len(references[name]) for name in REFERENCE_LISTS)
    if images > MAX_IMAGES:
        found.append(f"{images} reference images; the limit is {MAX_IMAGES}")
    if videos > MAX_VIDEOS:
        found.append(f"{videos} reference videos; the limit is {MAX_VIDEOS}")
    if audios > MAX_AUDIOS:
        found.append(f"{audios} reference audio clips; the limit is {MAX_AUDIOS}")
    if images + videos + audios > MAX_ASSETS:
        found.append(f"{images + videos + audios} reference assets; the limit is {MAX_ASSETS} in total")

    if is_edit:
        if videos != 1:
            found.append("an edit takes exactly one entry in reference_videos: the video to edit")
        if images or audios or has_frames:
            found.append("an edit carries only the video it edits: no images, audio or frames")

    if body.get("n", 1) != 1:
        found.append("n must be 1: every request produces one video")
    if "seed" in body:
        found.append("seed is not supported on Seedance 2.5")
    if body.get("watermark") is True:
        found.append("watermark: true is not supported")

    for name in ("start_image", "end_image") + REFERENCE_LISTS:
        if name in body:
            for url in _urls(body[name]):
                if not url.startswith("https://"):
                    found.append(f"{name} must be a public https:// URL (got {url[:40]!r})")

    if len(json.dumps(body).encode("utf-8")) >= MAX_BODY_BYTES:
        found.append("the JSON body must stay under 1 MiB; upload large inputs instead of inlining them")
    return found
