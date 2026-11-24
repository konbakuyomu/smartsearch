"""Regression contracts for discovery -> reading -> assessment -> delivery."""

import asyncio
import time
from dataclasses import replace

import pytest
import httpx

from smart_search import service
from smart_search.jev import JevClient, evidence_preview, select_channels
from smart_search.jev_search import ChannelExecutor, available_channels
from smart_search.provider_errors import ProviderCallError


@pytest.mark.asyncio
async def test_eligible_read_is_not_starved_by_two_higher_search_scores(monkeypatch):
    client = JevClient(replace(service.config.jev_settings(), max_channels=2), time.monotonic() + 30)

    async def evaluate(*args):
        return {"channel_0": .57, "channel_1": .53, "channel_2": .52}

    monkeypatch.setattr(client, "evaluate", evaluate)
    candidates = [{"id": str(i), "operation": op, "url": "https://example.org/paper" if op == "fetch" else ""}
                  for i, op in enumerate(["search", "search", "fetch"])]
    selected, _ = await select_channels(client, "verify paper", candidates, evidence=[], history=[], validation="balanced", require_read=True)
    assert any(item["operation"] == "fetch" for item in selected)
    assert len(selected) == 2


def configure_fetch(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "0")


def test_url_pool_ranks_before_limiting_and_is_arrival_order_independent(monkeypatch):
    configure_fetch(monkeypatch)
    sources = [{"url": f"https://example.org/{i}", "title": "Unrelated directory", "content": "navigation"} for i in range(5)]
    sources.append({"url": "https://journals.example/paper", "title": "Gallium indium ultrasound solidification", "content": "Ga-In ultrasound experiment"})
    def urls(items):
        return {c["url"] for c in available_channels(service, "gallium indium ultrasound", items) if c["operation"] == "fetch"}
    assert "https://journals.example/paper" in urls(sources)
    assert urls(sources) == urls(list(reversed(sources)))
    candidates = available_channels(service, "gallium indium ultrasound", sources)
    candidate = next(c for c in candidates if c["url"] == "https://journals.example/paper")
    assert candidate["source"]["title"] == "Gallium indium ultrasound solidification"
    assert "Ga-In" in candidate["source"]["snippet"]


def test_explicit_only_url_scope_prevents_unrelated_search_and_fetch(monkeypatch):
    configure_fetch(monkeypatch)
    channels = available_channels(service, "仅使用这个链接，不要替换来源 https://example.invalid/paper", [{"url": "https://elsewhere.org/answer"}])
    assert channels
    assert all(c["operation"] == "fetch" and c["url"] == "https://example.invalid/paper" for c in channels)


def test_relevant_middle_source_and_body_passage_are_visible():
    items = [{"id": str(i), "provider": "test", "content": "Navigation menu " * 200, "url": f"https://e.org/{i}"} for i in range(20)]
    items[9]["content"] += "\n\nGa-40wt.%In ultrasound changes the solidification experiment.\n\n" + "References\n" * 300
    preview = evidence_preview(items, query="Ga-40wt.%In ultrasound solidification")
    assert any("Ga-40wt.%In" in i["content"] for i in preview)
    assert sum(i.get("omitted_results", 0) for i in preview) > 0


def test_evidence_report_contains_requested_fact_beyond_navigation():
    body = "Navigation [Home](https://example.org)\n\n" * 100 + "Python 3.15.1 release date: October 25, 2026. Second maintenance release."
    report = service._evidence_only_synthesis("Python 3.15.1 release date and maintenance release", [{"content": body, "url": "https://example.org/release", "title": "Python release", "provider": "test"}], [])
    assert "October 25, 2026" in report


