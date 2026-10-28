import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from smart_search import cli, service
from smart_search.jev import JevClient
from smart_search.jev_search import ChannelExecutor, FALLBACK_RESERVE_RATIO
from smart_search.provider_errors import ProviderCallError


def response(questions, values):
    return {"answers": {key: {"type": "noul", "noul": values.get(key, 0.01)} for key in questions}}


def configure_exa(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-test")

    async def search(*args, **kwargs):
        return {"ok": True, "results": [{"url": "https://example.org/source", "content": "Retrieved result"}]}

    monkeypatch.setattr(service, "exa_search", search)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["jev", "hybrid"])
async def test_ordinary_search_has_one_judgment_and_ignores_research_options(monkeypatch, mode):
    configure_exa(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", mode)
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("SMART_SEARCH_JEV_MAX_ROUNDS", "10")
    monkeypatch.setenv("SMART_SEARCH_JEV_MAX_CHANNELS", "10")
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    calls = []

    async def judge(self, state, questions, timeout):
        assert "available_channels" in state, "ordinary search must not assess, filter, or synthesize"
        calls.append(state)
        return response(questions, {f"channel_{i}": 0.99 for i in range(len(state["available_channels"]))})

    monkeypatch.setattr(JevClient, "_request", judge)
    result = await service.search("Find this source", validation="strict", extra_sources=2)

    assert result["ok"]
    assert len(calls) == 1
    assert len(result["provider_attempts"]) == 1
    assert result["routing_decision"]["stop_reason"] == "single_pass"
    assert result["evidence_assessment"]["status"] == "not_evaluated"
    assert result["evidence_assessment"]["sufficient"] is None
    assert result["result_filter"]["enabled"] is False
    assert result["synthesis"]["status"] == "disabled"
    assert result["timeout_seconds"] == 300


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["local", "rules", "off"])
async def test_local_aliases_never_call_jev_even_when_key_exists(monkeypatch, mode):
    configure_exa(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", mode)
    monkeypatch.setenv("TYPESAFE_API_KEY", "unused-jev-key")
    monkeypatch.setenv("INTENT_EMBEDDING_API_KEY", "unused-embedding-key")
    monkeypatch.setenv("INTENT_CLASSIFIER_API_KEY", "unused-classifier-key")

    async def forbidden(*args, **kwargs):
        raise AssertionError("local mode must not use a remote router")

    monkeypatch.setattr(JevClient, "_request", forbidden)
    result = await service.search("Find this source", fallback="off")

    assert result["ok"]
    assert result["jev_calls"] == []
    assert result["routing_decision"]["intent_router_mode"] == "local"
    assert not result["degraded"]


@pytest.mark.asyncio
async def test_missing_jev_uses_local_retrieval_unless_fallback_is_off(monkeypatch):
    configure_exa(monkeypatch)
    result = await service.search("Find this source")
    assert result["ok"]
    assert result["degraded"]
    assert result["jev_calls"] == []
    refused = await service.search("Find this source", fallback="off")
    assert not refused["ok"]
    assert refused["error_type"] == "config_error"


@pytest.mark.asyncio
async def test_context7_ordinary_search_selects_library_locally(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-test")
    calls = []

    async def judge(self, state, questions, timeout):
        assert "available_channels" in state, "no second Jev library selection"
        calls.append(state)
        return response(questions, {"channel_0": 0.99})

    async def library(*args, **kwargs):
        return {"ok": True, "results": [{"id": "/websites/react_dev", "title": "React", "description": "React documentation"}]}

    async def docs(library_id, query):
        assert library_id == "/websites/react_dev"
        return {"ok": True, "content": "useEffect cleanup documentation"}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "context7_library", library)
    monkeypatch.setattr(service, "context7_docs", docs)
    result = await service.search("React useEffect API docs")
    assert result["ok"]
    assert len(calls) == 1
    assert "cleanup documentation" in result["content"]


@pytest.mark.asyncio
async def test_research_reads_discovered_source_before_citing(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test")
    operations = []

    async def judge(self, state, questions, timeout):
        if "available_channels" in state:
            scores = {f"channel_{i}": 0.99 if (item["operation"] == "fetch" if operations else item["id"] == "tavily:search") else 0.01
                      for i, item in enumerate(state["available_channels"])}
        else:
            read = "fetch" in operations
            scores = {"useful": 0.99 if read else 0.1, "sufficient": 0.99 if read else 0.1}
        return response(questions, scores)

    async def search(*args, **kwargs):
        operations.append("search")
        return [{"url": "https://example.org/source", "content": "Discovery snippet"}]

    async def fetch(url):
        operations.append("fetch")
        return "Actual fetched primary source text"

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "call_tavily_search", search)
    monkeypatch.setattr(service, "call_tavily_extract", fetch)
    result = await service.research("Find evidence", evidence_dir=str(tmp_path / "evidence"))

    assert result["ok"]
    assert operations == ["search", "fetch"]
    assert result["gap_check"]["status"] == "closed"
    assert len(result["citations"]) == 1
    assert "Actual fetched" in result["content"]
    assert "Discovery snippet" not in result["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["auto", "off"])
async def test_empty_ordinary_channel_uses_only_same_capability_fallback(monkeypatch, fallback):
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-test")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")
    judgments, retrievals = [], []

    async def judge(self, state, questions, timeout):
        judgments.append(state)
        return response(questions, {f"channel_{i}": 0.99 if item["provider"] == "context7" else 0.01
                                   for i, item in enumerate(state["available_channels"])})

    async def library(*args, **kwargs):
        retrievals.append("context7")
        return {"ok": True, "results": []}

    async def exa(*args, **kwargs):
        retrievals.append("exa")
        return {"ok": True, "results": [{"url": "https://example.org/docs", "content": "Documentation"}]}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "context7_library", library)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("React API docs", fallback=fallback)
    assert len(judgments) == 1
    assert retrievals == (["context7", "exa"] if fallback == "auto" else ["context7"])
    assert result["ok"] == (fallback == "auto")
    assert {item["capability"] for item in result["provider_attempts"]} == {"docs_search"}
    assert result["evidence_assessment"]["status"] == "not_evaluated"


