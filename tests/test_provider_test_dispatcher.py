"""Single-provider connection testing, the thing `doctor` could only do all at once."""

import asyncio
import json

import httpx
import pytest

from smart_search import service
from smart_search.provider_health import ProviderHealthStore


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(service.config, "_config_file", tmp_path / "config.json")
    monkeypatch.setattr(service.config, "_cached_model", None)
    store = ProviderHealthStore(tmp_path / "provider_health.json", cooldown_seconds=900, failure_threshold=2)
    monkeypatch.setattr(service, "provider_health", store)
    return store


@pytest.mark.asyncio
async def test_unknown_provider_is_a_parameter_error(isolated):
    result = await service.test_provider_connection("not-a-provider")
    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert "exa" in result["known_providers"]


def test_every_known_provider_resolves_to_a_strategy():
    for provider, kind in service.PROBE_KIND.items():
        if kind == "main":
            continue
        target = kind.split(":", 1)[1] if kind.startswith("shared:") else provider
        assert target in service._LIVE_PROBES, f"{provider} has no runnable probe"


@pytest.mark.asyncio
async def test_success_clears_an_existing_cooldown(isolated, monkeypatch):
    service.config.set_config_value("EXA_API_KEY", "exa-key")
    isolated.record_failure("exa", service._provider_fingerprint("exa"), "auth_error", "401")
    assert isolated.status("exa")["state"] == "cooldown"

    async def ok_probe():
        return {"status": "ok", "message": "Exa API 可用", "response_time_ms": 12}

    monkeypatch.setitem(service._LIVE_PROBES, "exa", ok_probe)
    result = await service.test_provider_connection("exa")

    assert result["ok"] is True
    assert result["probe"] == "live"
    assert result["recorded_as"] == "exa"
    assert isolated.status("exa")["state"] == "closed", "a passing test must be a recovery path"


@pytest.mark.asyncio
async def test_failure_is_recorded_into_the_cooldown_store(isolated, monkeypatch):
    service.config.set_config_value("EXA_API_KEY", "exa-key")

    async def auth_failure():
        return {"status": "auth_error", "message": "401 unauthorized"}

    monkeypatch.setitem(service._LIVE_PROBES, "exa", auth_failure)
    result = await service.test_provider_connection("exa")

    assert result["ok"] is False
    assert result["status"] == "auth_error"
    # A hard failure opens the cooldown on the first occurrence.
    assert isolated.status("exa")["state"] == "cooldown"


@pytest.mark.asyncio
async def test_overrides_never_touch_the_health_store(isolated, monkeypatch):
    service.config.set_config_value("XAI_API_KEY", "saved-key")
    isolated.record_failure("zhipu", service._provider_fingerprint("zhipu"), "auth_error", "401")

    async def fake_main(provider_config):
        assert provider_config["api_key"] == "candidate-key"
        return {"status": "ok", "message": "ok"}

    monkeypatch.setattr(service, "_safe_test_main_provider_connection", fake_main)
    result = await service.test_provider_connection(
        "xai-responses", overrides={"XAI_API_KEY": "candidate-key"}
    )

    assert result["ok"] is True
    assert result["recorded_as"] == "", "an override run must not claim a health record"
    assert isolated.status("zhipu")["state"] == "cooldown", "unrelated cooldowns stay put"


@pytest.mark.asyncio
async def test_a_hanging_probe_is_bounded_by_the_ceiling(isolated, monkeypatch):
    service.config.set_config_value("EXA_API_KEY", "exa-key")

    async def never_returns():
        await asyncio.sleep(30)

    monkeypatch.setitem(service._LIVE_PROBES, "exa", never_returns)
    result = await service.test_provider_connection("exa", timeout_seconds=0.05)

    assert result["status"] == "timeout"
    assert "0.05s" in result["message"]


@pytest.mark.asyncio
async def test_reader_reports_the_shared_credential(isolated, monkeypatch):
    service.config.set_config_value("ZHIPU_MCP_API_KEY", "mcp-key")

    async def ok_probe():
        return {"status": "ok", "message": "可用"}

    monkeypatch.setitem(service._LIVE_PROBES, "zhipu-mcp", ok_probe)
    result = await service.test_provider_connection("zhipu-mcp-reader")

    assert result["probe"] == "shared"
    assert result["recorded_as"] == "zhipu-mcp"
    assert "zhipu-mcp" in result["message"]


@pytest.mark.asyncio
async def test_firecrawl_reports_presence_not_a_green_tick(isolated):
    result = await service.test_provider_connection("firecrawl")
    assert result["status"] == "not_configured"

    service.config.set_config_value("FIRECRAWL_API_KEY", "fc-key")
    result = await service.test_provider_connection("firecrawl")
    assert result["probe"] == "presence"
    assert result["status"] == "configured"
    assert result["ok"] is False, "presence is not proof the key works"


