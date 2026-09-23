import asyncio
import json
import time

import httpx
import pytest

from smart_search import service
from smart_search.jev import JevClient, assess_evidence, filter_evidence, noul
from smart_search.jev_search import available_channels
from smart_search.provider_errors import ProviderCallError


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "jev-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "0")
    return service.config.jev_settings()


def answer_payload(questions, scores):
    return {
        "model": "jev-test", "usage": {"input_tokens": 50, "output_tokens": 5},
        "answers": {key: {"type": "noul", "noul": scores.get(key, 0.0)} for key in questions},
    }


def scripted_jev(monkeypatch, selections, assessments, *, filter_score=None, synthesis_score=None):
    """Stub only the remote boundary; retain parsing and all workflow decisions."""
    calls = []
    selections = iter(selections)
    assessments = iter(assessments)

    async def request(self, state, questions, timeout):
        calls.append((state, questions))
        if "available_channels" in state:
            selected = next(selections)
            scores = {f"channel_{i}": 0.95 if item["id"] in selected else 0.02 for i, item in enumerate(state["available_channels"])}
        elif "groups" in state:
            assert filter_score is not None, "filtering should not be called"
            scores = {f"group_{i}": filter_score(group) for i, group in enumerate(state["groups"])}
        elif "synthesize" in questions:
            assert synthesis_score is not None, "synthesis judgment should not be called"
            if isinstance(synthesis_score, Exception):
                raise synthesis_score
            scores = {"synthesize": synthesis_score}
        else:
            scores = next(assessments)
        return answer_payload(questions, scores)

    monkeypatch.setattr(JevClient, "_request", request)
    return calls


def hit(text, url="https://example.org/docs", title="Documentation"):
    return {"url": url, "title": title, "content": text}


def evidence(text, number):
    return {"id": f"e{number}", "provider": "exa", "url": f"https://example.org/{number}", "title": f"Result {number}", "content": text}


@pytest.mark.asyncio
async def test_only_allowed_configured_operations_reach_jev(monkeypatch, configured):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("TAVILY_ENABLED", "false")
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-secret")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", "context7")
    calls = scripted_jev(monkeypatch, [{"exa:search"}], [])

    result = await service.route("TaskGroup cancellation", mode="jev")

    assert result["ok"]
    assert result["executed_search"] is False
    assert [item["id"] for item in calls[0][0]["available_channels"]] == ["exa:search"]
    payload = json.dumps(calls)
    for secret in ("jev-test-secret", "exa-test-secret", "tavily-secret", "context7-secret"):
        assert secret not in payload
    assert result["jev_usage"]["input_tokens"] == 50


@pytest.mark.asyncio
async def test_parallel_multiselect_does_not_require_or_call_grok(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    calls = scripted_jev(monkeypatch, [{"exa:search", "zhipu:search"}], [{"useful": 0.99, "sufficient": 0.95}])
    started = set()
    both_started = asyncio.Event()

    async def retrieve(provider):
        started.add(provider)
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), 0.5)
        return {"ok": True, "results": [hit(f"Evidence from {provider}", f"https://example.org/{provider}")]}

    async def exa(*args, **kwargs):
        return await retrieve("exa")

    async def zhipu(*args, **kwargs):
        return await retrieve("zhipu")

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "zhipu_search", zhipu)
    result = await service.search("Compare these two sources")

    assert result["ok"]
    assert set(result["providers_used"]) == {"exa", "zhipu"}
    assert result["synthesis"]["status"] == "disabled"
    assert result["routing_decision"]["stop_reason"] == "sufficient"
    assert len(calls) == 2  # Selection, retrieval, assessment; no pre-search review.
    assert service.validate_minimum_profile()["ok"]


@pytest.mark.asyncio
async def test_tinyfish_registration_can_search_then_fetch_new_evidence(monkeypatch, configured):
    # The TinyFish provider is contributed separately. Exercise its service
    # contract without requiring that PR to be merged before Jev.
    monkeypatch.setitem(service.PROVIDER_PROFILES, "tinyfish", {
        "capability": "web_search", "capabilities": ["web_search", "web_fetch"],
        "strengths": ["web search", "URL extraction"], "exclusions": [],
    })
    original_configured = service._provider_configured
    monkeypatch.setattr(service, "_provider_configured", lambda provider: provider == "tinyfish" or original_configured(provider))
    dispatched = []

    async def judge(self, state, questions, timeout):
        if "available_channels" in state:
            operation = "fetch" if state["evidence"] else "search"
            scores = {
                f"channel_{i}": 0.95 if item["provider"] == "tinyfish" and item["operation"] == operation else 0.01
                for i, item in enumerate(state["available_channels"])
            }
        else:
            scores = {"useful": 0.95, "sufficient": 0.95 if len(dispatched) == 2 else 0.1}
        return answer_payload(questions, scores)

    async def search(query, count):
        dispatched.append(("search", query))
        return [{"url": "https://example.org/tinyfish", "description": "Useful excerpt"}]

    async def fetch(url):
        dispatched.append(("fetch", url))
        return {"ok": True, "content": "Complete page evidence"}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "call_tinyfish_search", search, raising=False)
    monkeypatch.setattr(service, "call_tinyfish_fetch", fetch, raising=False)

    result = await service.search("Find the complete explanation")

    assert result["ok"]
    assert dispatched == [("search", "Find the complete explanation"), ("fetch", "https://example.org/tinyfish")]
    assert "Complete page evidence" in result["content"]
    assert result["providers_used"] == ["tinyfish"]
    assert result["routing_decision"]["stop_reason"] == "sufficient"


