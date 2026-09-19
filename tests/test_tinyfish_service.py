import pytest

from smart_search import service


@pytest.mark.asyncio
async def test_fetch_uses_tinyfish_when_it_is_the_only_configured_fetch_provider(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    async def yes_tinyfish(url):
        return {"ok": True, "provider": "tinyfish", "url": url, "content": "# TinyFish Page"}

    monkeypatch.setattr(service, "call_tinyfish_fetch", yes_tinyfish)

    result = await service.fetch("https://example.com")

    assert result["ok"] is True
    assert result["provider"] == "tinyfish"
    assert result["content"] == "# TinyFish Page"
    assert [attempt["provider"] for attempt in result["provider_attempts"]] == ["tinyfish"]


@pytest.mark.asyncio
async def test_fetch_falls_back_to_tinyfish_after_earlier_providers_fail(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    async def no_tavily(url):
        return None

    async def yes_tinyfish(url):
        return {"ok": True, "provider": "tinyfish", "url": url, "content": "# Page"}

    monkeypatch.setattr(service, "call_tavily_extract", no_tavily)
    monkeypatch.setattr(service, "call_tinyfish_fetch", yes_tinyfish)

    result = await service.fetch("https://example.com")

    assert result["provider"] == "tinyfish"
    assert [attempt["provider"] for attempt in result["provider_attempts"]] == ["tavily", "tinyfish"]
    assert result["fallback_used"] is True


@pytest.mark.asyncio
async def test_fetch_reports_tinyfish_error_type_when_the_whole_chain_fails(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    async def failing_tinyfish(url):
        return {"ok": False, "provider": "tinyfish", "error_type": "rate_limited", "error": "quota exhausted"}

    monkeypatch.setattr(service, "call_tinyfish_fetch", failing_tinyfish)

    result = await service.fetch("https://example.com")

    assert result["ok"] is False
    assert result["error_type"] == "rate_limited"
    assert "quota exhausted" in result["error"]


@pytest.mark.asyncio
async def test_web_search_fallback_accepts_tinyfish_candidates(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    async def yes_tinyfish(query, count=5):
        return [{"title": "T", "url": "https://tiny.example.com", "description": "d", "provider": "tinyfish"}]

    monkeypatch.setattr(service, "call_tinyfish_search", yes_tinyfish)

    sources, attempts = await service._run_web_search_fallback("example query", count=3)

    assert [source["url"] for source in sources] == ["https://tiny.example.com"]
    assert sources[0]["provider"] == "tinyfish"
    assert [attempt["provider"] for attempt in attempts] == ["tinyfish"]
    assert attempts[0]["status"] == "ok"


@pytest.mark.asyncio
async def test_web_search_prefers_tavily_over_tinyfish(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    async def yes_tavily(query, max_results=6):
        return [{"title": "Tavily", "url": "https://tavily.example.com", "content": "c"}]

    async def unexpected_tinyfish(query, count=5):
        raise AssertionError("TinyFish must not run once Tavily answered")

    monkeypatch.setattr(service, "call_tavily_search", yes_tavily)
    monkeypatch.setattr(service, "call_tinyfish_search", unexpected_tinyfish)

    sources, attempts = await service._run_web_search_fallback("q", count=2)

    assert sources[0]["provider"] == "tavily"
    assert [attempt["provider"] for attempt in attempts] == ["tavily"]


def test_tinyfish_is_registered_as_an_optional_two_capability_provider():
    profiles = service.provider_profiles()

    assert profiles["tinyfish"]["capability"] == "web_search"
    assert set(profiles["tinyfish"]["capabilities"]) == {"web_search", "web_fetch"}
    assert profiles["tinyfish"]["minimum_profile_role"] == ""
    assert "challenge page rejection" in profiles["tinyfish"]["quality_filters"]


def test_tinyfish_joins_both_fallback_chains_after_the_established_providers(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    status = service.get_capability_status()

    assert status["web_search"]["fallback_chain"] == ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish"]
    assert status["web_fetch"]["fallback_chain"] == ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish"]
    assert status["web_search"]["configured"] == ["tinyfish"]
    assert status["web_fetch"]["configured"] == ["tinyfish"]


def test_tinyfish_never_satisfies_main_search_or_docs_search(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")

    result = service.validate_minimum_profile()

    # TinyFish is registered for web_search and web_fetch only; a search/fetch key
    # must never be mistaken for a synthesis or docs provider.
    assert result["ok"] is False
    assert set(result["missing"]) == {"main_search", "docs_search"}
    assert result["capability_status"]["main_search"]["configured"] == []
    assert result["capability_status"]["docs_search"]["configured"] == []
    assert result["capability_status"]["web_fetch"]["configured"] == ["tinyfish"]


def test_tinyfish_credential_fingerprint_tracks_the_api_key(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "first-key")
    first = service._provider_fingerprint("tinyfish")

    monkeypatch.setenv("TINYFISH_API_KEY", "second-key")
    second = service._provider_fingerprint("tinyfish")

    assert first and second and first != second


@pytest.mark.asyncio
async def test_correcting_fetch_endpoint_retries_after_auth_cooldown(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")
    monkeypatch.setenv("TINYFISH_FETCH_API_URL", "https://wrong.example/fetch")
    calls = []

    async def fetch_from_configured_endpoint(url):
        endpoint = service.config.tinyfish_fetch_api_url
        calls.append(endpoint)
        if endpoint == "https://wrong.example/fetch":
            return {"ok": False, "error_type": "auth_error", "error": "wrong endpoint"}
        return {"ok": True, "content": "Recovered page"}

    monkeypatch.setattr(service, "call_tinyfish_fetch", fetch_from_configured_endpoint)

    failed = await service.fetch("https://example.com")
    assert failed["ok"] is False
    assert service._provider_health_status("tinyfish")["state"] == "cooldown"
    await service.fetch("https://example.com")
    assert calls == ["https://wrong.example/fetch"]

    monkeypatch.setenv("TINYFISH_FETCH_API_URL", "https://fixed.example/fetch")
    recovered = await service.fetch("https://example.com")

    assert recovered["ok"] is True
    assert recovered["content"] == "Recovered page"
    assert calls == ["https://wrong.example/fetch", "https://fixed.example/fetch"]
    assert service._provider_health_status("tinyfish")["state"] == "closed"


@pytest.mark.asyncio
async def test_research_route_keeps_tinyfish_after_firecrawl(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-secret")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret")

    async def firecrawl_sources(query, max_results=6):
        return [{"url": "https://example.com/evidence", "description": "Evidence"}]

    monkeypatch.setattr(service, "call_firecrawl_search", firecrawl_sources)
    routes = service._research_capability_routes("history of printing", {}, "auto")
    providers = routes["capabilities"]["web_search"]["providers"]
    sources, attempts = await service._run_web_search_fallback(
        "history of printing", providers=",".join(providers), fallback="off"
    )

    assert providers == ["firecrawl", "tinyfish"]
    assert sources[0]["provider"] == providers[0]
    assert [attempt["provider"] for attempt in attempts] == [providers[0]]
