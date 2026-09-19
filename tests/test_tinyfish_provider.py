import json

import httpx
import pytest

from smart_search.providers.tinyfish import TinyFishFetchProvider, TinyFishSearchProvider


class FakeTinyFishClient:
    calls = []
    get_response: httpx.Response | None = None
    post_response: httpx.Response | None = None
    exception: Exception | None = None

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers, params=None):
        self.__class__.calls.append({"method": "GET", "url": url, "headers": headers, "params": params})
        if self.__class__.exception:
            raise self.__class__.exception
        return self.__class__.get_response

    async def post(self, url, headers, json):
        self.__class__.calls.append({"method": "POST", "url": url, "headers": headers, "json": json})
        if self.__class__.exception:
            raise self.__class__.exception
        return self.__class__.post_response


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakeTinyFishClient.calls = []
    FakeTinyFishClient.get_response = None
    FakeTinyFishClient.post_response = None
    FakeTinyFishClient.exception = None


def _monkeypatch_client(monkeypatch):
    monkeypatch.setattr("smart_search.providers.tinyfish.httpx.AsyncClient", FakeTinyFishClient)


def _search_response(payload, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("GET", "https://api.search.tinyfish.ai"))


def _fetch_response(payload, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", "https://api.fetch.tinyfish.ai"))


@pytest.mark.asyncio
async def test_search_sends_api_key_header_and_normalizes_results(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.get_response = _search_response(
        {
            "query": "react hooks",
            "results": [
                {
                    "position": 1,
                    "site_name": "react.dev",
                    "snippet": "Hooks let you use state.",
                    "title": "Rules of Hooks",
                    "url": "https://react.dev/reference/rules",
                    "date": "2026-05-01",
                }
            ],
            "total_results": 1,
        }
    )
    provider = TinyFishSearchProvider("https://api.search.tinyfish.ai", "tf-secret")

    data = json.loads(await provider.search("react hooks", max_results=5))

    assert data["ok"] is True
    assert data["results"][0] == {
        "title": "Rules of Hooks",
        "url": "https://react.dev/reference/rules",
        "description": "Hooks let you use state.",
        "provider": "tinyfish",
        "source": "react.dev",
        "published_date": "2026-05-01",
    }
    call = FakeTinyFishClient.calls[0]
    assert call["headers"]["X-API-Key"] == "tf-secret"
    assert call["params"] == {"query": "react hooks"}
    assert call["url"] == "https://api.search.tinyfish.ai"


@pytest.mark.asyncio
async def test_search_truncates_to_max_results(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.get_response = _search_response(
        {
            "results": [
                {"title": f"T{index}", "url": f"https://example.com/{index}", "snippet": "s"}
                for index in range(4)
            ]
        }
    )
    provider = TinyFishSearchProvider("https://api.search.tinyfish.ai", "key")

    data = json.loads(await provider.search("x", max_results=2))

    assert [item["url"] for item in data["results"]] == ["https://example.com/0", "https://example.com/1"]


@pytest.mark.asyncio
async def test_fetch_posts_markdown_request_and_returns_content(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.post_response = _fetch_response(
        {
            "results": [
                {
                    "url": "https://example.com",
                    "final_url": "https://example.com/",
                    "title": "Example",
                    "published_date": "2026-01-02",
                    "format": "markdown",
                    "text": "# Example\n\nBody",
                }
            ],
            "errors": [],
        }
    )
    provider = TinyFishFetchProvider("https://api.fetch.tinyfish.ai", "tf-secret")

    data = json.loads(await provider.fetch("https://example.com"))

    assert data["ok"] is True
    assert data["content"] == "# Example\n\nBody"
    assert data["final_url"] == "https://example.com/"
    assert data["title"] == "Example"
    call = FakeTinyFishClient.calls[0]
    assert call["json"] == {"urls": ["https://example.com"], "format": "markdown"}
    assert call["headers"]["X-API-Key"] == "tf-secret"


@pytest.mark.asyncio
async def test_fetch_reports_per_url_errors_as_provider_error(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.post_response = _fetch_response(
        {"results": [], "errors": [{"url": "https://gone.example.com", "error": "upstream returned 404"}]}
    )
    provider = TinyFishFetchProvider("https://api.fetch.tinyfish.ai", "key")

    data = json.loads(await provider.fetch("https://gone.example.com"))

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert "404" in data["error"]


@pytest.mark.asyncio
async def test_fetch_flags_a_challenge_page_as_quality_error(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.post_response = _fetch_response(
        {
            "results": [
                {
                    "url": "https://protected.example.com",
                    "format": "markdown",
                    "text": "Title: Just a moment Checking if the site connection is secure",
                }
            ],
            "errors": [],
        }
    )
    provider = TinyFishFetchProvider("https://api.fetch.tinyfish.ai", "key")

    data = json.loads(await provider.fetch("https://protected.example.com"))

    assert data["ok"] is False
    assert data["error_type"] == "quality_error"


@pytest.mark.asyncio
async def test_search_and_fetch_without_key_return_config_error_without_a_request(monkeypatch):
    _monkeypatch_client(monkeypatch)

    search_data = json.loads(await TinyFishSearchProvider("https://api.search.tinyfish.ai", "").search("x"))
    fetch_data = json.loads(await TinyFishFetchProvider("https://api.fetch.tinyfish.ai", "").fetch("https://example.com"))

    assert search_data["error_type"] == "config_error"
    assert fetch_data["error_type"] == "config_error"
    assert FakeTinyFishClient.calls == []


@pytest.mark.asyncio
async def test_search_classifies_auth_failures_without_leaking_the_key(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.get_response = httpx.Response(
        401,
        json={"error": {"message": "invalid api key tf-secret"}},
        request=httpx.Request("GET", "https://api.search.tinyfish.ai"),
    )
    provider = TinyFishSearchProvider("https://api.search.tinyfish.ai", "tf-secret")

    data = json.loads(await provider.search("x"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "tf-secret" not in data["error"]


@pytest.mark.asyncio
async def test_search_rejects_a_payload_without_results(monkeypatch):
    _monkeypatch_client(monkeypatch)
    FakeTinyFishClient.get_response = _search_response({"query": "x"})
    provider = TinyFishSearchProvider("https://api.search.tinyfish.ai", "key")

    data = json.loads(await provider.search("x"))

    assert data["ok"] is False
    assert data["error_type"] == "parse_error"

