import pytest

from smart_search import service


def test_minimum_profile_reports_missing_categories(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")

    result = service.validate_minimum_profile()

    assert result["ok"] is False
    assert set(result["missing"]) == {"main_search", "docs_search", "web_fetch"}
    assert "capability_status" in result


@pytest.mark.asyncio
async def test_mock_smoke_passes():
    result = await service.smoke("mock")

    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["failed_cases"] == []
    assert any(case["name"] == "docs_search fallback context7_to_exa" for case in result["cases"])
    assert any(case["name"] == "openai-compatible Responses mock protocol subset" for case in result["cases"])
    assert any(case["name"] == "deep_research explicit planner simple current prompt uses capability plan" for case in result["cases"])


@pytest.mark.asyncio
async def test_mock_smoke_covers_deep_research_capability_matrix():
    result = await service.smoke("mock")
    case_names = {case["name"] for case in result["cases"]}

    expected = {
        "deep_research explicit planner simple current prompt uses capability plan",
        "deep_research docs api prompt uses docs capabilities",
        "deep_research claim verification requires fetch_before_claim",
        "deep_research url prompt is fetch first",
        "deep_research normal search prompt does not trigger",
        "deep_research missing provider gives capability guidance",
        "deep_research fixed topic recipes are examples not schema",
    }
    assert expected <= case_names

    current_case = next(case for case in result["cases"] if case["name"] == "deep_research explicit planner simple current prompt uses capability plan")
    plan = current_case["research_plan"]
    assert plan["question"] == "深度搜索一下最近的比特币行情"
    assert plan["intent_signals"]["recency_requirement"] == "current"
    assert plan["intent_signals"]["claim_risk"] == "high"
    assert plan["trigger_source"] == "explicit_cli"
    assert plan["preflight"]["executed_by_deep_command"] is False
    assert plan["evidence_policy"] == "fetch_before_claim"
    assert {"intent_signals", "decomposition", "capability_plan", "gap_check", "usage_boundary"} <= set(plan)


@pytest.mark.asyncio
async def test_mock_smoke_does_not_depend_on_local_keys(monkeypatch):
    for key in service.config._CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")

    result = await service.smoke("mock")

    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["failed_cases"] == []
    assert any(case["name"] == "doctor minimum profile fails closed" for case in result["cases"])


@pytest.mark.asyncio
async def test_live_smoke_treats_provider_failure_as_degraded_when_fallback_exists(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")

    async def fake_doctor():
        return {
            "ok": True,
            "minimum_profile_ok": True,
            "error_type": "",
            "error": "",
            "capability_status": {
                "main_search": {"configured": ["xai-responses"], "fallback_chain": ["xai-responses", "openai-compatible"], "ok": True},
                "web_search": {"configured": ["zhipu", "tavily"], "fallback_chain": ["zhipu", "tavily", "firecrawl"], "ok": True},
                "docs_search": {"configured": ["context7"], "fallback_chain": ["context7", "exa"], "ok": True},
                "web_fetch": {"configured": ["tavily"], "fallback_chain": ["tavily", "firecrawl"], "ok": True},
            },
            "zhipu_connection_test": {"status": "warning", "message": "HTTP 429: Too Many Requests"},
            "context7_connection_test": {"status": "not_configured", "message": "CONTEXT7_API_KEY 未设置"},
        }

    async def fake_fetch(url):
        return {"ok": True, "url": url, "provider": "tavily", "content": "# Page", "provider_attempts": []}

    monkeypatch.setattr(service, "doctor", fake_doctor)
    monkeypatch.setattr(service, "fetch", fake_fetch)

    result = await service.smoke("live")

    assert result["ok"] is True
    assert result["status"] == "degraded"
    assert result["failed_cases"] == []
    assert result["degraded_cases"] == ["zhipu search"]
    assert "context7 library" in result["skipped_cases"]


@pytest.mark.asyncio
async def test_live_smoke_reports_skipped_optional_cases_without_failing(monkeypatch):
    async def fake_doctor():
        return {
            "ok": True,
            "minimum_profile_ok": True,
            "error_type": "",
            "error": "",
            "capability_status": {
                "main_search": {"configured": ["xai-responses"], "fallback_chain": ["xai-responses"], "ok": True},
                "web_search": {"configured": [], "fallback_chain": ["zhipu", "tavily", "firecrawl"], "ok": False},
                "docs_search": {"configured": [], "fallback_chain": ["context7", "exa"], "ok": False},
                "web_fetch": {"configured": [], "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"], "ok": False},
            },
            "zhipu_connection_test": {"status": "not_configured", "message": "missing"},
            "context7_connection_test": {"status": "not_configured", "message": "missing"},
        }

    monkeypatch.setattr(service, "doctor", fake_doctor)

    result = await service.smoke("live")

    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert result["failed_cases"] == []
    assert set(result["skipped_cases"]) == {"zhipu search", "context7 library", "web fetch fallback chain"}


@pytest.mark.asyncio
async def test_live_smoke_fails_when_configured_main_search_connection_fails(monkeypatch):
    async def fake_doctor():
        return {
            "ok": False,
            "minimum_profile_ok": True,
            "error_type": "network_error",
            "error": "main provider timed out",
            "primary_connection_test": {"status": "timeout", "message": "main provider timed out"},
            "capability_status": {
                "main_search": {"configured": ["openai-compatible"], "fallback_chain": ["openai-compatible"], "ok": True},
                "web_search": {"configured": [], "fallback_chain": [], "ok": False},
                "docs_search": {"configured": ["exa"], "fallback_chain": ["exa"], "ok": True},
                "web_fetch": {"configured": [], "fallback_chain": [], "ok": False},
            },
            "zhipu_connection_test": {"status": "not_configured", "message": "missing"},
            "context7_connection_test": {"status": "not_configured", "message": "missing"},
        }

    monkeypatch.setattr(service, "doctor", fake_doctor)

    result = await service.smoke("live")

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["failed_cases"] == ["main search connection"]


@pytest.mark.asyncio
async def test_live_smoke_accepts_a_main_search_fallback_connection(monkeypatch):
    async def fake_doctor():
        return {
            "ok": True,
            "minimum_profile_ok": True,
            "error_type": "",
            "error": "",
            "primary_connection_test": {"status": "timeout", "message": "primary provider timed out"},
            "main_search_connection_tests": {
                "xai-responses": {"status": "timeout", "message": "primary provider timed out"},
                "openai-compatible": {"status": "ok", "message": "fallback provider available"},
            },
            "capability_status": {
                "main_search": {"configured": ["xai-responses", "openai-compatible"], "fallback_chain": ["xai-responses", "openai-compatible"], "ok": True},
                "web_search": {"configured": [], "fallback_chain": [], "ok": False},
                "docs_search": {"configured": [], "fallback_chain": [], "ok": False},
                "web_fetch": {"configured": [], "fallback_chain": [], "ok": False},
            },
            "zhipu_connection_test": {"status": "not_configured", "message": "missing"},
            "context7_connection_test": {"status": "not_configured", "message": "missing"},
        }

    monkeypatch.setattr(service, "doctor", fake_doctor)

    result = await service.smoke("live")

    main_search_case = next(case for case in result["cases"] if case["name"] == "main search connection")
    assert result["ok"] is True
    assert result["status"] == "healthy"
    assert main_search_case["status"] == "ok"
    assert main_search_case["available_providers"] == ["openai-compatible"]


@pytest.mark.asyncio
async def test_live_smoke_reports_failed_status_for_critical_case(monkeypatch):
    async def fake_doctor():
        return {
            "ok": False,
            "minimum_profile_ok": False,
            "error_type": "config_error",
            "error": "missing web_fetch",
            "capability_status": {"web_fetch": {"configured": [], "fallback_chain": [], "ok": False}},
            "zhipu_connection_test": {"status": "not_configured", "message": "missing"},
            "context7_connection_test": {"status": "not_configured", "message": "missing"},
        }

    monkeypatch.setattr(service, "doctor", fake_doctor)

    result = await service.smoke("live")

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["failed_cases"] == ["doctor minimum profile"]


@pytest.mark.asyncio
async def test_fetch_attempts_show_fallback(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret")

    async def no_tavily(url):
        return None

    async def yes_firecrawl(url, ctx=None):
        return "# Page"

    monkeypatch.setattr(service, "call_tavily_extract", no_tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", yes_firecrawl)

    result = await service.fetch("https://example.com")

    assert result["ok"] is True
    assert result["provider"] == "firecrawl"
    assert result["fallback_used"] is True
    assert [a["provider"] for a in result["provider_attempts"]] == ["tavily", "firecrawl"]


@pytest.mark.asyncio
async def test_search_docs_intent_uses_docs_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    monkeypatch.setenv("CONTEXT7_API_KEY", "ctx-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Answer."

    async def fake_context7(name, query=""):
        return {"ok": True, "results": [{"id": "/reactjs/react.dev", "title": "React", "description": "UI"}], "total": 1}

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "context7_library", fake_context7)

    result = await service.search("React useEffect API docs", validation="balanced")

    assert result["ok"] is True
    assert result["routing_decision"]["docs_intent"] is True
    assert result["fallback_used"] is False
    assert "context7" in result["providers_used"]
    assert "exa" not in result["providers_used"]


@pytest.mark.asyncio
async def test_search_docs_intent_falls_back_to_exa_after_context7_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    monkeypatch.setenv("CONTEXT7_API_KEY", "ctx-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Answer."

    async def fake_context7(name, query=""):
        return {"ok": True, "results": [], "total": 0}

    async def fake_exa(*args, **kwargs):
        return {"ok": True, "results": [{"url": "https://docs.example.com", "title": "Docs"}]}

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "context7_library", fake_context7)
    monkeypatch.setattr(service, "exa_search", fake_exa)

    result = await service.search("React useEffect API docs", validation="balanced")

    assert result["ok"] is True
    assert result["fallback_used"] is True
    providers = [attempt["provider"] for attempt in result["provider_attempts"] if attempt["capability"] == "docs_search"]
    assert providers == ["context7", "exa"]
    assert "exa" in result["providers_used"]


@pytest.mark.asyncio
async def test_search_zh_current_uses_zhipu_reinforcement(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Answer."

    async def fake_zhipu(query, count=10, **kwargs):
        return {
            "ok": True,
            "results": [{"url": "https://example.com/news", "title": "News", "provider": "zhipu"}],
            "total": 1,
        }

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "zhipu_search", fake_zhipu)

    result = await service.search("今天国内 AI 新闻", validation="balanced")

    assert result["ok"] is True
    assert result["routing_decision"]["zh_current_intent"] is True
    assert "zhipu" in result["providers_used"]
