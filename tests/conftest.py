"""A fake HTTP layer: the client is built with opener=FakeAPI(...), so no key,
network or real job is involved."""
import io
import json
import os
import sys
import urllib.error
from email.message import Message

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from seedance import Seedance  # noqa: E402


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def http_error(url, status, payload, headers=None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError(url, status, "error", message, io.BytesIO(json.dumps(payload).encode()))


class FakeAPI:
    """Answers by URL suffix from queued responses; records every request."""

    def __init__(self):
        self.calls = []
        self.routes = {}

    def on(self, method, suffix, *answers):
        self.routes.setdefault((method, suffix), []).extend(answers)
        return self

    def __call__(self, request, timeout=None):
        body = request.data
        self.calls.append({
            "method": request.get_method(),
            "url": request.full_url,
            "headers": {k.lower(): v for k, v in request.header_items()},
            "json": json.loads(body) if body and request.full_url.startswith("https://api.test") else None,
            "data": body,
        })
        for (method, suffix), answers in self.routes.items():
            if request.get_method() == method and request.full_url.endswith(suffix) and answers:
                answer = answers.pop(0)
                if isinstance(answer, Exception):
                    raise answer
                if isinstance(answer, bytes):
                    return Response(answer)
                return Response(json.dumps(answer).encode())
        raise AssertionError(f"unexpected {request.get_method()} {request.full_url}")


@pytest.fixture
def api():
    return FakeAPI()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(api, sleeps):
    return Seedance(api_key="test-key", base_url="https://api.test/v1", opener=api, sleep=sleeps.append)