@pytest.mark.asyncio
async def test_partial_results_trigger_new_channels_with_failure_and_gap_context(monkeypatch, configured):
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    calls = scripted_jev(
        monkeypatch, [{"exa:search"}, {"zhipu:search"}],
        [{"useful": 0.95, "sufficient": 0.1, "gap_freshness": 0.9}, {"useful": 0.99, "sufficient": 0.95}],
    )

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Old but relevant evidence")]}

    async def zhipu(*args, **kwargs):
        return {"ok": True, "results": [hit("Current evidence", "https://example.org/current")]}

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "zhipu_search", zhipu)
    result = await service.search("Current announcement")

    assert result["ok"]
    assert len(result["routing_decision"]["rounds"]) == 2
    second_selection = calls[2][0]
    assert "zhipu:search" in [item["id"] for item in second_selection["available_channels"]]
    assert any(item["provider"] == "exa" and item["query"] != "Current announcement" for item in second_selection["available_channels"])
    assert second_selection["search_history"][0]["assessment"]["gaps"] == ["freshness"]
    assert second_selection["evidence"][0]["content"] == "Old but relevant evidence"
    assert "Old but relevant evidence" in result["content"]
    assert "Current evidence" in result["content"]


@pytest.mark.asyncio
async def test_provider_failure_advances_to_another_configured_channel(monkeypatch, configured):
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    calls = scripted_jev(monkeypatch, [{"exa:search"}, {"zhipu:search"}], [{"useful": 0.9, "sufficient": 0.9}])

    async def exa(*args, **kwargs):
        return {"ok": False, "error_type": "auth_error", "error": "HTTP 401"}

    async def zhipu(*args, **kwargs):
        return {"ok": True, "results": [hit("Useful result")]}

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "zhipu_search", zhipu)
    result = await service.search("question")

    assert result["ok"]
    assert calls[1][0]["search_history"][0]["attempts"][0]["error_type"] == "auth_error"
    assert [item["provider"] for item in result["provider_attempts"]] == ["exa", "zhipu"]


@pytest.mark.asyncio
@pytest.mark.parametrize("setting,value,stop", [
    ("SMART_SEARCH_JEV_MAX_ROUNDS", "1", "round_limit"),
    ("SMART_SEARCH_FALLBACK_MODE", "off", "followup_disabled"),
])
async def test_search_limits_stop_without_repeating_a_channel(monkeypatch, configured, setting, value, stop):
    monkeypatch.setenv(setting, value)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    calls = scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.9, "sufficient": 0.1}])

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Partial answer")]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question")
    assert result["partial_success"]
    assert result["routing_decision"]["stop_reason"] == stop
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_newly_discovered_url_can_be_fetched_but_unconfigured_readers_cannot(monkeypatch, configured):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("TAVILY_ENABLED", "true")
    seen_candidates = []

    async def request(self, state, questions, timeout):
        if "available_channels" in state:
            candidates = state["available_channels"]
            seen_candidates.append(candidates)
            selected = "fetch" if state["evidence"] else "search"
            scores = {f"channel_{i}": 0.9 if item["operation"] == selected and item["provider"] == ("tavily" if selected == "fetch" else "exa") else 0.01 for i, item in enumerate(candidates)}
        else:
            scores = {"useful": 0.95, "sufficient": 0.95 if len(state["evidence"]) == 2 else 0.1}
        return answer_payload(questions, scores)

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Search excerpt")]}

    async def extract(url):
        assert url == "https://example.org/docs"
        return "Full page evidence"

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "call_tavily_extract", extract)
    result = await service.search("Need the full technical explanation")
    assert result["ok"]
    assert all(item["operation"] == "search" for item in seen_candidates[0])
    assert {item["provider"] for item in seen_candidates[1] if item["operation"] == "fetch"} == {"tavily"}
    assert "Full page evidence" in result["content"]


@pytest.mark.asyncio
async def test_mixed_results_stop_search_and_filter_only_when_enabled(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    calls = scripted_jev(
        monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}] * 2,
        filter_score=lambda group: 0.95 if any("required" in item["content"] for item in group) else 0.01,
    )

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("required answer"), hit("unrelated advertisement", "https://example.org/ad")]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question")
    assert result["ok"]
    assert len(result["routing_decision"]["rounds"]) == 1
    assert "unrelated advertisement" not in json.dumps(result)
    assert result["sources_count"] == 1
    assert result["result_filter"]["removed_chars"] > 0
    assert any("groups" in state for state, _ in calls)


@pytest.mark.asyncio
async def test_binary_filter_checks_both_halves_and_keeps_uncertain_leaves(monkeypatch, configured):
    original = [evidence(text, i) for i, text in enumerate([
        "needed first fact", "noise", "noise", "noise", "noise", "uncertain qualification", "noise", "needed conflicting fact",
    ])]
    inspected = []

    async def request(self, state, questions, timeout):
        groups = state["groups"]
        inspected.extend(groups)
        scores = {f"group_{i}": (0.9 if any("needed" in item["content"] for item in group) else 0.5 if any("uncertain" in item["content"] for item in group) else 0.01) for i, group in enumerate(groups)}
        return answer_payload(questions, scores)

    monkeypatch.setattr(JevClient, "_request", request)
    result, info = await filter_evidence(JevClient(configured, time.monotonic() + 5), "question", original)
    assert [item["content"] for item in result] == ["needed first fact", "uncertain qualification", "needed conflicting fact"]
    assert any(len(group) == 4 and group[0]["id"] == "e0" for group in inspected)
    assert any(len(group) == 4 and group[0]["id"] == "e4" for group in inspected)
    assert original[1]["content"] == "noise"
    assert info["output_results"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "malformed", "all_removed"])
async def test_filter_fails_open_without_losing_original_evidence(monkeypatch, configured, failure):
    original = [evidence("Relevant original material", 1)]

    async def request(self, state, questions, timeout):
        if failure == "timeout":
            raise httpx.ReadTimeout("late response")
        if failure == "malformed":
            return {"answers": {}}
        return answer_payload(questions, {key: 0.0 for key in questions})

    monkeypatch.setattr(JevClient, "_request", request)
    result, info = await filter_evidence(JevClient(configured, time.monotonic() + 5), "question", original)
    assert result == original
    assert info["status"] == "retained"
    assert info["dropped_chunk_ids"] == []


