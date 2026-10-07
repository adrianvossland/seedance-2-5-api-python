# Seedance 2.5 API for Python — from $0.0874/s (480p)

**ByteDance Seedance 2.5 is live on [ArgoLink](https://argolink.io/gh-seedance-2-5-api-python)**: $0.0874/s at 480p, $0.196/s at 720p and $0.483/s at 1080p, 15% under the official BytePlus price. This package wraps its video API in one dependency-free Python class: text, first/last-frame, multimodal-reference and video-edit jobs, automatic upload of local files, typed errors, and a cost estimate before you submit.

[Install](#install) · [Quick start](#quick-start) · [Modes](#modes) · [Methods](#methods) · [Errors](#errors-and-retries) · [Pricing](#pricing-and-cost-estimates) · [Model page](https://argolink.io/en/models/seedance-2.5)

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue) ![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen) ![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)

<sub>Last checked: 2026-10-07 against the Seedance 2.5 model page and API guide. Unofficial; not affiliated with ByteDance.</sub>

## Why a client instead of three HTTP calls

The raw API is small (submit, poll, download), but a production integration keeps re-solving the same problems. This package solves them once:

- **Validation before sending.** Durations outside 4–30 s, `4k`, a fixed ratio on a first frame, frames mixed with references, a `seed`: caught locally with a readable message, before a request or a cent is spent.
- **Local files just work.** Pass a path where a URL is expected and it is uploaded through a media ticket first. The API key never reaches the storage host.
- **Errors you can branch on.** Every documented HTTP error and job failure becomes an exception with `code`, `param` or `field`, and for failed jobs the API's own `retryable` flag.
- **Polite retries.** `429` and `503` are retried with backoff, honouring `Retry-After`; neither is billed.
- **Streaming downloads** in 1 MiB chunks, and jobs you can resume from a stored `request_id`.
- **Cost estimates** from the published per-second rates, including reference-video seconds and edits.

## Install

```bash
pip install "git+https://github.com/adrianvossland/seedance-2-5-api-python"

# or from a clone, with the test extra
git clone https://github.com/adrianvossland/seedance-2-5-api-python
cd seedance-2-5-api-python
pip install -e ".[test]"
```

Python 3.9 or newer; the standard library is the only dependency.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SEEDANCE_API_KEY` | yes | — | Bearer key; create one at [argolink.io/app/keys](https://argolink.io/app/keys) |
| `SEEDANCE_BASE_URL` | no | `https://argolink.io/v1` | any endpoint that speaks the same `/v1/videos` protocol |

Both can also be passed to the constructor: `Seedance(api_key=..., base_url=...)`.

## Quick start

```python
from seedance import Seedance

client = Seedance()
job = client.text_to_video(
    "A paper lantern drifts up from a night market, the camera tilts up to follow it into the stars",
    duration=8,
    resolution="720p",
    aspect_ratio="9:16",
)
print(job.request_id)                        # store it if the process may restart

done = client.run(job, "lantern.mp4", on_progress=lambda j: print(f"{j.progress}%"))
print(done.usage)                            # Usage(output_seconds=8, reference_video_seconds=0, billed_seconds=8)
```

`text_to_video` returns as soon as the job is accepted. `run` polls every 10 seconds, prints progress through the callback, downloads the MP4 when the job is done and returns the finished job. A 4–10 second clip usually takes 2–5 minutes.

## Modes

Every mode is one method; each returns a pending `Job`. Media arguments accept an `https://` URL or a local path.

**First frame, or first and last frame.** The ratio follows the first frame (`aspect_ratio` is sent as `adaptive`):

```python
job = client.image_to_video(
    "Day turns to night over the harbour while the boats switch on their lights",
    "harbour-day.png",                       # uploaded automatically
    last_frame="harbour-night.png",
    duration=6,
    resolution="1080p",
)
```

**Reference.** Up to 30 images, 10 videos and 10 audio clips (50 in total), named in the prompt as `@Image 1`, `@Video 1`, `@Audio 1`. Audio on its own is allowed:

```python
job = client.reference_to_video(
    "The dancer from @Image 1 performs on the rooftop in @Image 2, copying the footwork of @Video 1 in time with @Audio 1",
    images=["https://example.com/dancer.png", "https://example.com/rooftop.jpg"],
    videos=["footwork.mp4"],
    audios=["https://example.com/beat.mp3"],
    duration=10,
    aspect_ratio="9:16",
)
```

**Edit a video.** One 4–30 s source clip; the result keeps its length and ratio:

```python
job = client.edit_video("Make it a snowy evening, keep the people and the camera move", "street-6s.mp4")
```

**Anything else.** `submit()` takes a raw request body, so every documented field stays reachable, including `size` and the fal/OpenRouter field names:

```python
job = client.submit({"prompt": "A koi pond in the rain, top-down", "size": "1080x1920", "generate_audio": False})
```

Runnable versions of each are in [`examples/`](./examples): [text_to_video.py](./examples/text_to_video.py), [first_and_last_frame.py](./examples/first_and_last_frame.py), [reference_assets.py](./examples/reference_assets.py), [edit_video.py](./examples/edit_video.py) and [parallel_jobs.py](./examples/parallel_jobs.py).

## Methods

| Method | Returns | What it does |
|---|---|---|
| `text_to_video(prompt, *, duration=5, resolution="720p", aspect_ratio="16:9", generate_audio=True)` | `Job` | prompt-only job |
| `image_to_video(prompt, first_frame, *, last_frame=None, duration=5, resolution="720p", generate_audio=True)` | `Job` | first frame or first + last frame |
| `reference_to_video(prompt, *, images=(), videos=(), audios=(), duration=5, resolution="720p", aspect_ratio="16:9", generate_audio=True)` | `Job` | multimodal reference job |
| `edit_video(prompt, video, *, resolution="720p", generate_audio=None)` | `Job` | edit a 4–30 s clip |
| `submit(body)` | `Job` | any raw body; `model` is filled in and the body is validated |
| `get(job)` | `Job` | one status read |
| `wait(job, *, poll_interval=10, timeout=1800, on_progress=None)` | `Job` | poll until `done`; raises on `failed`/`expired` or local timeout |
| `download(job, path)` | `Path` | stream the MP4 to disk |
| `run(job, path, **wait_options)` | `Job` | `wait` + `download` |
| `upload(path, content_type=None)` | `str` | upload a local file, return its `media_url` |

Every `job` argument also accepts a bare `request_id` string. Module-level helpers: `estimate(...)` for costs and `problems(body)` for validation. A `Job` exposes `request_id`, `status`, `progress`, `eta_seconds`, `video_url`, `video_duration`, `usage` (`output_seconds`, `reference_video_seconds`, `billed_seconds`), `error` and the untouched `raw` payload.

The constructor takes `api_key`, `base_url`, `timeout=60`, `max_retries=4`, `poll_interval=10`, `validate=True`, plus `opener` and `sleep` hooks that the tests use to replace the network.

## Errors and retries

```python
from seedance import JobFailedError, RequestValidationError

try:
    done = client.run(client.text_to_video("A lighthouse in a storm", duration=12), "storm.mp4")
except RequestValidationError as error:
    print("fix the request:", error.problems)
except JobFailedError as error:
    if error.retryable:
        ...                                  # same request again is safe and was not billed
    else:
        print(error.code, error.field, error.message)
```

| Exception | Raised when | Useful attributes | What to do |
|---|---|---|---|
| `RequestValidationError` | a local check failed; nothing was sent | `problems` | fix the request |
| `BadRequestError` | `400` `field_invalid`, `json_invalid` or `request_unsupported` | `code`, `param` | fix the request |
| `AuthenticationError` | `401` | `status` | check the key |
| `AccessDeniedError` | `402` / `403`: balance, or no video permission on the key | `status` | top up or switch key |
| `NotFoundError` | `404` `video_request_not_found` | `code` | wrong ID or another user's key |
| `VideoNotReadyError` | `409` `job_video_not_ready` | `code` | call `wait()` first |
| `RateLimitError` | `429`, still failing after `max_retries` | `status` | lower your concurrency |
| `ServiceUnavailableError` | `503` `no_capacity`, still failing after retries | `retry_after` | try again later |
| `JobFailedError` | status `failed` / `expired`, or a `424` download | `code`, `retryable`, `field`, `job` | resubmit if `retryable` |
| `JobTimeoutError` | `wait()` hit its local `timeout` | `job` | call `wait()` again; the job keeps running |

All of them subclass `SeedanceError`. Failed and expired jobs are never billed, and the codes you can meet on a failed job are `invalid_input`, `content_policy_violation`, `copyright_violation`, `generation_failed`, `generation_timeout`, `capacity_unavailable`, `internal_error` and `cancelled`.

## What is checked before a request is sent

`submit()` runs `seedance.problems(body)` and refuses to send a body that breaks a documented Seedance 2.5 rule:

- `prompt` present and at most 40,000 bytes of UTF-8; the JSON body under 1 MiB
- `duration` a whole number from 4 to 30 (an edit takes none)
- `resolution` one of `480p`, `720p`, `1080p`
- `aspect_ratio` one of `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16` for text and reference jobs, and only `adaptive` for frame and edit jobs
- `end_image` only together with `start_image`, and frames never mixed with reference lists
- at most 30 images, 10 videos and 10 audio clips, 50 in total
- an edit carries exactly one video and nothing else; `extend` is not a task type
- no `seed`, no `watermark: true`, `n` only 1, and every media URL on `https://`

Pass `validate=False` to skip the checks. Bodies whose `model` is not `seedance-2.5` are sent unchecked, so the same client can post to `seedance-2.0` and its Fast and Mini versions, which share the endpoint.

## Pricing and cost estimates

```python
from seedance import estimate

estimate(10, "1080p")                                  # 10 s -> $4.83
estimate(5, "720p", reference_video_seconds=[3.6])     # 5 + 3 = 8 s -> $1.568
estimate(resolution="720p", edit_source_seconds=6)     # an edit bills 6 + 6 = 12 s -> $2.352
```

Seconds are billed as the output length rounded to whole seconds plus the reference videos' total with any fraction dropped. Reference images, audio and uploads are free, and nothing is charged for a failed or expired job. `estimate()` returns the billed seconds, the rate, the cost and the official list price for the same job.

Price per second of output without video input, as each provider publishes it:

| Provider | 480p | 720p | 1080p | 5 s at 1080p |
|---|---:|---:|---:|---:|
| **[ArgoLink](https://argolink.io/en/models/seedance-2.5)** | **$0.0874** | **$0.196** | **$0.483** | **$2.42** |
| [BytePlus ModelArk](https://docs.byteplus.com/en/docs/modelark/model-pricing) (official) | $0.1028 | $0.2311 | $0.5686 | $2.84 |
| [Kie.ai](https://kie.ai/seedance-2-5) | $0.140 | $0.315 | $0.790 | $3.95 |
| [fal.ai](https://fal.ai/models/bytedance/seedance-2.5/text-to-video) | $0.2205 | $0.4730 | $1.164 | $5.82 |

<sub>All four pages read on 2026-10-07. BytePlus bills $10.70 per million tokens ($11.70 at 1080p); the per-second figures apply that to a 16:9 frame at 24 fps, and BytePlus's own 5 s 1080p example comes to $2.843.</sub>

With a reference video in the request the providers part ways. ArgoLink adds the reference seconds at the same per-second rate. BytePlus ($6.40 per million tokens, $7.00 at 1080p), Kie.ai ($0.085 / $0.190 / $0.475 per second) and fal (its token price × 0.6) switch to a lower rate but count input and output seconds together. For video-heavy jobs, compare with your own clip lengths.

## Running many jobs

An account can run up to 50 Seedance 2.5 jobs at once, whatever it has spent. A `Seedance` instance holds no per-request state, so share one across threads. [`parallel_jobs.py`](./examples/parallel_jobs.py) renders several prompts with a `ThreadPoolExecutor` and resubmits only failures marked `retryable`. If you go past the limit, the API answers `429`, which the client retries with backoff before raising `RateLimitError`.

## Command line

The package installs a `seedance` command (also available as `python -m seedance`):

```bash
seedance "A paper lantern drifts up from a night market" -d 8 -r 720p -a 9:16 -o lantern.mp4
seedance "Day turns to night over the harbour" --first-frame day.png --last-frame night.png -r 1080p
seedance "Make it snow" --edit street.mp4 --estimate --edit-seconds 6   # 12 s x $0.196/s = $2.3520 at 720p
```

Local files are uploaded, progress goes to stderr, and `--estimate` prints the cost without calling the API.

## Limits at a glance

| | Seedance 2.5 |
|---|---|
| Model ID | `seedance-2.5` |
| Duration | 4–30 s, default 5 |
| Resolution | 480p, 720p (default), 1080p |
| Aspect ratio | 21:9, 16:9 (default), 4:3, 1:1, 3:4, 9:16; frames: adaptive |
| Images | JPEG or PNG, ≤ 20 MiB, ≤ 30 per request |
| Reference video | MP4 or MOV, ≤ 100 MiB, 2–30 s each and 30 s together, ≤ 10 |
| Reference audio | WAV or MP3, ≤ 15 MB, 2–30 s each and 30 s together, ≤ 10 |
| Output | one 24 fps H.264 MP4 with a generated AAC soundtrack (off with `generate_audio=False`) |
| Not supported | `seed`, `watermark: true`, more than one video per request, 4K |

## FAQ

**Does it support asyncio?**
The client is synchronous. In async code, run the blocking calls in a thread: `await asyncio.to_thread(client.run, job, "out.mp4")`.

**How do I resume a job after a crash?**
Store `job.request_id` when you submit. Later, `client.wait(request_id)` and `client.download(request_id, path)` pick it up; only the key that created the job can read it.

**Why does the client refuse my first-frame request?**
Seedance 2.5 frame jobs take their ratio from the first frame, so `aspect_ratio` must be `adaptive` or absent; `image_to_video()` sends `adaptive` for you. Frames also cannot be combined with reference images.

**Can I use it with Seedance 2.0?**
Yes, through `submit({"model": "seedance-2.0", ...})`. Local validation is skipped for other models, because the 2.0 family has different limits (4–15 s, up to 4K, 9 images, 3 videos and 3 audio clips).

**Is there a webhook?**
No. The API is poll-only; `wait()` polls every 10 seconds, which matches the documented 10–15 second interval.

**Why does my own `urllib` code get `403` with "error code: 1010"?**
The API sits behind Cloudflare, which refuses urllib's default `Python-urllib/3.x` User-Agent (checked 2026-10-07; `requests`, Node's `fetch` and `curl` pass). Send any descriptive `User-Agent` header. This client sends `seedance-2-5-api-python/0.1.0`.

**Can I point it at another provider?**
Set `SEEDANCE_BASE_URL` to any endpoint that implements the same `/v1/videos/generations`, `/v1/videos/{request_id}` and `/content` routes and the `pending`, `done`, `failed`, `expired` statuses.

## Tests

```bash
pip install -e ".[test]"
pytest
```

The 37 tests replace the network with a fake opener, so they need no key and create no jobs. They cover request bodies for each mode, the upload ticket and PUT, polling, retries on `503` with `Retry-After`, typed errors, local validation and the billing arithmetic.

## License

MIT
