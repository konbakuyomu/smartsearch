"""Foreground opt-in, transport and evidence checks; all retrieval here is mocked."""

import asyncio
import json

import httpx
import pytest

from smart_search import jev_search, service, ui_api
from smart_search.providers.parallel import PARALLEL_MCP_URL, PARALLEL_USER_AGENT

QUERY = "Python pathlib Path documentation"
URL = "https://docs.python.org/3/library/pathlib.html"


@pytest.fixture
def mcp(monkeypatch):
    requests = []
    state = {"results": [{"url": URL, "title": "pathlib", "excerpts": ["Path represents filesystem paths."]}],
             "format": "sse", "error": "", "tools": ["web_search"], "structured": True}
    original = httpx.AsyncClient

    async def handler(request):
        assert str(request.url) == PARALLEL_MCP_URL
        assert request.headers["User-Agent"] == PARALLEL_USER_AGENT
        assert "authorization" not in request.headers
        assert "x-api-key" not in request.headers
        body = json.loads(request.content)
        requests.append(body)
        method = body["method"]
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {}}
        else:
            assert request.headers["Mcp-Session-Id"] == "synthetic-mcp-session"
            assert request.headers["MCP-Protocol-Version"] == "2025-03-26"
            if method == "notifications/initialized":
                return httpx.Response(202)
            if method == "tools/list":
                result = {"tools": [{"name": tool} for tool in state["tools"]]}
            else:
                assert method == "tools/call"
                assert body["params"] == {"name": "web_search", "arguments": {
                    "objective": "Find public software documentation matching the search query.",
                    "search_queries": [QUERY]}}
                if state["error"] == "timeout":
                    raise httpx.ReadTimeout("fixture timeout")
                if state["error"] == "deadline":
                    await asyncio.sleep(1)
                if state["error"] == "http":
                    return httpx.Response(503)
                data = {"results": state["results"]}
                result = {"content": [{"type": "text", "text": json.dumps(data)}],
                          "isError": state["error"] == "tool"}
                if state["structured"]:
                    result["structuredContent"] = data
        payload = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        if state["error"] == "rpc" and method == "tools/call":
            payload = {"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32000, "message": "unavailable"}}
        if state["error"] == "malformed" and method == "tools/call":
            return httpx.Response(200, text="invalid", headers={"Content-Type": "application/json"})
        headers = {"Mcp-Session-Id": "synthetic-mcp-session"}
        if state["format"] == "sse":
            headers["Content-Type"] = "text/event-stream"
            return httpx.Response(200, text=f"event: message\ndata: {json.dumps(payload)}\n\n", headers=headers)
        return httpx.Response(200, json=payload, headers=headers)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    return state, requests


def payload(**extra):
    return {"command": "search", "provider": "parallel", "query": QUERY, "public_query_confirmed": True, **extra}


@pytest.mark.asyncio
@pytest.mark.parametrize("format,structured", [("sse", True), ("json", False)])
async def test_foreground_ui_returns_original_source_and_only_sends_typed_query(mcp, monkeypatch, format, structured):
    state, requests = mcp
    state.update(format=format, structured=structured)
    # Saved keys and unexpected request fields must never enter the retrieval payload.
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-unused-router-key")
    monkeypatch.setenv("EXA_API_KEY", "synthetic-unused-exa-key")
    result = await ui_api.run_query(payload(context="synthetic-private-context", history=["synthetic-private-history"]))
    assert result["ok"]
    assert result["provider"] == "parallel"
    assert result["sources"][0]["url"] == URL
    assert result["sources"][0]["read"] is False
    assert URL in result["content"]
    assert result["jev_calls"] == []
    assert result["routing_decision"]["rounds"][0]["selection_source"] == "explicit"
    assert len(result["provider_attempts"]) == 1
    assert result["evidence_assessment"]["status"] == "not_evaluated"
    assert [body["method"] for body in requests] == ["initialize", "notifications/initialized", "tools/list", "tools/call"]
    assert "synthetic-private" not in json.dumps(requests)
    assert "synthetic-unused" not in json.dumps(requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmed", [None, False, "true", 1])
async def test_confirmation_is_required_before_any_request(mcp, confirmed):
    result = await ui_api.run_query(payload(public_query_confirmed=confirmed))
    assert result["error_type"] == "parameter_error"
    assert mcp[1] == []


@pytest.mark.asyncio
async def test_offline_route_remains_offline_even_with_parallel_selected(mcp):
    await ui_api.run_query(payload(command="route", public_query_confirmed=False))
    assert mcp[1] == []


def test_parallel_excluded_from_automatic_and_provider_filtered_catalogs(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", "parallel")
    for providers in ("auto", "parallel", "parallel,exa"):
        assert all(c["provider"] != "parallel" for c in jev_search.available_channels(service, QUERY, [], providers))
    assert all("parallel" not in chain for chain in service.RESEARCH_PROFILE_ORDER.values())
    assert service.provider_profiles()["parallel"]["explicit_only"]


@pytest.mark.asyncio
async def test_default_ui_preserves_existing_search_dispatch(mcp, monkeypatch):
    seen = []

    async def existing(query, **kwargs):
        seen.append((query, kwargs))
        return {"ok": True}

    monkeypatch.setattr(service, "search", existing)
    assert (await ui_api.run_query({"command": "search", "query": QUERY}))["ok"]
    assert seen == [(QUERY, {"timeout_seconds": None})]
    assert mcp[1] == []


@pytest.mark.asyncio
async def test_explicit_selection_still_respects_disabled_provider(mcp, monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", "parallel")
    result = await ui_api.run_query(payload())
    assert result["error_type"] == "config_error"
    assert mcp[1] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("error,expected", [("http", "network_error"), ("tool", "provider_error"), ("rpc", "provider_error"), ("timeout", "timeout"), ("malformed", "provider_error")])
async def test_unavailable_search_reports_error_without_fallback(mcp, error, expected):
    mcp[0]["error"] = error
    result = await ui_api.run_query(payload())
    assert not result["ok"]
    assert result["error_type"] == expected
    assert len(result["provider_attempts"]) == 1
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_missing_tool_does_not_call_other_tools(mcp):
    mcp[0]["tools"] = ["web_research", "web_fetch"]
    result = await ui_api.run_query(payload())
    assert result["error_type"] == "provider_error"
    assert all(body["method"] != "tools/call" for body in mcp[1])


@pytest.mark.asyncio
async def test_empty_search_is_not_success_or_health_failure(mcp):
    mcp[0]["results"] = []
    result = await ui_api.run_query(payload())
    assert not result["ok"]
    assert result["provider_attempts"][0]["status"] == "empty"
    assert service._provider_health_status("parallel")["state"] != "cooldown"


@pytest.mark.asyncio
async def test_shared_deadline_is_preserved(mcp):
    mcp[0]["error"] = "deadline"
    result = await ui_api.run_query(payload(timeout_seconds=0.01))
    assert result["error_type"] == "timeout"
    assert result["timeout_phase"] == "retrieval"
    assert len(result["provider_attempts"]) == 1


@pytest.mark.asyncio
async def test_research_cannot_enable_foreground_provider(mcp):
    result = await jev_search.search(QUERY, validation="balanced", fallback="auto", providers="auto",
                                     timeout_seconds=1, single_pass=False, foreground_provider="parallel")
    assert result["error_type"] == "parameter_error"
    assert mcp[1] == []


@pytest.mark.asyncio
async def test_cooldown_prevents_dispatch(mcp):
    service._record_provider_result("parallel", "error", "auth_error", "synthetic unavailable service")
    result = await ui_api.run_query(payload())
    assert not result["ok"]
    assert result["provider_attempts"][0]["status"] == "skipped"
    assert mcp[1] == []


@pytest.mark.asyncio
async def test_cancellation_preserves_shared_cancelled_result(mcp):
    mcp[0]["error"] = "deadline"
    task = asyncio.create_task(ui_api.run_query(payload()))
    while not any(body["method"] == "tools/call" for body in mcp[1]):
        await asyncio.sleep(0)
    task.cancel()
    result = await task
    assert result["error_type"] == "cancelled"
    assert result["provider_attempts"][0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_executor_rejects_implicit_or_changed_queries(mcp):
    settings = service.config.jev_settings()
    client = jev_search.JevClient(settings, float("inf"))
    channel = {"provider": "parallel", "operation": "search"}
    for executor, query in [
        (jev_search.ChannelExecutor(service, client), QUERY),
        (jev_search.ChannelExecutor(service, client, foreground_query=QUERY), QUERY + " other context"),
        (jev_search.ChannelExecutor(service, client, foreground_query=QUERY, research=True), QUERY),
    ]:
        with pytest.raises(service.ProviderCallError, match="explicit foreground"):
            await executor.execute(channel, query)
    assert mcp[1] == []