@pytest.mark.asyncio
async def test_filter_bounds_whole_state_with_long_metadata_and_retains_oversized_question(monkeypatch, configured):
    original = [{**evidence("Relevant evidence", 1), "title": "T" * 25000, "url": "https://example.org/" + "u" * 25000}]
    states = []
    async def request(self, state, questions, timeout):
        states.append(state)
        assert len(json.dumps(state, ensure_ascii=False)) <= 20000
        return answer_payload(questions, {key: .99 for key in questions})
    monkeypatch.setattr(JevClient, "_request", request)
    retained, info = await filter_evidence(JevClient(configured, time.monotonic() + 5), "question", original)
    assert states and retained == original and info["status"] == "ok"
    states.clear()
    retained, info = await filter_evidence(JevClient(configured, time.monotonic() + 5), "q" * 21000, original)
    assert not states and retained == original and info["status"] == "retained"


@pytest.mark.asyncio
async def test_filter_outage_returns_evidence_without_another_auto_judgment(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "auto")
    calls = []
    async def request(self, state, questions, timeout):
        phase = "selection" if "available_channels" in state else "filter" if "groups" in state else "assessment"
        calls.append(phase)
        assert "synthesize" not in questions
        if phase == "filter":
            raise ProviderCallError("rate_limit", "Synthetic TypeSafe limit")
        return answer_payload(questions, {key: .99 for key in questions})
    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Useful original evidence")]}
    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr("smart_search.jev_search.ChannelExecutor.synthesis_config", lambda *args: {"model": "test"})
    result = await service.search("question")
    assert calls == ["selection", "assessment", "filter"]
    assert result["ok"] and result["degraded"]
    assert result["synthesis"]["reason"] == "judgment_unavailable"
    assert "Useful original evidence" in result["content"]


@pytest.mark.asyncio
async def test_long_document_filter_sees_tail_content_and_removes_unrelated_paragraphs(monkeypatch, configured):
    text = ("Unrelated advertisement. " * 65 + "\n\n") * 8 + "Required cancellation caveat: CancelledError must be re-raised."
    original = [evidence(text, 1)]
    inspected_sizes = []

    async def request(self, state, questions, timeout):
        inspected_sizes.append(len(json.dumps(state, ensure_ascii=False)))
        scores = {f"group_{i}": 0.95 if any("Required" in item["content"] for item in group) else 0.0 for i, group in enumerate(state["groups"])}
        return answer_payload(questions, scores)

    monkeypatch.setattr(JevClient, "_request", request)
    result, info = await filter_evidence(JevClient(configured, time.monotonic() + 5), "cancellation caveats", original)
    assert "CancelledError must be re-raised" in result[0]["content"]
    assert len(result[0]["content"]) < len(text) // 2
    assert result[0]["url"] == original[0]["url"]
    assert info["input_chunks"] > 4
    assert max(inspected_sizes) < 21000


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, True, -0.1, 1.1, "0.9", float("nan"), float("inf")])
async def test_client_rejects_invalid_probabilities(monkeypatch, configured, invalid):
    async def request(self, state, questions, timeout):
        return {"answers": {"a": {"type": "noul", "noul": invalid}}}

    monkeypatch.setattr(JevClient, "_request", request)
    with pytest.raises(ProviderCallError, match="invalid probability"):
        await JevClient(configured, time.monotonic() + 5).evaluate({}, {"a": {}}, "test")


@pytest.mark.asyncio
async def test_unknown_response_ids_do_not_invent_channels(monkeypatch, configured):
    async def request(self, state, questions, timeout):
        data = answer_payload(questions, {key: 0.01 for key in questions})
        data["answers"]["firecrawl:search"] = {"type": "noul", "noul": 1.0}
        return data

    monkeypatch.setattr(JevClient, "_request", request)
    result = await service.search("question", fallback="off")
    assert result["ok"] is False
    assert result["provider_attempts"] == []
    assert result["routing_decision"]["stop_reason"] == "no_suitable_channels"


@pytest.mark.asyncio
async def test_deadline_cancels_remote_judgment_and_reports_timeout(monkeypatch, configured):
    cancelled = asyncio.Event()

    async def request(self, state, questions, timeout):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(JevClient, "_request", request)
    result = await service.search("question", timeout_seconds=0.03)
    assert result["error_type"] == "timeout"
    assert result["timeout_phase"] == "selection"
    assert cancelled.is_set()
    assert result["provider_attempts"] == []


@pytest.mark.asyncio
async def test_assessment_failure_returns_evidence_with_unknown_status(monkeypatch, configured):
    calls = 0

    async def request(self, state, questions, timeout):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise httpx.ReadTimeout("assessment unavailable")
        return answer_payload(questions, {key: 0.9 for key in questions})

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Original evidence survives")]}

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question")
    assert result["ok"] is True
    assert result["degraded"]
    assert result["evidence_assessment"]["status"] == "unverified"
    assert result["partial_success"]
    assert "Original evidence survives" in result["content"]