@pytest.mark.asyncio
async def test_ordinary_deadline_cancels_retrieval(monkeypatch):
    configure_exa(monkeypatch)
    cancelled = asyncio.Event()

    async def slow(*args, **kwargs):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.set()

    monkeypatch.setattr(service, "exa_search", slow)
    result = await service.search("Find this source", timeout_seconds=0.2)
    assert cancelled.is_set()
    assert not result["ok"]
    assert result["error_type"] == "timeout"
    assert result["timeout_phase"] == "retrieval"
    assert len(result["provider_attempts"]) == 1


@pytest.mark.asyncio
async def test_ordinary_search_reserves_time_for_same_capability_fallback(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-test")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")

    async def judge(self, state, questions, timeout):
        return response(questions, {f"channel_{i}": 0.99 if item["provider"] == "context7" else 0.01
                                   for i, item in enumerate(state["available_channels"])})

    async def library(*args, **kwargs):
        await asyncio.Event().wait()

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [{"url": "https://example.org/docs", "content": "Fallback documentation"}]}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "context7_library", library)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await asyncio.wait_for(service.search("React API docs", fallback="auto", timeout_seconds=0.4), 1)

    assert result["ok"]
    assert "Fallback documentation" in result["content"]
    assert [item["provider"] for item in result["provider_attempts"]] == ["context7", "exa"]
    assert result["provider_attempts"][0]["error_type"] == "timeout"
    assert result["provider_attempts"][1]["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["auto", "off"])
async def test_source_free_model_uses_web_search_fallback(monkeypatch, fallback):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test")
    called = []

    async def model(self, query, platform="", ctx=None):
        called.append("xai-responses")
        return "我先检索权威来源。"

    async def tavily(*args, **kwargs):
        called.append("tavily")
        return [{"url": "https://example.org/source", "content": "Retrieved source"}]

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", model)
    monkeypatch.setattr(service, "call_tavily_search", tavily)
    result = await service.search("Find this source", fallback=fallback)

    assert called == (["xai-responses", "tavily"] if fallback == "auto" else ["xai-responses"])
    assert result["ok"] == (fallback == "auto")
    assert result["error_type"] == ("" if fallback == "auto" else "evidence_error")
    assert result["sources_count"] == (1 if fallback == "auto" else 0)
    assert result["provider_attempts"][0]["status"] == "empty"
    assert result["provider_attempts"][0]["error_type"] == "evidence_error"
    if fallback == "auto":
        assert result["sources"][0]["url"] == "https://example.org/source"
        assert [item["capability"] for item in result["provider_attempts"]] == ["main_search", "web_search"]


@pytest.mark.asyncio
async def test_ordinary_search_reserves_time_for_answer_family_fallback(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test")
    monkeypatch.setattr(service.SearchBudget, "remaining_seconds", lambda self: 0.4)

    async def model(self, query, platform="", ctx=None):
        await asyncio.Event().wait()

    async def tavily(*args, **kwargs):
        return [{"url": "https://example.org/source", "content": "Fallback source"}]

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", model)
    monkeypatch.setattr(service, "call_tavily_search", tavily)
    result = await asyncio.wait_for(service.search("Find this source", fallback="auto", timeout_seconds=0.4), 1)

    assert result["ok"]
    assert "Fallback source" in result["content"]
    assert [item["provider"] for item in result["provider_attempts"]] == ["xai-responses", "tavily"]
    assert result["provider_attempts"][0]["error_type"] == "timeout"
    assert result["provider_attempts"][1]["status"] == "ok"
    retrieval = next(item for item in result["phase_attempts"] if item["phase"] == "retrieval")
    assert retrieval["budget_ms"] == 400 * FALLBACK_RESERVE_RATIO


@pytest.mark.asyncio
async def test_selected_model_keeps_configured_failure_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "primary")
    monkeypatch.setenv("OPENAI_COMPATIBLE_FALLBACK_MODELS", "backup")
    called = []

    def providers(configs, fallback):
        async def search(query, platform):
            called.append(configs[0]["model"])
            if configs[0]["model"] == "primary":
                raise RuntimeError("primary unavailable")
            return "Retrieved answer https://example.com/source"
        return [SimpleNamespace(search=search)]

    monkeypatch.setattr(service, "_main_search_providers", providers)
    result = await service.search("Find this source")
    assert result["ok"]
    assert called == ["primary", "backup"]
    assert result["model"] == "backup"
    assert result["model_fallback_used"]
    assert result["jev_calls"] == []


@pytest.mark.asyncio
async def test_calibration_is_retired_without_remote_calls():
    result = await service.route_calibrate()
    assert result["deprecated"]
    assert not result["executed_remote"]


@pytest.mark.asyncio
async def test_empty_context7_document_does_not_become_a_read_citation(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTEXT7_API_KEY", "ctx-test")

    async def libraries(*args, **kwargs):
        return {"ok": True, "results": [{"id": "/reactjs/react.dev", "title": "React"}]}

    async def docs(*args, **kwargs):
        return {"ok": True, "content": ""}

    monkeypatch.setattr(service, "context7_library", libraries)
    monkeypatch.setattr(service, "context7_docs", docs)
    result = await service.research("React API docs", budget="standard", evidence_dir=str(tmp_path))
    assert not result["ok"]
    assert result["citations"] == []
    assert result["evidence_items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["auto", "off"])
@pytest.mark.parametrize("primary", ["openai-compatible", "xai-responses"])
async def test_model_answer_without_sources_uses_same_capability_fallback(monkeypatch, primary, fallback):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", primary)
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "300")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD", "1")
    called = []
    backup = "xai-responses" if primary == "openai-compatible" else "openai-compatible"

    async def search(self, query, platform="", ctx=None):
        provider = "openai-compatible" if isinstance(self, service.OpenAICompatibleSearchProvider) else "xai-responses"
        called.append(provider)
        if provider == primary:
            return "我先检索权威来源。"
        return 'Retrieved answer.\n\nsources([{"url":"https://example.org/source","title":"Source"}])'

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", search)
    result = await service.search("Find this source", fallback=fallback)

    assert called == ([primary, backup] if fallback == "auto" else [primary])
    assert result["ok"] == (fallback == "auto")
    assert result["error_type"] == ("" if fallback == "auto" else "evidence_error")
    assert {item["capability"] for item in result["provider_attempts"]} == {"main_search"}
    attempt = [item for item in result["provider_attempts"] if item["provider"] == primary][-1]
    assert attempt["status"] == "empty"
    assert attempt["error_type"] == "evidence_error"
    assert attempt["error"] == "Search model answer contained no source URLs"
    assert attempt["result_count"] == 0
    assert "我先检索" not in result["content"]
    health = service._provider_health_status(primary)
    assert health["state"] == "closed"
    assert health["consecutive_failures"] == 0
    if fallback == "auto":
        assert result["content"] == "Retrieved answer."
        assert result["provider"] == backup


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["auto", "off"])
@pytest.mark.parametrize("primary", ["openai-compatible", "xai-responses"])
@pytest.mark.parametrize("answer, reason, message", [
    ("NO_WEB_SEARCH", "no_web_search", "Search model reported that it has no web search access"),
    ("I'll look up this on https://example.org/page.", "preface_only", "Search model returned only a preface announcing a search"),
])
async def test_model_answer_quality_uses_same_capability_fallback(monkeypatch, primary, fallback, answer, reason, message):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_MODE", "chat-completions")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "test-model")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_MODEL", "test-model")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", primary)
    called = []
    backup = "xai-responses" if primary == "openai-compatible" else "openai-compatible"

    async def search(self, query, platform="", ctx=None):
        provider = "openai-compatible" if isinstance(self, service.OpenAICompatibleSearchProvider) else "xai-responses"
        called.append(provider)
        if provider == primary:
            return answer
        return 'Retrieved answer.\n\nsources([{"url":"https://example.org/source","title":"Source"}])'

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", search)
    result = await service.search("Find this source", fallback=fallback)

    assert called == ([primary, backup] if fallback == "auto" else [primary])
    assert result["ok"] == (fallback == "auto")
    attempt = [item for item in result["provider_attempts"] if item["provider"] == primary][-1]
    assert attempt["status"] == "empty"
    assert attempt["error_type"] == "evidence_error"
    assert attempt["error"] == message
    assert attempt["result_count"] == 0
    if fallback == "auto":
        assert result["content"] == "Retrieved answer."
        assert result["provider"] == backup
        assert result["answer_check"]["status"] == "passed"
    else:
        assert result["answer_check"] == {
            "status": "rejected", "method": "local", "reason": reason, "provider": primary,
            "api_mode": "chat-completions" if primary == "openai-compatible" else "xai-responses", "model": "test-model",
        }
        assert any("Search model answer rejected" in warning for warning in result["warnings"])
        if primary == "openai-compatible":
            assert any("XAI_API_URL" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_rejected_model_answer_keeps_degraded_reason(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")

    async def search(self, query, platform="", ctx=None):
        return "NO_WEB_SEARCH"

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    result = await service.search("Find this source", providers="openai-compatible", fallback="auto")

    assert result["ok"] is False
    assert result["degraded"] is True
    assert result["degraded_reason"].startswith("TYPESAFE_API_KEY is not configured")
    assert result["answer_check"]["reason"] == "no_web_search"
    assert any("XAI_API_URL" in warning for warning in result["warnings"])


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai-compatible", "xai-responses"])
async def test_model_answer_rejects_think_only_urls(monkeypatch, provider):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    async def search(self, query, platform="", ctx=None):
        return "<think>参考 https://example.com/x</think>我先检索"

    provider_type = service.OpenAICompatibleSearchProvider if provider == "openai-compatible" else service.XAIResponsesSearchProvider
    monkeypatch.setattr(provider_type, "search", search)
    result = await service.search("Find this source", providers=provider, fallback="off")

    assert result["ok"] is False
    assert result["error_type"] == "evidence_error"
    assert result["content"] == ""
    assert result["sources"] == []
    assert result["provider_attempts"][0]["status"] == "empty"
    assert result["provider_attempts"][0]["error_type"] == "evidence_error"
    assert service._provider_health_status(provider)["consecutive_failures"] == 0
    assert service._OPENAI_COMPATIBLE_MODEL_BREAKERS == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback,backup_has_sources", [("auto", True), ("auto", False), ("off", True)])
async def test_source_free_model_tries_configured_fallback(monkeypatch, fallback, backup_has_sources):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "primary-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_FALLBACK_MODELS", "fallback-model")
    called, successes = [], []
    record_success = service._record_openai_model_success

    def success(api_url, model, api_mode):
        successes.append(model)
        record_success(api_url, model, api_mode)

    async def search(self, query, platform="", ctx=None):
        called.append(self.model)
        self.last_transport_attempts = [{"transport": "non_stream", "status": "ok", "result_count": 1}]
        if self.model == "fallback-model" and backup_has_sources:
            return 'Retrieved answer.\n\nsources([{"url":"https://example.org/source"}])'
        return "我先检索权威来源。"

    monkeypatch.setattr(service, "_record_openai_model_success", success)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    result = await service.search("Find this source", providers="openai-compatible", fallback=fallback)

    expected_ok = fallback == "auto" and backup_has_sources
    assert called == (["primary-model", "fallback-model"] if fallback == "auto" else ["primary-model"])
    assert result["ok"] is expected_ok
    assert result["error_type"] == ("" if expected_ok else "evidence_error")
    assert successes == (["fallback-model"] if expected_ok else [])
    assert service._OPENAI_COMPATIBLE_MODEL_BREAKERS == {}
    attempts = result["provider_attempts"]
    assert [item["model"] for item in attempts] == called
    for attempt in attempts[:1] if expected_ok else attempts:
        assert attempt["status"] == "empty"
        assert attempt["error_type"] == "evidence_error"
        assert attempt["error"] == "Search model answer contained no source URLs"
        assert attempt["result_count"] == 0
    if expected_ok:
        assert result["model"] == "fallback-model"
        assert attempts[-1]["status"] == "ok"
    else:
        assert service._provider_health_status("openai-compatible")["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_source_free_xai_fallback_reports_openai_model_metadata(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_MODEL", "xai-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "relay-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_MODE", "responses")
    called = []

    async def search(self, query, platform="", ctx=None):
        called.append(self.model)
        if self.model == "xai-model":
            return "我先检索权威来源。"
        return 'Retrieved answer.\n\nsources([{"url":"https://example.org/source"}])'

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", search)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    result = await service.search("Find this source")

    assert called == ["xai-model", "relay-model"]
    assert result["ok"] is True
    assert result["provider"] == "openai-compatible"
    assert result["model"] == "relay-model"
    assert result["primary_api_mode"] == "responses"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["local", "jev"])
@pytest.mark.parametrize("stream", [None, False, True])
@pytest.mark.parametrize("effort", ["", "HIGH"])
async def test_search_xai_stream_and_reasoning_effort(monkeypatch, mode, stream, effort):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", mode)
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_REASONING_EFFORT", effort)
    annotations = [{"type": "url_citation", "url": "https://example.org/source", "title": "Source"}]
    events = [
        {"type": "response.output_text.delta", "delta": "Retrieved "},
        {"type": "response.output_text.delta", "delta": "answer."},
        {"type": "response.output_text.annotation.added", "annotation": annotations[0]},
        {"type": "response.completed", "response": {"status": "completed", "output": []}},
    ]
    requests, judgments = [], []
    original_client = httpx.AsyncClient

    async def judge(self, state, questions, timeout):
        if "answer" in state:
            return response(questions, {"substantive": 0.99, "contradicted": 0.01})
        judgments.append(state)
        return response(questions, {"channel_0": 0.99})

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert str(request.url) == "https://api.x.ai/v1/responses"
        if payload["stream"]:
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                                  text="".join(f"data: {json.dumps(event)}\n\n" for event in events))
        return httpx.Response(200, json={"output": [{"type": "message", "content": [
            {"type": "output_text", "text": "Retrieved answer.", "annotations": annotations},
        ]}]})

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    result = await service.search("Find this source", providers="xai-responses", fallback="off", stream=stream)

    assert result["ok"] is True
    assert result["content"] == "Retrieved answer."
    assert result["primary_sources"][0]["url"] == "https://example.org/source"
    assert result["primary_sources"][0]["title"] == "Source"
    assert len(requests) == 1
    assert requests[0]["stream"] is bool(stream)
    if effort:
        assert requests[0]["reasoning"] == {"effort": "high"}
    else:
        assert "reasoning" not in requests[0]
    assert len(judgments) == (1 if mode == "jev" else 0)
    assert len(result["provider_attempts"]) == 1
    assert result["provider_attempts"][0]["stream"] is bool(stream)
    assert result["provider_attempts"][0]["reasoning_effort"] == effort.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_search_xai_unsupported_reasoning_fails_once(monkeypatch, stream):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_REASONING_EFFORT", "high")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "3")
    requests = []
    original_client = httpx.AsyncClient
    error_body = b'{"error":{"message":"reasoning.effort is not supported"}}'

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(400, stream=httpx.ByteStream(error_body))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    result = await service.search("Find this source", providers="xai-responses", fallback="off", stream=stream)

    assert len(requests) == 1
    assert requests[0]["stream"] is stream
    assert requests[0]["reasoning"] == {"effort": "high"}
    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert result["error"] == "HTTP 400: " + error_body.decode()
    assert result["provider_attempts"][0]["stream"] is stream
    assert result["provider_attempts"][0]["reasoning_effort"] == "high"