@pytest.mark.asyncio
async def test_context7_resolves_library_name_separately_and_rejects_unrelated(monkeypatch):
    seen = []

    async def library(name, query):
        seen.append(name)
        return {"ok": True, "results": [{"id": "/cleanup/tool", "title": "Artifactory Cleanup", "description": "Removes artifacts"}]}

    async def docs(*args):
        pytest.fail("An unrelated first library must not be read")

    monkeypatch.setattr(service, "context7_library", library)
    monkeypatch.setattr(service, "context7_docs", docs)
    client = JevClient(replace(service.config.jev_settings(), api_key=""), time.monotonic() + 30)
    executor = ChannelExecutor(service, client)
    with pytest.raises(ProviderCallError):
        await executor._context7("React 的 useEffect 清理函数如何处理依赖？")
    assert seen == ["React"]


@pytest.mark.asyncio
async def test_fetch_fallback_respects_allowlist(monkeypatch):
    configure_fetch(monkeypatch)
    calls = []

    async def empty(url):
        calls.append("tavily")
        return ""

    async def scrape(url):
        calls.append("firecrawl")
        return "Full source evidence"

    monkeypatch.setattr(service, "call_tavily_extract", empty)
    monkeypatch.setattr(service, "call_firecrawl_scrape", scrape)
    result, attempts = await service._run_web_fetch_fallback("https://e.org/paper", allowed_providers={"tavily"}, deadline=time.monotonic() + 10)
    assert result is None
    assert calls == ["tavily"]
    result, attempts = await service._run_web_fetch_fallback("https://e.org/paper", allowed_providers={"tavily", "firecrawl"}, deadline=time.monotonic() + 10)
    assert result["provider"] == "firecrawl"
    assert [a["status"] for a in attempts] == ["empty", "ok"]


def stub_research_judge(monkeypatch):
    async def request(self, state, questions, timeout):
        scores = {}
        for key in questions:
            if key.startswith("channel_"):
                channel = state["available_channels"][int(key.split("_")[1])]
                scores[key] = .99 if channel["operation"] == "fetch" and channel["provider"] == "tavily" else .98 if channel["provider"] == "firecrawl" and channel["operation"] == "search" else .01
            else:
                scores[key] = .95 if key in {"useful", "sufficient", "synthesize"} else .01
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in scores.items()}}
    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-jev")


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_primary", [False, True])
async def test_research_keeps_slow_read_and_uses_same_url_fallback(monkeypatch, tmp_path, empty_primary):
    from smart_search import jev_search
    configure_fetch(monkeypatch)
    stub_research_judge(monkeypatch)
    monkeypatch.setattr(jev_search, "STRAGGLER_GRACE_SECONDS", .01)
    calls = []

    async def read(url):
        await asyncio.sleep(.15)
        calls.append(("tavily", url))
        return "" if empty_primary else "Verified Ga-In original experimental result."

    async def scrape(url):
        calls.append(("firecrawl", url))
        return "Verified Ga-In original experimental result."

    async def search(query, count):
        return [{"url": "https://e.org/other", "content": "Fast discovery snippet"}]

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(service, "call_firecrawl_scrape", scrape)
    monkeypatch.setattr(service, "call_firecrawl_search", search)
    result = await service.research("Read https://e.org/paper to verify Ga-In", budget="standard", evidence_dir=str(tmp_path))
    assert result["completion"]["answer"] == "complete"
    assert result["completion"]["unique_read_sources"] == 1
    assert result["evidence_items"][0]["url"] == "https://e.org/paper"
    assert not any(a["status"] == "cancelled" for a in result["provider_attempts"])
    if empty_primary:
        assert calls == [("tavily", "https://e.org/paper"), ("firecrawl", "https://e.org/paper")]
        assert result["evidence_items"][0]["provider"] == "firecrawl"
        assert [(a["provider"], a["status"]) for a in result["provider_attempts"] if a["operation"] == "fetch"] == [("tavily", "empty"), ("firecrawl", "ok")]


@pytest.mark.asyncio
async def test_synthesis_failure_is_partial_even_with_closed_evidence(monkeypatch, tmp_path):
    configure_fetch(monkeypatch)
    stub_research_judge(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "true")
    async def read(url):
        return "Fact from the original source."
    async def synthesize(*args):
        raise ProviderCallError("network_error", "Controlled synthesis outage")
    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    result = await service.research("只读取 https://e.org/paper", budget="standard", evidence_dir=str(tmp_path))
    assert result["ok"]  # Compatibility: retrieval succeeded.
    assert result["gap_check"]["status"] == "closed"
    assert result["completion"]["answer"] == "partial"
    assert result["degraded"] and result["partial_success"]
    assert "Fact from the original source" in result["content"]


