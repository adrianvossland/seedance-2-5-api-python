"""Edit an existing clip. Quote it first: an edit bills the source twice."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seedance import Seedance, estimate  # noqa: E402

quote = estimate(resolution="720p", edit_source_seconds=6)
print(f"expected: {quote.billed_seconds} s, ${quote.usd}")  # 12 s, $2.352

client = Seedance()
job = client.edit_video(
    "Make it a snowy evening with lit shop windows; keep the people and the camera move",
    "street-6s.mp4",
    resolution="720p",
)
client.run(job, "street-snow.mp4")