@pytest.mark.asyncio
@pytest.mark.parametrize(("configured", "override", "expected"), [
    ("true", None, True), ("1", None, True), ("yes", None, True),
    ("true", False, False), ("false", True, True), ("", None, False),
])
async def test_search_xai_stream_follows_xai_stream_unless_overridden(monkeypatch, xai_requests, configured, override, expected):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", configured)

    result = await service.search("Find this source", providers="xai-responses", fallback="off", stream=override)

    assert result["ok"] is True
    assert [payload["stream"] for payload in xai_requests] == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(("stream", "transport"), [(True, "stream"), (False, "non_stream")])
async def test_search_xai_attempt_reports_transport(monkeypatch, xai_requests, stream, transport):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    result = await service.search("Find this source", providers="xai-responses", fallback="off", stream=stream)

    assert [attempt["transport"] for attempt in result["provider_attempts"]] == [transport]


@pytest.mark.asyncio
@pytest.mark.parametrize(("configured", "override", "expected"), [
    ("true", None, True), ("true", False, False), ("", True, True), ("", None, False),
])
async def test_research_xai_stream_follows_xai_stream_unless_overridden(monkeypatch, tmp_path, xai_requests, configured, override, expected):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", configured)

    await service.research("Find this source", budget="quick", evidence_dir=str(tmp_path), stream=override)

    assert xai_requests and {payload["stream"] for payload in xai_requests} == {expected}