@pytest.mark.asyncio
async def test_context7_resolves_actual_library_and_fetches_documents(monkeypatch, configured):
    monkeypatch.setenv("CONTEXT7_API_KEY", "context7-secret")

    async def request(self, state, questions, timeout):
        if "available_channels" in state:
            scores = {f"channel_{i}": 0.95 if item["provider"] == "context7" else 0.01 for i, item in enumerate(state["available_channels"])}
        elif "libraries" in state:
            scores = {"library_0": 0.01, "library_1": 0.95}
        else:
            scores = {"useful": 0.99, "sufficient": 0.95}
        return answer_payload(questions, scores)

    async def library(*args):
        return {"ok": True, "results": [
            {"id": "/zpao/qrcode.react", "title": "QRcode React"},
            {"id": "/reactjs/react.dev", "title": "React"},
        ]}

    async def docs(library_id, query):
        assert library_id == "/reactjs/react.dev"
        return {"ok": True, "content": json.dumps({"content": "Cleanup executes before re-running effects.", "results": []})}

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "context7_library", library)
    monkeypatch.setattr(service, "context7_docs", docs)
    result = await service.search("React useEffect cleanup")
    assert result["ok"]
    assert "Cleanup executes" in result["content"]
    assert "qrcode" not in result["content"]
    assert result["sources"][0]["url"] == "context7:/reactjs/react.dev"


@pytest.mark.parametrize("key,value", [
    ("SMART_SEARCH_JEV_MAX_ROUNDS", "0"), ("SMART_SEARCH_JEV_MAX_ROUNDS", "2.5"),
    ("SMART_SEARCH_JEV_MAX_CHANNELS", "100"), ("SMART_SEARCH_JEV_ROUTE_THRESHOLD", "nan"),
    ("SMART_SEARCH_JEV_TIMEOUT_SECONDS", "inf"), ("SMART_SEARCH_JEV_FILTER_RESULTS", "sometimes"),
    ("SMART_SEARCH_JEV_FILTER_THRESHOLD", "0.9"), ("TYPESAFE_API_URL", "https://user:secret@example.org"),
])
def test_config_rejects_unsafe_or_unbounded_values(monkeypatch, configured, key, value):
    with pytest.raises(ValueError):
        service.config.set_config_value(key, value)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        service.config.jev_settings()
    assert service.config.get_config_info()["config_parameter_errors"]


def test_config_masks_key_and_environment_overrides_file(monkeypatch, configured):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    service.config.set_config_value("TYPESAFE_API_KEY", "secret-file-key")
    service.config.set_config_value("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    assert service.config.jev_settings().filter_results
    assert "secret-file-key" not in json.dumps(service.config.get_config_info())
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "false")
    assert not service.config.jev_settings().filter_results


def test_explicit_provider_filter_and_cooldown_exclude_candidates(monkeypatch, configured):
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    assert [item["provider"] for item in available_channels(service, "question", [], "exa")] == ["exa"]
    monkeypatch.setattr(service, "_provider_health_status", lambda provider: {"state": "cooldown" if provider == "exa" else "closed"})
    assert [item["provider"] for item in available_channels(service, "question", [])] == ["zhipu"]


@pytest.mark.parametrize("query,expected", [
    ("请读取 https://www.iana.org/help/example-domains，说明用途。", ["https://www.iana.org/help/example-domains"]),
    ("请读取 https://example.org/中文路径？再核验 https://example.org/second。", ["https://example.org/中文路径", "https://example.org/second"]),
    ("请看 https://example.org/search?q=asyncio&lang=zh-CN", ["https://example.org/search?q=asyncio&lang=zh-CN"]),
])
def test_chinese_sentence_punctuation_does_not_become_part_of_fetch_url(query, expected):
    assert service._extract_urls(query) == expected


@pytest.mark.asyncio
async def test_missing_jev_key_is_config_error_without_search(monkeypatch, configured):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    result = await service.search("question", fallback="off")
    assert result["error_type"] == "config_error"
    assert result["provider_attempts"] == []


@pytest.mark.asyncio
async def test_real_http_contract_retries_throttling_and_masks_errors(monkeypatch, configured):
    requests = []
    pauses = []
    original_client = httpx.AsyncClient

    async def handler(request):
        requests.append(request)
        assert request.url == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["Authorization"] == "Bearer jev-test-secret"
        body = json.loads(request.content)
        assert body["state"] == {"input": "known evidence"}
        if len(requests) == 1:
            return httpx.Response(429)
        if len(requests) == 2:
            return httpx.Response(529)
        return httpx.Response(200, json=answer_payload(body["questions"], {"relevant": 0.9}))

    async def sleep(delay):
        pauses.append(delay)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(asyncio, "sleep", sleep)
    client = JevClient(configured, time.monotonic() + 5)
    result = await client.evaluate({"input": "known evidence"}, {"relevant": noul("Relevant?", "yes", "no")}, "test")
    assert result == {"relevant": 0.9}
    assert pauses == [0.5, 1.0]

    async def rejected(request):
        return httpx.Response(401, text="Invalid credential jev-test-secret")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(rejected), **kwargs))
    with pytest.raises(ProviderCallError) as caught:
        await client.evaluate({}, {"relevant": noul("Relevant?", "yes", "no")}, "test")
    assert caught.value.error_type == "auth_error"
    assert "jev-test-secret" not in str(caught.value)
    assert "jev-test-secret" not in json.dumps(client.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,probability,should_synthesize", [
    ("true", None, True), ("false", None, False),
    ("auto", 0.95, True), ("auto", 0.05, False), ("auto", 0.5, False),
])
async def test_synthesis_modes_use_only_filtered_evidence(monkeypatch, configured, mode, probability, should_synthesize):
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", mode)
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    calls = scripted_jev(
        monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}] * 2,
        filter_score=lambda group: 0.95 if any("needed" in item["content"] for item in group) else 0.0,
        synthesis_score=probability,
    )
    payloads = []

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("needed fact"), hit("discard this advertisement", "https://example.org/ad")]}

    async def complete(self, headers, payload, ctx=None):
        payloads.append(payload)
        return "Answer based on the needed fact."

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "_execute_with_transport_fallback", complete)
    result = await service.search("question")
    assert result["ok"]
    assert result["synthesis"]["mode"] == mode
    assert result["synthesis"]["enabled"] is should_synthesize
    assert len(payloads) == int(should_synthesize)
    if should_synthesize:
        assert result["model"] == "summary-model"
        assert "tools" not in payloads[0]
        assert "needed fact" in json.dumps(payloads[0])
        assert "advertisement" not in json.dumps(payloads[0])
    else:
        assert "needed fact" in result["content"]
    decisions = [state for state, questions in calls if "synthesize" in questions]
    if mode == "auto":
        assert len(decisions) == 1
        assert "needed fact" in json.dumps(decisions[0])
        assert "advertisement" not in json.dumps(decisions[0])
        assert calls[-1][0] == decisions[0]  # The decision follows filtering.
        assert result["synthesis"]["probability"] == probability
        assert result["synthesis"]["decision_source"] == "jev"
    else:
        assert not decisions
    assert "summary-secret" not in json.dumps(result)
    assert result["providers_used"] == ["exa"]