@pytest.mark.asyncio
async def test_anysearch_probe_uses_the_domain_listing(isolated, monkeypatch):
    service.config.set_config_value("ANYSEARCH_API_KEY", "as-key")
    called = []

    async def fake_domains():
        called.append(True)
        return {"ok": True, "elapsed_ms": 30}

    monkeypatch.setattr(service, "anysearch_domains", fake_domains)
    result = await service.test_provider_connection("anysearch")

    assert called == [True], "the probe must not spend search quota"
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_sciverse_probe_uses_the_catalog(isolated, monkeypatch):
    service.config.set_config_value("SCIVERSE_API_TOKEN", "sv-token")
    called = []

    async def fake_catalog():
        called.append(True)
        return {"ok": True, "elapsed_ms": 25}

    monkeypatch.setattr(service, "sciverse_catalog", fake_catalog)
    result = await service.test_provider_connection("sciverse")

    assert called == [True]
    assert result["ok"] is True


def test_record_probe_result_matches_the_doctor_contract(isolated, monkeypatch):
    service.config.set_config_value("EXA_API_KEY", "exa-key")
    for status in service.DOCTOR_PROBE_NEUTRAL_STATUSES:
        service._record_probe_result("exa", {"status": status, "message": "n/a"})
        assert isolated.status("exa")["state"] == "closed", f"{status} must stay neutral"

    service._record_probe_result("exa", {"status": "config_error", "message": "missing url"})
    assert isolated.status("exa")["state"] == "cooldown"
    service._record_probe_result("exa", {"status": "ok", "message": "fine"})
    assert isolated.status("exa")["state"] == "closed"


@pytest.mark.asyncio
@pytest.mark.parametrize(("effort", "stream"), [("medium", True), ("", False)])
async def test_xai_test_sends_the_configured_reasoning_effort_and_stream(isolated, monkeypatch, xai_requests, effort, stream):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_REASONING_EFFORT", effort)
    monkeypatch.setenv("XAI_STREAM", "true" if stream else "false")

    result = await service.test_provider_connection("xai-responses")

    assert result["status"] == "ok"
    assert len(xai_requests) == 1
    assert xai_requests[0]["stream"] is stream
    assert xai_requests[0].get("reasoning") == ({"effort": effort} if effort else None)
    assert "tools" not in xai_requests[0]
    assert result["sent"] == {"reasoning_effort": effort, "stream": stream, "tools": []}


@pytest.mark.asyncio
async def test_xai_test_uses_unsaved_form_values(isolated, monkeypatch, xai_requests):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    result = await service.test_provider_connection(
        "xai-responses", overrides={"XAI_REASONING_EFFORT": "low", "XAI_STREAM": "true"},
    )

    assert result["status"] == "ok"
    assert xai_requests[0]["reasoning"] == {"effort": "low"}
    assert xai_requests[0]["stream"] is True


@pytest.mark.asyncio
async def test_doctor_xai_test_sends_the_configured_reasoning_effort(isolated, monkeypatch, xai_requests):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_REASONING_EFFORT", "medium")

    info = await service.doctor()

    assert xai_requests[0]["reasoning"] == {"effort": "medium"}
    assert info["main_search_connection_tests"]["xai-responses"]["sent"]["reasoning_effort"] == "medium"


@pytest.mark.asyncio
async def test_xai_stream_test_reports_an_error_event_after_http_200(isolated, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", "true")
    event = {"type": "error", "error": {"message": "reasoning.effort is not supported"}}
    original_client = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, text=f"data: {json.dumps(event)}\n\n")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    result = await service.test_provider_connection("xai-responses")

    assert result["status"] != "ok"
    assert "reasoning.effort is not supported" in result["message"]


def answer_xai(monkeypatch, handler):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.asyncio
async def test_xai_stream_test_reports_a_stream_without_text(isolated, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", "true")
    completed = {"type": "response.completed", "response": {"status": "completed", "output": []}}
    answer_xai(monkeypatch, lambda request: httpx.Response(
        200, headers={"Content-Type": "text/event-stream"}, text=f"data: {json.dumps(completed)}\n\n"))

    result = await service.test_provider_connection("xai-responses")

    assert result["status"] == "warning"


@pytest.mark.asyncio
async def test_xai_test_message_names_the_sent_parameters(isolated, monkeypatch, xai_requests):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_REASONING_EFFORT", "medium")
    monkeypatch.setenv("XAI_STREAM", "true")

    result = await service.test_provider_connection("xai-responses")

    assert "reasoning.effort=medium, stream=true, tools=[]" in result["message"]


@pytest.mark.asyncio
async def test_xai_test_reports_sent_parameters_when_it_times_out(isolated, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    monkeypatch.setenv("XAI_STREAM", "true")

    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    answer_xai(monkeypatch, handler)

    result = await service.test_provider_connection("xai-responses")

    assert result["status"] == "timeout"
    assert result["sent"] == {"reasoning_effort": "", "stream": True, "tools": []}
