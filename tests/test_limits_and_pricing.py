import pytest

from seedance import estimate, problems

PROMPT = {"model": "seedance-2.5", "prompt": "a lighthouse in a storm"}
IMG = {"url": "https://example.com/a.png"}
VID = {"url": "https://example.com/a.mp4"}


@pytest.mark.parametrize("body", [
    PROMPT,
    {**PROMPT, "duration": 30, "resolution": "1080p", "aspect_ratio": "21:9"},
    {**PROMPT, "start_image": IMG, "end_image": IMG, "aspect_ratio": "adaptive"},
    {**PROMPT, "reference_images": [IMG] * 30, "reference_videos": [VID] * 10, "reference_audios": [VID] * 10},
    {**PROMPT, "reference_audios": [{"url": "https://example.com/beat.mp3"}]},
    {**PROMPT, "omni_reference_task_type": "edit", "reference_videos": [VID]},
])
def test_documented_requests_pass(body):
    assert problems(body) == []


@pytest.mark.parametrize("body, fragment", [
    ({"model": "seedance-2.5"}, "prompt is required"),
    ({**PROMPT, "prompt": "é" * 20_001}, "bytes"),
    ({**PROMPT, "duration": 3}, "duration"),
    ({**PROMPT, "duration": 5.5}, "duration"),
    ({**PROMPT, "resolution": "4k"}, "resolution"),
    ({**PROMPT, "aspect_ratio": "adaptive"}, "aspect_ratio"),
    ({**PROMPT, "start_image": IMG, "aspect_ratio": "16:9"}, "adaptive"),
    ({**PROMPT, "end_image": IMG}, "end_image needs a start_image"),
    ({**PROMPT, "start_image": IMG, "reference_images": [IMG]}, "cannot be combined"),
    ({**PROMPT, "reference_images": [IMG] * 31}, "31 reference images"),
    ({**PROMPT, "omni_reference_task_type": "edit", "reference_videos": [VID, VID]}, "exactly one"),
    ({**PROMPT, "omni_reference_task_type": "edit", "reference_videos": [VID], "duration": 5}, "leave duration out"),
    ({**PROMPT, "omni_reference_task_type": "extend", "reference_videos": [VID]}, "extend"),
    ({**PROMPT, "seed": 42}, "seed"),
    ({**PROMPT, "n": 2}, "n must be 1"),
    ({**PROMPT, "reference_images": [{"url": "http://example.com/a.png"}]}, "https"),
])
def test_documented_rejections(body, fragment):
    assert any(fragment in problem for problem in problems(body)), problems(body)


def test_text_job_cost():
    quote = estimate(8, "720p")
    assert (quote.billed_seconds, quote.usd) == (8, 1.568)
    assert quote.official_usd == 1.8488


def test_reference_video_seconds_are_added_with_fractions_dropped():
    # documented example: a 5 s video with a 2.4 s reference video bills 7 s
    assert estimate(5, "480p", [2.4]).billed_seconds == 7
    assert estimate(4, "720p", [1.6, 1.6]).billed_seconds == 7


def test_edit_bills_the_source_twice():
    quote = estimate(resolution="720p", edit_source_seconds=5)
    assert (quote.billed_seconds, quote.usd) == (10, 1.96)


def test_unknown_resolution_is_refused():
    with pytest.raises(ValueError):
        estimate(5, "4k")
