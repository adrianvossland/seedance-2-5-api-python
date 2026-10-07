import pytest
from conftest import http_error

from seedance import (
    AuthenticationError,
    JobFailedError,
    RequestValidationError,
    Seedance,
    SeedanceError,
    VideoNotReadyError,
)

DONE = {
    "request_id": "r1", "status": "done", "model": "seedance-2.5", "progress": 100,
    "video": {"duration": 5, "url": "https://api.test/v1/videos/r1/content"},
    "usage": {"output_seconds": 5, "reference_video_seconds": 0, "billed_seconds": 5},
}


def test_text_to_video_posts_the_documented_body(api, client):
    api.on("POST", "/videos/generations", {"request_id": "r1"})
    job = client.text_to_video("a red fox in snow", duration=8, resolution="1080p", aspect_ratio="9:16")

    call = api.calls[0]
    assert call["url"] == "https://api.test/v1/videos/generations"
    assert call["headers"]["authorization"] == "Bearer test-key"
    # urllib's default "Python-urllib/3.x" agent is refused by the API's Cloudflare front (403, error 1010)
    assert call["headers"]["user-agent"].startswith("seedance-2-5-api-python/")
    assert call["json"] == {
        "model": "seedance-2.5", "prompt": "a red fox in snow", "duration": 8,
        "resolution": "1080p", "aspect_ratio": "9:16", "generate_audio": True,
    }
    assert (job.request_id, job.status) == ("r1", "pending")


def test_local_first_frame_is_uploaded_then_referenced(api, client, tmp_path):
    frame = tmp_path / "first.png"
    frame.write_bytes(b"\x89PNG fake")
    api.on("POST", "/media/uploads", {"upload_url": "https://storage.test/put/abc", "media_url": "https://cdn.test/abc.png"})
    api.on("PUT", "/put/abc", b"")
    api.on("POST", "/videos/generations", {"request_id": "r2"})

    client.image_to_video("the camera pushes in", frame, last_frame="https://example.com/last.png")

    ticket, put, submit = api.calls
    assert ticket["json"] == {"model": "seedance-2.5", "type": "image", "content_type": "image/png", "size_bytes": 9}
    assert put["method"] == "PUT" and put["data"] == b"\x89PNG fake"
    assert put["headers"]["content-type"] == "image/png"
    assert "authorization" not in put["headers"], "the API key must not reach the storage host"
    assert submit["json"]["start_image"] == {"url": "https://cdn.test/abc.png"}
    assert submit["json"]["end_image"] == {"url": "https://example.com/last.png"}
    assert submit["json"]["aspect_ratio"] == "adaptive"


def test_edit_sends_one_video_and_no_duration(api, client):
    api.on("POST", "/videos/generations", {"request_id": "r3"})
    client.edit_video("make it snow", "https://example.com/street.mp4")
    body = api.calls[0]["json"]
    assert body["omni_reference_task_type"] == "edit"
    assert body["reference_videos"] == [{"url": "https://example.com/street.mp4"}]
    assert "duration" not in body and "aspect_ratio" not in body


def test_wait_reports_progress_then_returns_usage(api, client, sleeps):
    api.on("GET", "/videos/r1",
           {"request_id": "r1", "status": "pending", "progress": 0},
           {"request_id": "r1", "status": "pending", "progress": 61, "estimated_seconds_remaining": 70},
           DONE)
    seen = []
    job = client.wait("r1", on_progress=lambda j: seen.append((j.progress, j.eta_seconds)))
    assert seen == [(0, None), (61, 70)]
    assert sleeps == [10.0, 10.0]
    assert job.usage.billed_seconds == 5 and job.video_url.endswith("/r1/content")


def test_failed_job_raises_with_code_and_retryable(api, client):
    api.on("GET", "/videos/r1", {
        "request_id": "r1", "status": "failed",
        "error": {"code": "capacity_unavailable", "message": "no capacity", "retryable": True},
    })
    with pytest.raises(JobFailedError) as raised:
        client.wait("r1")
    assert raised.value.code == "capacity_unavailable"
    assert raised.value.retryable is True


def test_503_is_retried_after_retry_after(api, client, sleeps):
    api.on("POST", "/videos/generations",
           http_error("https://api.test/v1/videos/generations", 503,
                      {"error": {"type": "overloaded_error", "code": "no_capacity", "message": "busy"}},
                      {"Retry-After": "7"}),
           {"request_id": "r4"})
    assert client.text_to_video("a lighthouse in a storm").request_id == "r4"
    assert sleeps == [7.0]


def test_401_is_not_retried(api, client, sleeps):
    api.on("GET", "/videos/r1", http_error("https://api.test/v1/videos/r1", 401,
                                           {"error": {"type": "authentication_error", "message": "bad key"}}))
    with pytest.raises(AuthenticationError) as raised:
        client.get("r1")
    assert raised.value.status == 401 and sleeps == []


def test_download_streams_the_mp4(api, client, tmp_path):
    api.on("GET", "/videos/r1/content", b"\x00\x00\x00\x18ftypmp42" * 1000)
    path = client.download("r1", tmp_path / "out.mp4")
    assert path.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")


def test_download_before_done_raises_not_ready(api, client, tmp_path):
    api.on("GET", "/videos/r1/content", http_error(
        "https://api.test/v1/videos/r1/content", 409,
        {"error": {"type": "invalid_request_error", "code": "job_video_not_ready", "message": "not ready"}}))
    with pytest.raises(VideoNotReadyError) as raised:
        client.download("r1", tmp_path / "out.mp4")
    assert raised.value.code == "job_video_not_ready"


def test_invalid_request_is_stopped_before_sending(api, client):
    with pytest.raises(RequestValidationError) as raised:
        client.text_to_video("a lighthouse", duration=31)
    assert "duration" in str(raised.value)
    assert api.calls == []


def test_base_url_and_key_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("SEEDANCE_API_KEY", "env-key")
    monkeypatch.setenv("SEEDANCE_BASE_URL", "https://proxy.test/v1/")
    client = Seedance()
    assert (client.api_key, client.base_url) == ("env-key", "https://proxy.test/v1")
    monkeypatch.delenv("SEEDANCE_API_KEY")
    with pytest.raises(SeedanceError):
        Seedance()
