"""First and last frame from local images: both are uploaded, the ratio follows the first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seedance import Seedance  # noqa: E402

client = Seedance()
job = client.image_to_video(
    "Day turns to night over the harbour while the boats switch on their lights",
    "harbour-day.png",              # local file -> uploaded, media_url used
    last_frame="harbour-night.png",
    duration=6,
    resolution="1080p",
)
client.run(job, "harbour.mp4")