@pytest.mark.asyncio
@pytest.mark.parametrize("api_mode", ["chat-completions", "responses"])
@pytest.mark.parametrize("providers", ["auto", "exa,jev-synthesis"])
async def test_dedicated_synthesis_ignores_main_model_and_request_override(monkeypatch, configured, api_mode, providers):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_MODE", api_mode)
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    monkeypatch.setenv("XAI_MODEL", "main-model")
    scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}])
    requests = []

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Independent evidence")]}

    async def complete(self, headers, payload, ctx=None):
        requests.append((self.api_url, self.api_key, self.model, self.api_mode, payload))
        return "Dedicated answer"

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "_execute_with_transport_fallback", complete)
    result = await service.search("question", model="request-model", providers=providers)

    assert result["ok"] and result["content"] == "Dedicated answer"
    assert result["model"] == result["synthesis"]["model"] == "summary-model"
    assert len(requests) == 1
    url, key, model, mode, payload = requests[0]
    assert (url, key, model, mode) == ("https://summary.example.org/v1", "summary-secret", "summary-model", api_mode)
    assert "tools" not in payload
    assert "main-secret" not in json.dumps(result)
    assert "summary-secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_incomplete_dedicated_synthesis_never_calls_main_model(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}])
    calls = []

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Evidence remains available")]}

    async def complete(*args, **kwargs):
        calls.append(True)
        return "Unexpected answer"

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "_execute_with_transport_fallback", complete)
    result = await service.search("question")

    assert result["ok"] and not calls
    assert result["synthesis"]["status"] == "failed"
    assert result["synthesis"]["error_type"] == "parameter_error"
    assert "Evidence remains available" in result["content"]


@pytest.mark.asyncio
async def test_synthesis_failure_preserves_returned_evidence(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}])
    model_calls = []

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Evidence remains available without a main model")]}

    async def complete(*args, **kwargs):
        model_calls.append(True)
        return "Unexpected answer"

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "_execute_with_transport_fallback", complete)
    result = await service.search("question")
    assert result["ok"]
    assert not model_calls
    assert result["synthesis"]["status"] == "failed"
    assert "Evidence remains available" in result["content"]
    assert result["warnings"]


@pytest.mark.asyncio
async def test_strict_mode_does_not_treat_model_answer_and_bare_citation_as_proof(monkeypatch, configured):
    scripted_jev(monkeypatch, [], [{"useful": 0.99, "sufficient": 0.99}])
    items = [
        {**evidence("A generated answer", 1), "kind": "model_answer"},
        {**evidence("A page title", 2), "kind": "citation"},
    ]
    assessment = await assess_evidence(JevClient(configured, time.monotonic() + 5), "verify this claim", items, "strict")
    assert assessment["useful"]
    assert not assessment["sufficient"]


@pytest.mark.asyncio
async def test_strict_filtering_cannot_replace_source_evidence_with_citations(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    scripted_jev(
        monkeypatch, [{"exa:search"}], [{"useful": 0.99, "sufficient": 0.99}, {"useful": 0.99, "sufficient": 0.01}],
        filter_score=lambda group: 0.95 if any("Useful" in item["content"] for item in group) else 0.0,
    )

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [
            {**hit("Unrelated source passage"), "kind": "source"},
            {**hit("Useful generated summary", ""), "kind": "model_answer"},
            {**hit("Useful page title", "https://example.org/citation"), "kind": "citation"},
        ]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("verify this claim", validation="strict")

    assert result["ok"] is False
    assert result["error_type"] == "evidence_error"
    assert result["partial_success"] is True
    assert result["evidence_assessment"]["sufficient"] is False
    assert result["routing_decision"]["stop_reason"] == "filtered_sources_insufficient"
    assert "Useful generated summary" in result["content"]
    assert [item["kind"] for item in result["sources"]] == ["citation"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,key_name,url_name", [
    ("openai-compatible", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_API_URL"),
    ("xai-responses", "XAI_API_KEY", "XAI_API_URL"),
])
async def test_main_search_credential_change_and_reset_clear_jev_cooldown(monkeypatch, configured, provider, key_name, url_name):
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "300")
    monkeypatch.setenv(key_name, "wrong-key")
    monkeypatch.setenv(url_name, "https://api.example.org/v1")
    monkeypatch.delenv("EXA_API_KEY")
    scripted_jev(monkeypatch, [{f"{provider}:search"}], [])

    async def rejected(self, query, platform="", ctx=None):
        raise ProviderCallError("auth_error", "Rejected credential")

    provider_type = service.OpenAICompatibleSearchProvider if provider == "openai-compatible" else service.XAIResponsesSearchProvider
    monkeypatch.setattr(provider_type, "search", rejected)
    failed = await service.search("question", providers=provider)

    assert failed["ok"] is False
    assert not available_channels(service, "question", [])
    monkeypatch.setenv(key_name, "corrected-key")
    assert [item["provider"] for item in available_channels(service, "question", [])] == [provider]

    service._record_provider_result(provider, "error", "auth_error", "Rejected credential")
    assert not available_channels(service, "question", [])
    assert service.reset_provider_health([provider])["ok"] is True
    assert [item["provider"] for item in available_channels(service, "question", [])] == [provider]