@pytest.mark.parametrize("headers, body, expected", [
    ({"retry-after-ms": "475"}, "", .475),
    ({"retry-after": "0.25"}, "", .25),
    ({}, '{"error":{"message":"Please try again in 320ms."}}', .32),
    ({"retry-after": "NaN"}, "invalid hint", None),
])
def test_retry_hints_preserved_for_transport_and_cooldown(headers, body, expected, tmp_path):
    from smart_search.provider_errors import retry_delay, classify_provider_exception
    from smart_search.provider_health import ProviderHealthStore
    from smart_search.providers.openai_compatible import _WaitWithRetryAfter
    response = httpx.Response(429, headers=headers, text=body, request=httpx.Request("POST", "https://e.org"))
    assert retry_delay(response) == (pytest.approx(expected) if expected is not None else None)
    assert _WaitWithRetryAfter(1, 5)._parse_retry_after(response) == (pytest.approx(expected) if expected is not None else None)
    if expected is not None:
        kind, message = classify_provider_exception(httpx.HTTPStatusError("limited", request=response.request, response=response))
        store = ProviderHealthStore(tmp_path / "health.json", cooldown_seconds=300, clock=lambda: 100)
        status = store.record_failure("openai-compatible", "test", kind, message)
        assert status["cooldown_remaining_seconds"] == expected


@pytest.mark.asyncio
async def test_provider_versions_are_one_source_and_conflicts_remain_visible(monkeypatch):
    from smart_search.jev import assess_evidence
    from smart_search.jev_search import _append_evidence
    items = []
    for provider, content in [("tavily", "Reported temperature is 40 C."), ("firecrawl", "Reported temperature is 50 C.")]:
        _append_evidence(items, [{"provider": provider, "url": "https://e.org/paper", "content": content, "read": True}])
    client = JevClient(service.config.jev_settings(), time.monotonic() + 10)
    async def evaluate(state, questions, phase):
        assert state["unique_read_sources"] == 1
        assert {i["source_identity"] for i in state["evidence"]} == {"https://e.org/paper"}
        assert "40 C" in state["evidence"][0]["content"] and "50 C" in state["evidence"][1]["content"]
        assert "one source" in str(questions)
        return {key: .1 if key != "useful" else .95 for key in questions}
    monkeypatch.setattr(client, "evaluate", evaluate)
    result = await assess_evidence(client, "What is the temperature?", items, "balanced")
    assert result["unique_read_sources"] == 1 and not result["sufficient"]


def test_unread_streamed_rate_error_retains_classification():
    from smart_search.provider_errors import classify_provider_exception
    response = httpx.Response(429, stream=httpx.ByteStream(b"not yet read"), request=httpx.Request("POST", "https://e.org"))
    kind, _ = classify_provider_exception(httpx.HTTPStatusError("limited", request=response.request, response=response))
    assert kind == "rate_limited"


@pytest.mark.asyncio
async def test_large_selection_batches_preserve_scores_and_request_bound(monkeypatch):
    client = JevClient(replace(service.config.jev_settings(), max_channels=2), time.monotonic() + 10)
    calls = []
    candidates = [{"id": str(i), "operation": "fetch", "url": f"https://e.org/{i}", "description": "source " * 1500} for i in range(30)]
    async def evaluate(state, questions, phase):
        import json
        assert len(json.dumps({"state": state, "questions": questions}, ensure_ascii=False)) <= 32000
        calls.append(state["available_channels"])
        return {f"channel_{i}": .95 if item["id"] == "29" else .51 for i, item in enumerate(state["available_channels"])}
    monkeypatch.setattr(client, "evaluate", evaluate)
    selected, scores = await select_channels(client, "verify original source", candidates, evidence=[], history=[], validation="balanced", require_read=True)
    assert len(calls) > 1 and len(scores) == 30
    assert selected[0]["id"] == "29" and scores["29"] == .95