@pytest.mark.parametrize(("flag", "expected"), [("--stream", True), ("--no-stream", False)])
def test_research_cli_stream_flags_override_xai_stream(monkeypatch, tmp_path, capsys, xai_requests, flag, expected):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", "false" if expected else "true")

    cli.main(["research", "Find this source", "--budget", "quick", "--evidence-dir", str(tmp_path), flag, "--format", "json"])

    assert xai_requests and {payload["stream"] for payload in xai_requests} == {expected}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai-compatible", "xai-responses"])
async def test_model_answer_with_sources_keeps_success(monkeypatch, provider):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    async def search(self, query, platform="", ctx=None):
        return 'Retrieved answer.\n\nsources([{"url":"https://example.org/source","title":"Source"}])'

    provider_type = service.OpenAICompatibleSearchProvider if provider == "openai-compatible" else service.XAIResponsesSearchProvider
    monkeypatch.setattr(provider_type, "search", search)
    result = await service.search("Find this source", providers=provider, fallback="off")

    assert result["ok"]
    assert result["content"] == "Retrieved answer."
    assert result["provider"] == provider
    assert result["primary_sources_count"] == 1
    assert result["primary_sources"][0]["url"] == "https://example.org/source"
    assert result["primary_sources"][0]["kind"] == "citation"
    assert len(result["provider_attempts"]) == 1
    assert result["provider_attempts"][0]["status"] == "ok"
    assert result["provider_attempts"][0]["error_type"] == ""