@pytest.mark.asyncio
async def test_research_requires_read_evidence_and_keeps_the_report_contract(monkeypatch, configured, tmp_path):
    monkeypatch.setenv("TINYFISH_API_KEY", "tinyfish-fixture")

    async def judge(self, state, questions, timeout):
        if "available_channels" in state:
            scores = {f"channel_{i}": 0.95 if (not state["evidence"] and item["id"] == "exa:search") or
                      (state["evidence"] and item["provider"] == "tinyfish" and item["operation"] == "fetch") else 0.01
                      for i, item in enumerate(state["available_channels"])}
        else:
            assert all(item["read"] for item in state["evidence"])
            scores = {"useful": 0.95, "sufficient": 0.95}
        return answer_payload(questions, scores)

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("discovery-snippet-only")]}

    async def fetch(url):
        return {"ok": True, "content": "unique-evidence-body-marker"}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "call_tinyfish_fetch", fetch)
    result = await service.research("question", evidence_dir=str(tmp_path / "evidence"))
    assert result["ok"]
    assert result["mode"] == "deep_research_execution"
    assert (tmp_path / "evidence" / "report.json").exists()
    assert (tmp_path / "evidence" / "00-plan.json").exists()
    assert result["evidence_items"][0]["content"] == "unique-evidence-body-marker"
    assert result["citations"][0]["url"] == "https://example.org/docs"
    assert "discovery-snippet-only" not in result["final_answer"]


@pytest.mark.asyncio
async def test_slow_channel_is_cancelled_while_other_evidence_is_retained(monkeypatch, configured):
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")
    scripted_jev(monkeypatch, [{"exa:search", "zhipu:search"}], [{"useful": 0.95, "sufficient": 0.95}])
    cancelled = asyncio.Event()

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Fast useful evidence")]}

    async def zhipu(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service, "zhipu_search", zhipu)
    result = await service.search("question", timeout_seconds=0.1)
    assert result["ok"]
    assert result["timeout_phase"] == "retrieval"
    assert "Fast useful evidence" in result["content"]
    assert cancelled.is_set()


def stub_doctor_probes(monkeypatch, *, rejected=False):
    async def probe(*args, **kwargs):
        return {"status": "ok", "message": "fixture"}

    async def request(self, state, questions, timeout):
        if rejected:
            raise ProviderCallError("auth_error", "TypeSafe rejected credentials")
        return answer_payload(questions, {key: 0.99 for key in questions})

    for name in (
        "_test_exa_connection", "_test_tavily_connection", "_test_jina_connection",
        "_test_zhipu_connection", "_test_zhipu_mcp_connection", "_test_context7_connection",
    ):
        monkeypatch.setattr(service, name, probe)
    monkeypatch.setattr(JevClient, "_request", request)


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected", [False, True])
@pytest.mark.parametrize("mode", ["false", "auto"])
async def test_doctor_checks_jev_without_requiring_a_main_model(monkeypatch, configured, rejected, mode):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", mode)
    stub_doctor_probes(monkeypatch, rejected=rejected)
    result = await service.doctor()
    assert result["ok"] is not rejected
    assert result["intent_router_status"]["mode"] == "jev"
    if rejected:
        assert result["error_type"] == "auth_error"
    else:
        assert result["primary_connection_test"]["status"] == "not_required"


@pytest.mark.asyncio
async def test_doctor_checks_dedicated_synthesis_independently_of_main_model(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")

    async def synthesis_probe(provider_config):
        assert provider_config["provider"] == "jev-synthesis"
        assert provider_config["model"] == "summary-model"
        return {"status": "ok", "message": "fixture"}

    stub_doctor_probes(monkeypatch)
    monkeypatch.setattr(service, "_safe_test_main_provider_connection", synthesis_probe)

    result = await service.doctor()
    assert result["ok"]
    assert result["jev_synthesis_connection_test"]["status"] == "ok"
    assert result["primary_connection_test"]["status"] == "not_required"
    assert result["main_search_connection_tests"] == {}
    assert "summary-secret" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("dedicated_model,expected_status", [
    ("", "not_configured"), ("summary-model", "config_error"),
])
async def test_doctor_rejects_missing_dedicated_synthesis_even_with_main_model(monkeypatch, configured, dedicated_model, expected_status):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    if dedicated_model:
        monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", dedicated_model)

    stub_doctor_probes(monkeypatch)

    result = await service.doctor()
    assert not result["ok"] and result["error_type"] == "config_error"
    assert result["jev_synthesis_connection_test"]["status"] == expected_status
    assert result["primary_connection_test"]["status"] == "not_required"
    assert result["main_search_connection_tests"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected_status,expected_ok", [
    ("true", "config_error", False), ("auto", "skipped", True),
])
async def test_doctor_skips_disabled_dedicated_synthesis_provider(monkeypatch, configured, mode, expected_status, expected_ok):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", mode)
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", "jev-synthesis")
    stub_doctor_probes(monkeypatch)

    async def unexpected_probe(provider_config):
        raise AssertionError("Disabled synthesis provider must not be probed")

    monkeypatch.setattr(service, "_safe_test_main_provider_connection", unexpected_probe)
    result = await service.doctor()
    assert result["ok"] is expected_ok
    assert result["jev_synthesis_connection_test"]["status"] == expected_status
    assert result["jev_synthesis_connection_test"]["reason"] == "provider_disabled"


