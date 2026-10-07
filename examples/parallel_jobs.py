"""Run several prompts at once and resubmit jobs whose failure is marked retryable.

An account runs up to 50 Seedance 2.5 jobs at the same time; past that the API
answers 429, which the client already retries with backoff.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seedance import JobFailedError, Seedance  # noqa: E402

PROMPTS = {
    "espresso": "Espresso pours into a glass cup, macro, steam rising, morning light",
    "surfer": "A surfer drops into a glassy wave at sunrise, drone shot from behind",
    "origami": "A paper crane folds itself on a wooden desk, top-down, soft shadows",
    "tram": "A red tram crosses a rainy bridge at dusk, reflections on the wet rails",
}

client = Seedance()


def render(name: str, prompt: str, attempts: int = 2) -> str:
    for attempt in range(1, attempts + 1):
        job = client.text_to_video(prompt, duration=5, resolution="480p")
        try:
            done = client.run(job, f"{name}.mp4")
            return f"{name}: {done.usage.billed_seconds} s billed"
        except JobFailedError as error:
            if not error.retryable or attempt == attempts:
                return f"{name}: failed with {error.code} ({error.message})"
    return f"{name}: gave up"


with ThreadPoolExecutor(max_workers=len(PROMPTS)) as pool:
    for line in pool.map(render, PROMPTS, PROMPTS.values()):
        print(line)
