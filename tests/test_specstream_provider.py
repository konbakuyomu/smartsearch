from __future__ import annotations

import json
import time
from dataclasses import replace

import httpx
import pytest

from smart_search import jev_search, service
from smart_search.jev import JevClient
from smart_search.providers.specstream import SpecStreamFetchProvider, SpecStreamSearchProvider

SEARCH_URL = "https://api.specstream.ai/v1/web-search"
FETCH_URL = "https://api.specstream.ai/v1/extract"
KEY = "ss-synthetic-secret-key-0123"


class FakeSpecStreamClient:
    """Answer by endpoint URL and record each client's options and request."""

    options: list[dict] = []
    calls: list[dict] = []
    responses: dict[str, object] = {}

    def __init__(self, **kwargs):
        self.__class__.options.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, headers=None, json=None):
        self.__class__.calls.append({"url": url, "headers": headers, "json": json})
        answer = self.__class__.responses[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def fake_client(monkeypatch):
    FakeSpecStreamClient.options = []
    FakeSpecStreamClient.calls = []
    FakeSpecStreamClient.responses = {}
    monkeypatch.setattr("smart_search.providers.specstream.httpx.AsyncClient", FakeSpecStreamClient)
    return FakeSpecStreamClient


def _response(url, payload=None, status=200, *, content=None, headers=None):
    request = httpx.Request("POST", url)
    if content is not None:
        return httpx.Response(status, content=content, headers=headers, request=request)
    return httpx.Response(status, json=payload, headers=headers, request=request)


def _search_ok():
    return _response(SEARCH_URL, {"sources": [{"title": "Example", "url": "https://example.com/a", "excerpt": "Excerpt"}]})


def _fetch_ok(**item):
    return _response(FETCH_URL, {"results": [{"url": "https://example.com", "ok": True, "markdown": "# Example Domain", **item}]})


async def _run(operation):
    if operation == "search":
        raw = await SpecStreamSearchProvider(SEARCH_URL, KEY).search("query", max_results=3)
    else:
        raw = await SpecStreamFetchProvider(FETCH_URL, KEY).fetch("https://example.com/page")
    return json.loads(raw)


def _endpoint(operation):
    return SEARCH_URL if operation == "search" else FETCH_URL


@pytest.mark.asyncio
async def test_specstream_search_provider_normalizes_sources(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "sources": [
                        {
                            "title": "Example Docs",
                            "url": "https://example.com/docs",
                            "snippet": "Short snippet",
                            "excerpt": "Verified excerpt text",
                            "source": "example.com",
                            "published": "2026-11-20",
                        }
                    ]
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = SpecStreamSearchProvider("https://api.specstream.ai/v1/web-search", "ss-secret", 30.0)
    raw = await provider.search("example docs", max_results=4)
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["provider"] == "specstream"
    assert captured["headers"]["Authorization"] == "Bearer ss-secret"
    assert captured["json"] == {"q": "example docs", "num": 4, "passages": True}
    assert len(data["results"]) == 1
    assert data["results"][0]["description"] == "Verified excerpt text"
    assert data["results"][0]["source"] == "example.com"


@pytest.mark.asyncio
async def test_specstream_fetch_provider_extracts_content(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "results": [
                        {
                            "url": "https://example.com/article",
                            "ok": True,
                            "title": "Article",
                            "text": "Clean page content.",
                        }
                    ]
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = SpecStreamFetchProvider("https://api.specstream.ai/v1/extract", "ss-secret", 30.0)
    raw = await provider.fetch("https://example.com/article")
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["provider"] == "specstream"
    assert data["title"] == "Article"
    assert data["content"] == "Clean page content."
    assert captured["json"] == {"urls": ["https://example.com/article"]}


@pytest.mark.asyncio
async def test_service_fetch_uses_specstream_when_only_configured_provider(monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "ss-secret")
    for k in ("TAVILY_API_KEY", "JINA_API_KEY", "ZHIPU_MCP_API_KEY", "FIRECRAWL_API_KEY", "TINYFISH_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    async def yes_specstream(url):
        return {"ok": True, "provider": "specstream", "url": url, "content": "# SpecStream Page"}

    monkeypatch.setattr(service, "call_specstream_fetch", yes_specstream)
    result = await service.fetch("https://example.com")
    assert result["ok"] is True
    assert result["provider"] == "specstream"
    assert result["content"] == "# SpecStream Page"


# ---- provider failure semantics -------------------------------------------


@pytest.mark.asyncio
async def test_missing_key_is_a_config_error_without_a_request(fake_client):
    search = json.loads(await SpecStreamSearchProvider(SEARCH_URL, "").search("query"))
    fetch = json.loads(await SpecStreamFetchProvider(FETCH_URL, "").fetch("https://example.com"))

    assert search["ok"] is False and search["error_type"] == "config_error"
    assert fetch["ok"] is False and fetch["error_type"] == "config_error"
    assert await service.call_specstream_search("query") is None
    assert (await service.call_specstream_fetch("https://example.com"))["error_type"] == "config_error"
    assert fake_client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["search", "fetch"])
@pytest.mark.parametrize("status,expected", [
    (401, "auth_error"), (403, "auth_error"), (429, "rate_limited"), (500, "network_error"), (503, "network_error"),
])
async def test_http_failures_are_classified_without_leaking_the_key(fake_client, operation, status, expected):
    fake_client.responses[_endpoint(operation)] = _response(
        _endpoint(operation), {"error": f"rejected Authorization: Bearer {KEY} (api_key={KEY})"}, status)

    data = await _run(operation)

    assert data["ok"] is False
    assert data["error_type"] == expected
    assert f"HTTP {status}" in data["error"]
    assert KEY not in json.dumps(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["search", "fetch"])
async def test_timeout_is_classified(fake_client, operation):
    fake_client.responses[_endpoint(operation)] = httpx.ReadTimeout("read timed out")

    data = await _run(operation)

    assert data["ok"] is False and data["error_type"] == "timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["search", "fetch"])
@pytest.mark.parametrize("body", [{"content": b"<html>not json</html>"}, {"payload": ["not", "an", "object"]}])
async def test_invalid_json_or_non_object_is_a_parse_error(fake_client, operation, body):
    fake_client.responses[_endpoint(operation)] = _response(_endpoint(operation), **body)

    data = await _run(operation)

    assert data["ok"] is False and data["error_type"] == "parse_error"


@pytest.mark.asyncio
async def test_extract_item_failure_is_a_redacted_provider_error(fake_client):
    fake_client.responses[FETCH_URL] = _response(FETCH_URL, {"results": [
        {"url": "https://example.com/page", "ok": False, "error": f"target refused the request for key {KEY}"},
    ]})

    data = await _run("fetch")

    assert data["ok"] is False and data["error_type"] == "provider_error"
    assert "target refused the request" in data["error"]
    assert KEY not in json.dumps(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"results": []},
    {"results": [{"url": "https://example.com/page", "ok": True, "markdown": "   ", "text": ""}]},
])
async def test_empty_extract_is_a_provider_error(fake_client, payload):
    fake_client.responses[FETCH_URL] = _response(FETCH_URL, payload)

    data = await _run("fetch")

    assert data["ok"] is False and data["error_type"] == "provider_error"


@pytest.mark.asyncio
async def test_extract_prefers_markdown_and_flags_challenge_pages(fake_client):
    fake_client.responses[FETCH_URL] = _fetch_ok(text="plain text")
    assert (await _run("fetch"))["content"] == "# Example Domain"

    fake_client.responses[FETCH_URL] = _fetch_ok(markdown="Checking if the site connection is secure")
    data = await _run("fetch")

    assert data["ok"] is False
    assert data["error_type"] == "quality_error"
    assert "checking if the site connection is secure" in data["error"]


# ---- transport: redirects and TLS -------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["search", "fetch"])
async def test_redirect_is_reported_not_followed(fake_client, operation):
    fake_client.responses[_endpoint(operation)] = _response(
        _endpoint(operation), {}, 302, headers={"location": "https://elsewhere.example/collect"})

    data = await _run(operation)

    assert data["ok"] is False and data["error_type"] == "provider_error"
    assert "redirect" in data["error"] and "https://elsewhere.example/collect" in data["error"]
    assert len(fake_client.calls) == 1
    assert fake_client.options[-1]["follow_redirects"] is False


@pytest.mark.asyncio
async def test_a_real_client_does_not_send_the_key_to_the_redirect_target(monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.specstream.ai":
            return httpx.Response(307, headers={"location": "https://elsewhere.example/collect"})
        return httpx.Response(200, json={"sources": []})

    real_client = httpx.AsyncClient
    monkeypatch.setattr("smart_search.providers.specstream.httpx.AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))

    data = json.loads(await SpecStreamSearchProvider(SEARCH_URL, KEY).search("query"))

    assert data["ok"] is False and data["error_type"] == "provider_error"
    assert seen == [("api.specstream.ai", f"Bearer {KEY}")]


@pytest.mark.asyncio
async def test_ssl_verify_reaches_both_clients(fake_client, monkeypatch):
    fake_client.responses[SEARCH_URL] = _search_ok()
    fake_client.responses[FETCH_URL] = _fetch_ok()
    await SpecStreamSearchProvider(SEARCH_URL, KEY).search("query")
    assert fake_client.options[-1]["verify"] is True

    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    monkeypatch.setenv("SSL_VERIFY", "false")
    await service.call_specstream_search("query")
    await service.call_specstream_fetch("https://example.com")

    assert [options["verify"] for options in fake_client.options[1:]] == [False, False]


# ---- configuration, enablement, routing order ---------------------------------


def test_config_keys_are_writable_and_the_key_is_masked(monkeypatch):
    result = service.config.update_config_values({
        "SPECSTREAM_API_KEY": KEY,
        "SPECSTREAM_SEARCH_API_URL": "https://specstream.example/v1/web-search",
        "SPECSTREAM_FETCH_API_URL": "https://specstream.example/v1/extract",
        "SPECSTREAM_TIMEOUT_SECONDS": "12",
    })

    assert result["ok"], result
    assert service.config.specstream_timeout == 12.0
    assert service.config.specstream_fetch_api_url == "https://specstream.example/v1/extract"
    info = service.config.get_config_info()
    assert info["SPECSTREAM_API_KEY"] != KEY and KEY not in json.dumps(info, default=str)


@pytest.mark.parametrize("value", ["nonsense", "nan", "inf", "0", "-1"])
def test_timeout_rejects_invalid_writes(value):
    with pytest.raises(ValueError):
        service.config._validate_config_value("SPECSTREAM_TIMEOUT_SECONDS", value)


@pytest.mark.asyncio
async def test_disabled_switch_stops_every_request(fake_client, monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    monkeypatch.setenv("SPECSTREAM_ENABLED", "false")

    assert "specstream" not in service.get_capability_status()["web_search"]["configured"]
    assert "specstream" not in service.get_capability_status()["web_fetch"]["configured"]
    assert all(item["provider"] != "specstream" for item in jev_search.available_channels(service, "read https://example.com", []))
    assert await service.call_specstream_search("query") is None
    fetched = await service.call_specstream_fetch("https://example.com")
    assert fetched["disabled"] is True and fetched["error_type"] == "config_error"
    probe = await service.test_provider_connection("specstream")
    assert probe["status"] == "disabled"
    assert fake_client.calls == []


def test_profile_is_experimental():
    assert service.provider_profiles()["specstream"]["experimental"] is True


def _configure_every_web_provider(monkeypatch):
    for key in ("ZHIPU_API_KEY", "ZHIPU_MCP_API_KEY", "TAVILY_API_KEY", "JINA_API_KEY", "FIRECRAWL_API_KEY",
                "TINYFISH_API_KEY", "DEEPSEEK_API_KEY", "YUANBAO_SECRET_ID", "YUANBAO_SECRET_KEY", "SPECSTREAM_API_KEY"):
        monkeypatch.setenv(key, "synthetic-key")


def test_declared_and_actual_web_search_order_agree_and_end_with_specstream(monkeypatch):
    _configure_every_web_provider(monkeypatch)
    status = service.get_capability_status()
    chain = status["web_search"]["fallback_chain"]

    assert chain[-1] == "specstream"
    assert status["web_search"]["configured"] == chain
    assert status["web_fetch"]["configured"] == status["web_fetch"]["fallback_chain"]
    # Local rule routing stable-sorts candidates by PROVIDER_PROFILES insertion order.
    profile_order = [provider for provider, profile in service.PROVIDER_PROFILES.items()
                     if "web_search" in (profile.get("capabilities") or [profile["capability"]])]
    assert profile_order == chain
    query = "latest news today"
    candidates = jev_search.available_channels(service, query, [])
    selected = jev_search.fallback_channels(service, query, candidates, len(candidates))
    assert [item["provider"] for item in selected if item["capability"] == "web_search"] == chain


@pytest.mark.asyncio
async def test_fetch_fallback_tries_specstream_last(monkeypatch):
    _configure_every_web_provider(monkeypatch)

    async def nothing(url, *args, **kwargs):
        return None

    async def not_ok(url, *args, **kwargs):
        return {"ok": False}

    async def specstream(url):
        return {"ok": True, "provider": "specstream", "url": url, "content": "Page text"}

    for name in ("call_tavily_extract", "call_firecrawl_scrape", "call_deepseek_fetch"):
        monkeypatch.setattr(service, name, nothing)
    for name in ("jina_fetch", "zhipu_mcp_reader", "call_tinyfish_fetch"):
        monkeypatch.setattr(service, name, not_ok)
    monkeypatch.setattr(service, "call_specstream_fetch", specstream)

    result = await service.fetch("https://example.com/page")

    assert result["provider"] == "specstream"
    assert [attempt["provider"] for attempt in result["provider_attempts"]] == \
        service.get_capability_status()["web_fetch"]["fallback_chain"]
    assert service._research_fetch_order("summarize this page", "https://example.com/page")[-1] == "specstream"


# ---- probe, doctor and Jev dispatch -------------------------------------------


@pytest.mark.asyncio
async def test_probe_checks_search_and_fetch(fake_client, monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    fake_client.responses[SEARCH_URL] = _search_ok()
    fake_client.responses[FETCH_URL] = _fetch_ok()

    passed = await service.test_provider_connection("specstream")

    assert passed["ok"] is True and passed["probe"] == "live"
    assert sorted(call["url"] for call in fake_client.calls) == [FETCH_URL, SEARCH_URL]

    fake_client.responses[FETCH_URL] = _response(FETCH_URL, {"error": f"bad key {KEY}"}, 403)
    failed = await service.test_provider_connection("specstream")
    assert failed["status"] == "auth_error"
    assert "fetch" in failed["message"] and KEY not in json.dumps(failed)

    fake_client.responses[FETCH_URL] = _fetch_ok()
    fake_client.responses[SEARCH_URL] = _response(SEARCH_URL, {"error": "slow down"}, 429)
    assert (await service.test_provider_connection("specstream"))["status"] == "rate_limited"


@pytest.mark.asyncio
async def test_search_success_cannot_clear_a_fetch_failure(fake_client, monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    fake_client.responses[SEARCH_URL] = _search_ok()
    fake_client.responses[FETCH_URL] = _response(FETCH_URL, {"error": "fetch endpoint rejected the key"}, 401)

    assert not (await service.test_provider_connection("specstream", record_health=True))["ok"]
    assert service._provider_health_status("specstream")["state"] == "cooldown"

    fake_client.responses[FETCH_URL] = _fetch_ok()
    assert (await service.test_provider_connection("specstream", record_health=True))["ok"]
    assert service._provider_health_status("specstream")["state"] == "closed"


@pytest.mark.asyncio
async def test_doctor_runs_the_probe_and_counts_it_as_retrieval(fake_client, monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    fake_client.responses[SEARCH_URL] = _search_ok()
    fake_client.responses[FETCH_URL] = _fetch_ok()

    info = await service.doctor()

    assert info["specstream_connection_test"]["status"] == "ok"
    assert sorted(call["url"] for call in fake_client.calls) == [FETCH_URL, SEARCH_URL]
    assert info["retrieval_connection_verified"] is True

    async def times_out():
        raise httpx.ReadTimeout("probe timed out")

    monkeypatch.setattr(service, "_test_specstream_connection", times_out)
    assert (await service.doctor())["specstream_connection_test"]["status"] == "timeout"


@pytest.mark.asyncio
async def test_channel_executor_dispatches_search_and_fetch(monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", KEY)
    searches, fetches = [], []

    async def search(query, max_results=6):
        searches.append((query, max_results))
        return [{"title": "Doc", "url": "https://example.com/doc", "description": "Excerpt", "provider": "specstream"}]

    async def fetch(url):
        fetches.append(url)
        return {"ok": True, "provider": "specstream", "url": url, "content": "Full page text"}

    monkeypatch.setattr(service, "call_specstream_search", search)
    monkeypatch.setattr(service, "call_specstream_fetch", fetch)
    query = "read https://example.com/doc"
    channels = {item["operation"]: item for item in jev_search.available_channels(service, query, [])
                if item["provider"] == "specstream"}
    assert set(channels) == {"search", "fetch"}
    assert "verified" not in channels["search"]["guidance"].lower()
    client = JevClient(replace(service.config.jev_settings(), api_key=""), time.monotonic() + 30)
    executor = jev_search.ChannelExecutor(service, client, count=3)

    found = await executor.execute(channels["search"], "example docs")
    read = await executor.execute(channels["fetch"], query)

    assert searches == [("example docs", 3)]
    assert found[0]["provider"] == "specstream" and found[0]["read"] is False and found[0]["content"] == "Excerpt"
    assert fetches == ["https://example.com/doc"]
    assert read[0]["provider"] == "specstream" and read[0]["read"] is True and read[0]["content"] == "Full page text"
