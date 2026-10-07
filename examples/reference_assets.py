"""Reference mode: two images, one motion clip and a soundtrack, named in the prompt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seedance import Seedance  # noqa: E402

client = Seedance()
job = client.reference_to_video(
    "The dancer from @Image 1 performs on the rooftop in @Image 2, "
    "copying the footwork of @Video 1 in time with @Audio 1",
    images=["https://example.com/dancer.png", "https://example.com/rooftop.jpg"],
    videos=["footwork.mp4"],        # 3.2 s clip: adds 3 billed seconds
    audios=["https://example.com/beat.mp3"],
    duration=10,
    resolution="720p",
    aspect_ratio="9:16",
)
done = client.run(job, "rooftop-dance.mp4")
print(done.usage)  # Usage(output_seconds=10, reference_video_seconds=3, billed_seconds=13)