@pytest.mark.asyncio
@pytest.mark.parametrize("judgment,error_type", [
    (httpx.ReadTimeout("Jev unavailable"), "timeout"), ("invalid", "parse_error"),
])
async def test_auto_synthesis_judgment_failure_keeps_evidence(monkeypatch, configured, judgment, error_type):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "auto")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}], synthesis_score=judgment)
    model_calls = []

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Retained evidence after judgment failure")]}

    async def complete(*args, **kwargs):
        model_calls.append(True)
        return "Unexpected answer"

    monkeypatch.setattr(service, "exa_search", exa)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "_execute_with_transport_fallback", complete)
    result = await service.search("question")
    assert result["ok"]
    assert not model_calls
    assert "Retained evidence after judgment failure" in result["content"]
    assert result["synthesis"]["status"] == "decision_failed"
    assert result["synthesis"]["error_type"] == error_type
    assert result["synthesis"]["decision_source"] == "jev"
    assert result["warnings"]
    if error_type == "timeout":
        assert result["timeout_phase"] == "synthesis_decision"


@pytest.mark.asyncio
@pytest.mark.parametrize("restriction", ["missing", "disabled", "provider_filter"])
async def test_auto_synthesis_skips_without_an_allowed_synthesis_model(monkeypatch, configured, restriction):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "auto")
    monkeypatch.setenv("XAI_API_KEY", "main-secret")
    if restriction != "missing":
        monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_KEY", "summary-secret")
        monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://summary.example.org/v1")
        monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIS_MODEL", "summary-model")
    if restriction == "disabled":
        monkeypatch.setenv("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", "jev-synthesis")
    calls = scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.95, "sufficient": 0.95}])

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Useful evidence without synthesis")]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question", providers="exa" if restriction == "provider_filter" else "auto")
    assert result["ok"]
    assert len(calls) == 2
    assert result["synthesis"]["reason"] == "no_allowed_synthesis_model"
    assert result["synthesis"]["enabled"] is False
    assert "Useful evidence" in result["content"]


@pytest.mark.asyncio
async def test_auto_synthesis_does_not_run_without_useful_evidence(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "auto")
    monkeypatch.setenv("SMART_SEARCH_JEV_MAX_ROUNDS", "1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "grok-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.org/v1")
    calls = scripted_jev(monkeypatch, [{"exa:search"}], [{"useful": 0.01, "sufficient": 0.01}])

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("Irrelevant source")]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question")
    assert not result["ok"]
    assert len(calls) == 2
    assert result["synthesis"]["reason"] == "no_confirmed_useful_evidence"


@pytest.mark.parametrize("saved,expected", [
    (True, "true"), (False, "false"), ("true", "true"), ("false", "false"),
    ("auto", "auto"), (" AUTO ", "auto"), ("yes", "true"), ("0", "false"),
])
def test_synthesis_mode_loads_existing_booleans_and_new_enum(monkeypatch, configured, saved, expected):
    service.config._save_config_file({"SMART_SEARCH_JEV_SYNTHESIZE": saved})
    assert service.config.jev_settings().synthesis_mode == expected
    assert service.config.get_config_info()["SMART_SEARCH_JEV_SYNTHESIZE"] == expected
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "auto")
    assert service.config.jev_settings().synthesis_mode == "auto"


@pytest.mark.parametrize("invalid", ["automatic", "", "2"])
def test_invalid_synthesis_mode_is_rejected(configured, invalid):
    with pytest.raises(ValueError, match="true, false, or auto"):
        service.config.set_config_value("SMART_SEARCH_JEV_SYNTHESIZE", invalid)


