"""Text to video: a prompt alone, 8 seconds at 720p, then the price it was billed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run from a clone without installing

from seedance import Seedance, estimate  # noqa: E402

client = Seedance()
job = client.text_to_video(
    "A paper lantern drifts up from a night market, the camera tilts up to follow it into the stars",
    duration=8,
    resolution="720p",
    aspect_ratio="9:16",
)
print("request_id:", job.request_id)  # keep it: wait() can resume from it later

done = client.run(job, "lantern.mp4", on_progress=lambda j: print(f"{j.progress or 0}%"))
seconds = done.usage.billed_seconds
print(f"billed {seconds} s, ${estimate(seconds, '720p').usd}")  # 8 s, $1.568
