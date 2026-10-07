"""Cost estimates from the published per-second rates.

Rates read from https://argolink.io/en/models/seedance-2.5 on 2026-10-07; the
official column is the BytePlus ModelArk list price for the same tier, which the
model page shows next to it. Re-check the page before budgeting: it wins over
these constants.

Billing rule (from the API guide): billed seconds = the delivered video's length
rounded to whole seconds + the total length of the reference videos with any
part of a second dropped. Reference images and audio are free; an edit counts the
edited video both as output and as a reference video.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

CHECKED = "2026-10-07"
SOURCE = "https://argolink.io/en/models/seedance-2.5"
RATES = {"480p": 0.0874, "720p": 0.196, "1080p": 0.483}
OFFICIAL_RATES = {"480p": 0.1028, "720p": 0.2311, "1080p": 0.5686}


@dataclass(frozen=True)
class Estimate:
    resolution: str
    billed_seconds: int
    rate: float
    usd: float
    official_usd: float


def _whole(seconds: float) -> int:
    """Round half up, as a video length is rounded to whole seconds."""
    return int(math.floor(seconds + 0.5))


def billed_seconds(output_seconds: float, reference_video_seconds: Iterable[float] = ()) -> int:
    return _whole(output_seconds) + int(math.floor(sum(reference_video_seconds)))


def estimate(
    duration: float = 5,
    resolution: str = "720p",
    reference_video_seconds: Iterable[float] = (),
    edit_source_seconds: Optional[float] = None,
) -> Estimate:
    """Estimate one job. For an edit pass the length of the video being edited."""
    if resolution not in RATES:
        raise ValueError(f"unknown resolution {resolution!r}; Seedance 2.5 has {', '.join(RATES)}")
    if edit_source_seconds is not None:
        seconds = billed_seconds(edit_source_seconds, [edit_source_seconds])
    else:
        seconds = billed_seconds(duration, reference_video_seconds)
    return Estimate(
        resolution=resolution,
        billed_seconds=seconds,
        rate=RATES[resolution],
        usd=round(seconds * RATES[resolution], 4),
        official_usd=round(seconds * OFFICIAL_RATES[resolution], 4),
    )