def test_local_route_fallback_does_not_erase_successful_judgment(tmp_path):
    from smart_search.jev_search import _research_result
    plan = service.build_deep_research_plan("fact", budget="standard", evidence_dir=str(tmp_path))
    result = {"ok": True, "content": "fact", "degraded": True, "evidence_assessment": {"status": "sufficient", "gaps": []}}
    evidence = [{"id": "e1", "provider": "tavily", "title": "Source", "url": "https://e.org/paper", "content": "fact", "read": True}]
    report = _research_result(service, result, "fact", evidence, plan)
    assert report["gap_check"]["status"] == "closed"
    assert report["completion"]["answer"] == "complete"


def test_chinese_question_retains_english_material_and_experimental_sections():
    from smart_search.evidence import relevant_excerpt
    body = "Navigation [Menu](https://e.org)\n\n" * 100
    body += "# An ultrasound experiment\n\n## Abstract\n\nWe studied cavitation during solidification.\n\n"
    body += "## Experimental materials\n\nThe liquid layer was Ga–40wt.%In. No pipeline freezing experiment was performed.\n\n"
    body += "## References\n\n" + "DOI and ultrasound material references.\n\n" * 100
    excerpt = relevant_excerpt(body, "请核验 Ga-In 实验材料，区分组织细化和管道凝固堵塞的证据", 1200)
    assert "Ga–40wt.%In" in excerpt
    assert "No pipeline freezing experiment" in excerpt


@pytest.mark.asyncio
async def test_navigation_extraction_can_use_an_untried_reader(monkeypatch, tmp_path):
    configure_fetch(monkeypatch)
    stub_research_judge(monkeypatch)
    original = JevClient._request
    async def request(self, state, questions, timeout):
        response = await original(self, state, questions, timeout)
        if "sufficient" in questions:
            useful = any("Actual original experiment" in item.get("content", "") for item in state["evidence"])
            for key in ("useful", "sufficient"):
                response["answers"][key]["noul"] = .95 if useful else .01
        return response
    monkeypatch.setattr(JevClient, "_request", request)
    async def tavily(url):
        return "Sign in | Menu | Copyright. No article text."
    async def firecrawl(url):
        return "Actual original experiment: Ga-In dendrite fragmentation."
    monkeypatch.setattr(service, "call_tavily_extract", tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", firecrawl)
    result = await service.research("只读取 https://e.org/paper", budget="standard", evidence_dir=str(tmp_path))
    assert result["completion"]["answer"] == "complete"
    assert result["completion"]["unique_read_sources"] == 1
    assert [a["provider"] for a in result["provider_attempts"] if a["operation"] == "fetch"] == ["tavily", "firecrawl"]
    assert len(result["evidence_items"]) == 2  # Both captured versions remain auditable.


@pytest.mark.asyncio
async def test_fetch_deadline_retains_failed_primary_and_timed_out_fallback(monkeypatch, tmp_path):
    from smart_search.jev_search import search
    configure_fetch(monkeypatch)
    stub_research_judge(monkeypatch)
    cancelled = asyncio.Event()
    async def primary(url):
        raise ProviderCallError("network_error", "Controlled primary failure")
    async def alternate(url):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
    monkeypatch.setattr(service, "call_tavily_extract", primary)
    monkeypatch.setattr(service, "call_firecrawl_scrape", alternate)
    query = "只读取 https://e.org/paper"
    plan = service.build_deep_research_plan(query, budget="standard", evidence_dir=str(tmp_path))
    started = time.monotonic()
    result = await search(query, validation="balanced", fallback="auto", providers="auto", timeout_seconds=.3, research_plan=plan, single_pass=False)
    assert time.monotonic() - started < 1
    assert cancelled.is_set() and not result["ok"]
    attempts = result["provider_attempts"]
    assert [(a["provider"], a["error_type"]) for a in attempts] == [("tavily", "network_error"), ("firecrawl", "timeout")]