@pytest.mark.parametrize("key,value", [
    ("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "file:///private/summary"),
    ("SMART_SEARCH_JEV_SYNTHESIS_API_URL", "https://user:pass@summary.example.org/v1"),
    ("SMART_SEARCH_JEV_SYNTHESIS_API_MODE", "unsupported"),
])
def test_invalid_dedicated_synthesis_connection_is_rejected(configured, key, value):
    with pytest.raises(ValueError, match="Invalid SMART_SEARCH_JEV_SYNTHESIS_"):
        service.config.set_config_value(key, value)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing_key", "auth_error", "no_selection"])
async def test_jev_failure_uses_only_allowed_local_capability_fallback(monkeypatch, configured, failure):
    if failure == "missing_key":
        monkeypatch.delenv("TYPESAFE_API_KEY")
    calls = []

    async def judge(self, state, questions, timeout):
        if failure == "auth_error":
            raise ProviderCallError("auth_error", "rejected")
        return answer_payload(questions, {})

    async def exa(query, **kwargs):
        calls.append(query)
        return {"ok": True, "results": [hit("Unverified but retained evidence")]}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("general question", providers="exa")
    assert calls and result["degraded"]
    assert result["routing_decision"]["rounds"][0]["selection_source"] == "capability_fallback"
    assert result["providers_used"] == ["exa"]
    assert "jev-test-secret" not in json.dumps(result)
    if failure != "no_selection":
        assert result["ok"] and result["partial_success"]
        assert result["evidence_assessment"]["status"] == "unverified"


@pytest.mark.asyncio
async def test_gap_can_trigger_a_new_query_on_the_same_engine(monkeypatch, configured):
    queries = []

    async def judge(self, state, questions, timeout):
        if "available_channels" in state:
            scores = {f"channel_{i}": 0.95 if (not queries and item["id"] == "exa:search") or
                      (queries and "latest official news" in item["query"]) else 0.01
                      for i, item in enumerate(state["available_channels"])}
        else:
            scores = {"useful": 0.95, "sufficient": 0.95 if len(queries) > 1 else 0.1, "gap_freshness": 0.9 if len(queries) == 1 else 0}
        return answer_payload(questions, scores)

    async def exa(query, **kwargs):
        queries.append(query)
        return {"ok": True, "results": [hit(f"evidence-{len(queries)}", f"https://example.org/{len(queries)}")]}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("Company announcement")
    assert result["ok"]
    assert len(queries) == 2 and queries[0] != queries[1]
    assert "latest official news" in queries[1]
    assert len({attempt["channel_id"] for attempt in result["provider_attempts"]}) == 2


@pytest.mark.asyncio
async def test_filtering_rechecks_sufficiency_of_the_remaining_source(monkeypatch, configured):
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    scripted_jev(monkeypatch, [{"exa:search"}], [
        {"useful": 0.99, "sufficient": 0.99}, {"useful": 0.01, "sufficient": 0.01, "gap_direct_answer": 0.9}],
        filter_score=lambda group: 0.9 if any("noise" in item["content"] for item in group) else 0.0)

    async def exa(*args, **kwargs):
        return {"ok": True, "results": [hit("needed answer", "https://example.org/answer"), hit("noise", "https://example.org/noise")]}

    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question", validation="strict")
    assert not result["ok"] and not result["evidence_assessment"]["sufficient"]
    assert result["routing_decision"]["stop_reason"] == "filtered_evidence_insufficient"


@pytest.mark.asyncio
async def test_no_provider_is_started_after_selection_exhausts_deadline(monkeypatch, configured):
    from smart_search import jev_search
    exhausted, calls = False, []

    async def select(client, query, candidates, **kwargs):
        nonlocal exhausted
        exhausted = True
        return [candidates[0]], {candidates[0]["id"]: 0.9}

    async def exa(*args, **kwargs):
        calls.append(True)
        return {"ok": True, "results": [hit("too late")]}

    monkeypatch.setattr(jev_search, "select_channels", select)
    monkeypatch.setattr(service.SearchBudget, "remaining_seconds", lambda self: 0 if exhausted else 10)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("question")
    assert not calls
    assert result["routing_decision"]["stop_reason"] == "deadline"


def test_preview_is_bounded_even_with_many_large_metadata_fields():
    from smart_search.jev import evidence_preview
    rows = [{**evidence('"\\' * 10000, i), "url": "https://example.org/" + "x" * 2000, "title": "y" * 1000} for i in range(1000)]
    preview = evidence_preview(rows)
    assert len(json.dumps(preview, ensure_ascii=False)) <= 20000
    assert preview[-1]["omitted_results"] > 0
    assert any(item["truncated"] for item in preview)


def test_judge_preview_can_see_relevant_passages_late_in_long_page():
    from smart_search.jev import evidence_preview
    content = ("Navigation and unrelated reference\n\n" * 400 +
               "asyncio Task cancel() throws CancelledError inside the coroutine.\n\n" + "More index entries\n\n" * 100)
    preview = evidence_preview([{"id": "e1", "provider": "tinyfish", "content": content}], query="asyncio Task cancel CancelledError")
    assert "throws CancelledError" in preview[0]["content"]
    assert preview[0]["truncated"]
    assert len(json.dumps(preview, ensure_ascii=False)) <= 20000


@pytest.mark.asyncio
async def test_local_route_does_not_call_jev_or_require_its_key(monkeypatch, configured):
    monkeypatch.delenv("TYPESAFE_API_KEY")

    async def unexpected(*args, **kwargs):
        pytest.fail("A local route preview must not call TypeSafe")

    monkeypatch.setattr(JevClient, "_request", unexpected)
    result = await service.route("React API", mode="jev", allow_remote=False)
    assert result["ok"] and result["remote_judgment_required"]
    assert result["selected_channels"] == []


@pytest.mark.asyncio
async def test_preferred_provider_is_visible_and_breaks_equal_suitability_ties(monkeypatch, configured):
    monkeypatch.setenv("CONTEXT7_API_KEY", "fixture-context7")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", "context7,exa")
    seen = []

    async def judge(self, state, questions, timeout):
        seen.extend(state["available_channels"])
        return answer_payload(questions, {key: 0.9 for key in questions})

    monkeypatch.setattr(JevClient, "_request", judge)
    result = await service.route("React docs", mode="jev", allow_remote=True)
    assert result["selected_channels"][0]["provider"] == "context7"
    assert next(item for item in seen if item["provider"] == "context7")["preference_rank"] == 0


@pytest.mark.asyncio
async def test_research_preflight_failure_keeps_report_fields(monkeypatch, configured, tmp_path):
    monkeypatch.delenv("EXA_API_KEY")
    result = await service.research("question", evidence_dir=str(tmp_path / "evidence"))
    assert not result["ok"] and result["error_type"] == "config_error"
    assert result["citations"] == result["evidence_items"] == []
    assert result["gap_check"]["status"] == "failed"
    assert result["research_plan"]["evidence_policy"] == "fetch_before_claim"
    assert (tmp_path / "evidence" / "summary.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("level,channels,rounds", [("quick", 1, 2), ("standard", 2, 3), ("deep", 3, 3)])
async def test_research_budget_limits_are_distinct(monkeypatch, configured, tmp_path, level, channels, rounds):
    monkeypatch.setenv("TINYFISH_API_KEY", "fixture-tinyfish")

    async def judge(self, state, questions, timeout):
        if "available_channels" in state:
            scores = {f"channel_{i}": 0.95 if item["operation"] == "fetch" else 0.01
                      for i, item in enumerate(state["available_channels"])}
        else:
            scores = {"useful": 0.95, "sufficient": 0.95}
        return answer_payload(questions, scores)

    async def fetch(url):
        return {"ok": True, "content": "Actual source text"}

    monkeypatch.setattr(JevClient, "_request", judge)
    monkeypatch.setattr(service, "call_tinyfish_fetch", fetch)
    result = await service.research("Read https://example.org", budget=level, evidence_dir=str(tmp_path))
    assert result["ok"]
    assert result["routing_decision"]["limits"]["channels_per_round"] == channels
    assert result["routing_decision"]["limits"]["rounds"] == rounds
    assert result["budget"] == level
