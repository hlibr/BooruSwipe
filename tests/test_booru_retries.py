"""Tests for booru API retry behavior."""

import asyncio

import httpx

from booruswipe.gelbooru.client import DanbooruClient, E621Client, GelbooruClient


class FakeResponse:
    """Minimal response object for exercising retry logic."""

    def __init__(self, status_code: int, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.request = httpx.Request("GET", "https://example.com")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=self,
            )

    def json(self):
        return self._payload


class FakeAsyncClient:
    """Minimal async client that returns a scripted sequence of outcomes."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.headers = {}
        self.auth = None

    async def get(self, url):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_booru_request_retries_on_retryable_status_and_succeeds(monkeypatch):
    """Retryable booru status codes should back off and eventually succeed."""
    monkeypatch.setenv("BOORU_API_MAX_RETRIES", "3")
    monkeypatch.setenv("BOORU_API_RETRY_BASE_DELAY", "0.1")
    monkeypatch.setenv("BOORU_API_RETRY_MAX_DELAY", "0.5")

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr("booruswipe.gelbooru.client.asyncio.sleep", fake_sleep)

    client = DanbooruClient()
    client._client = FakeAsyncClient(
        [
            FakeResponse(503),
            FakeResponse(503),
            FakeResponse(200, payload={"ok": True}),
        ]
    )

    result = asyncio.run(client._request(tags="cat", limit="1"))

    assert result == {"ok": True}
    assert client._client.calls == 3
    assert sleep_calls == [0.1, 0.2]


def test_booru_request_retries_on_timeout(monkeypatch):
    """Network timeouts should back off and retry."""
    monkeypatch.setenv("BOORU_API_MAX_RETRIES", "2")
    monkeypatch.setenv("BOORU_API_RETRY_BASE_DELAY", "0.1")
    monkeypatch.setenv("BOORU_API_RETRY_MAX_DELAY", "0.5")

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr("booruswipe.gelbooru.client.asyncio.sleep", fake_sleep)

    request = httpx.Request("GET", "https://example.com")
    client = E621Client()
    client._client = FakeAsyncClient(
        [
            httpx.ReadTimeout("timeout", request=request),
            FakeResponse(200, payload={"ok": True}),
        ]
    )

    result = asyncio.run(client._request(tags="cat", limit="1"))

    assert result == {"ok": True}
    assert client._client.calls == 2
    assert sleep_calls == [0.1]


def test_booru_request_honors_retry_after(monkeypatch):
    """Retry-After should override the exponential backoff delay."""
    monkeypatch.setenv("BOORU_API_MAX_RETRIES", "2")
    monkeypatch.setenv("BOORU_API_RETRY_BASE_DELAY", "0.1")
    monkeypatch.setenv("BOORU_API_RETRY_MAX_DELAY", "0.5")

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr("booruswipe.gelbooru.client.asyncio.sleep", fake_sleep)

    client = GelbooruClient()
    client._client = FakeAsyncClient(
        [
            FakeResponse(429, headers={"Retry-After": "2"}),
            FakeResponse(200, payload={"post": [{"id": 1, "tag_string": "cat"}]}),
        ]
    )

    result = asyncio.run(client._request(tags="cat", limit=1, pid=0))

    assert result == {"post": [{"id": 1, "tag_string": "cat"}]}
    assert client._client.calls == 2
    assert sleep_calls == [2.0]


def test_danbooru_get_post_retries(monkeypatch):
    """Direct post fetches should also retry transient failures."""
    monkeypatch.setenv("BOORU_API_MAX_RETRIES", "2")
    monkeypatch.setenv("BOORU_API_RETRY_BASE_DELAY", "0.1")
    monkeypatch.setenv("BOORU_API_RETRY_MAX_DELAY", "0.5")

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr("booruswipe.gelbooru.client.asyncio.sleep", fake_sleep)

    client = DanbooruClient()
    client._client = FakeAsyncClient(
        [
            FakeResponse(502),
            FakeResponse(
                200,
                payload={
                    "id": 7,
                    "file_url": "https://example.com/image.jpg",
                    "tag_string": "cat",
                },
            ),
        ]
    )

    image = asyncio.run(client.get_post(7))

    assert image.id == 7
    assert image.url == "https://example.com/image.jpg"
    assert client._client.calls == 2
    assert sleep_calls == [0.1]