@pytest.mark.asyncio
async def test_model_answer_with_body_markdown_link_keeps_success_without_fallback(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", "openai-compatible")
    answer = "The [official guide](https://example.com/source) explains this behavior.\n\nAdditional explanation follows."
    called = []

    async def search(self, query, platform="", ctx=None):
        called.append("openai-compatible")
        return answer

    async def backup(self, query, platform="", ctx=None):
        called.append("xai-responses")
        raise AssertionError("A body source URL must not trigger fallback")

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", search)
    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", backup)
    result = await service.search("Find this source")

    assert result["ok"]
    assert result["content"] == answer
    assert result["sources"] == []
    assert result["primary_sources"] == []
    assert called == ["openai-compatible"]
    assert not result["fallback_used"]
    assert len(result["provider_attempts"]) == 1
    assert result["provider_attempts"][0]["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("research", [False, True])
async def test_context7_without_jev_selects_first_library(monkeypatch, research):
    async def libraries(*args, **kwargs):
        return {"ok": True, "results": [
            {"id": "/first/library", "title": "First candidate"},
            {"id": "/reactjs/react.dev", "title": "React"},
        ]}

    async def docs(library_id, query):
        assert library_id == "/first/library"
        return {"ok": True, "content": "Documentation"}

    monkeypatch.setattr(service, "context7_library", libraries)
    monkeypatch.setattr(service, "context7_docs", docs)
    client = SimpleNamespace(settings=SimpleNamespace(api_key=""), last_error=None)
    results = await ChannelExecutor(service, client, research=research)._context7("React API docs")
    assert results[0]["url"] == "context7:/first/library"


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_context7_jev_unresolved_selects_first_library(monkeypatch, failed):
    async def libraries(*args, **kwargs):
        return {"ok": True, "results": [{"id": "/first/library"}, {"id": "/second/library"}]}

    async def evaluate(*args):
        if failed:
            raise ProviderCallError("network_error", "Jev unavailable")
        return {"library_0": 0.1, "library_1": 0.4}

    async def docs(library_id, query):
        assert library_id == "/first/library"
        return {"ok": True, "content": "Documentation"}

    monkeypatch.setattr(service, "context7_library", libraries)
    monkeypatch.setattr(service, "context7_docs", docs)
    client = SimpleNamespace(settings=SimpleNamespace(api_key="jev-test"), last_error=None, evaluate=evaluate)
    results = await ChannelExecutor(service, client, research=True)._context7("React API docs")
    assert results[0]["url"] == "context7:/first/library"


@pytest.mark.asyncio
async def test_context7_no_relevant_snippets_is_empty_and_uses_fallback(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-test")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", "context7,exa")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "300")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD", "1")
    called = []

    def handler(request):
        called.append(request.url.path)
        if request.url.path == "/api/v2/libs/search":
            return httpx.Response(200, json={"results": [{"id": "/reactjs/react.dev", "title": "React"}]})
        assert request.url.path == "/api/v2/context"
        assert request.url.params["libraryId"] == "/reactjs/react.dev"
        return httpx.Response(404, json={"error": "no_relevant_snippets", "message": "No documentation matched this query."})

    async def exa(*args, **kwargs):
        called.append("exa")
        return {"ok": True, "results": [{"url": "https://example.org/docs", "content": "Fallback documentation"}]}

    client = httpx.AsyncClient
    monkeypatch.setattr("smart_search.providers.context7.httpx.AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("React API docs")

    assert called == ["/api/v2/libs/search", "/api/v2/context", "exa"]
    assert result["ok"]
    assert "Fallback documentation" in result["content"]
    assert [(item["provider"], item["status"]) for item in result["provider_attempts"]] == [("context7", "empty"), ("exa", "ok")]
    assert {item["capability"] for item in result["provider_attempts"]} == {"docs_search"}
    health = service._provider_health_status("context7")
    assert health["state"] == "closed"
    assert health["consecutive_failures"] == 0
