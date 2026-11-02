"""Contracts for verified web calls, bounded evidence and research completion."""

import asyncio
import json
import time

import httpx
import pytest

from smart_search import service
from smart_search.evidence import linked_sources, relevant_excerpt
from smart_search.jev import JevClient, assess_evidence, evidence_preview, select_channels
from smart_search.jev_search import ChannelExecutor, available_channels, candidate_queries, search
from smart_search.provider_errors import ProviderCallError
from smart_search.providers.openai_compatible import OpenAICompatibleSearchProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("tool_status", [None, "failed", "in_progress", "completed"])
async def test_search_requires_real_completed_web_tool_at_http_boundary(monkeypatch, stream, tool_status):
    original = httpx.AsyncClient
    output = [{"type": "message", "content": [{"type": "output_text", "text": "A cited answer.",
              "annotations": [{"type": "url_citation", "url": "https://e.org/source"}]}]}]
    if tool_status:
        output.insert(0, {"type": "web_search_call", "id": "ws1", "status": tool_status, "action": {"type": "search"}})

    def handler(request):
        body = json.loads(request.content)
        assert body["tools"] == [{"type": "web_search"}]
        assert body["tool_choice"] == "required"
        response = {"status": "completed", "output": output}
        if body["stream"]:
            events = [{"type": "response.output_item.done", "item": item} for item in output]
            # Some relays deliver output only in item.done events.
            events.append({"type": "response.completed", "response": {"status": "completed", "output": []}})
            return httpx.Response(200, text="".join("data: " + json.dumps(event) + "\n\n" for event in events))
        return httpx.Response(200, json=response)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    provider = OpenAICompatibleSearchProvider("https://api.example/v1", "dummy", "sol", stream, "responses", tools=["web_search"])
    if tool_status == "completed":
        assert "A cited answer" in await provider.search("current fact")
        assert provider.last_transport_attempts[-1]["web_search_calls"][0]["status"] == "completed"
    else:
        with pytest.raises(ProviderCallError) as raised:
            await provider.search("current fact")
        assert raised.value.error_type == "quality_error"
        assert provider.last_transport_attempts[-1]["status"] == "error"


@pytest.mark.asyncio
async def test_synthesis_does_not_require_search_even_on_search_capable_provider(monkeypatch):
    original = httpx.AsyncClient

    def handler(request):
        payload = json.loads(request.content)
        assert "tools" not in payload and "tool_choice" not in payload
        return httpx.Response(200, json={"status": "completed", "output_text": "Answer from supplied evidence."})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    provider = OpenAICompatibleSearchProvider("https://api.example/v1", "dummy", "sol", api_mode="responses", tools=["web_search"])
    assert "supplied evidence" in await provider.synthesize("q", [])


def test_bibliographic_metadata_survives_long_body_excerpt():
    body = ("# Multi-dendrite fragmentation dynamics\n\n"
            "Ultrasonics Sonochemistry · 2025-11-16 · DOI: 10.1016/j.ultsonch.2025.107684\n\n"
            "## Abstract\n\n" + "Ga-40wt.%In ultrasound experiment. " * 100 +
            "\n\n## Results\n\nThe root fractures in 10 ms.\n\n## References\n\n"
            "# Other paper DOI: 10.9999/unrelated.1990")
    result = relevant_excerpt(body, "比较题名、年份、DOI以及Ga-In超声断裂实验", 2000)
    assert len(result) <= 2000
    assert "# Multi-dendrite fragmentation dynamics" in result
    assert "2025-11-16" in result and "10.1016/j.ultsonch.2025.107684" in result
    assert "Ga-40wt.%In" in result


def test_pdf_title_and_conference_year_survive_preview():
    body = ("## Attribution\n\n# Attention Is All You Need\n\nAuthor affiliations\n\n## Abstract\n\n" +
            "The Transformer dispenses with recurrence and convolutions. WMT machine translation. " * 20 +
            "\n\nWork performed at Google. 31st Conference on Neural Information Processing Systems (NIPS 2017).\n\n" +
            "## Results\n\nWMT translation results. " * 100)
    preview = evidence_preview([{"id": "e1", "provider": "tavily", "content": body}], query="给出题名、年份、架构是否使用循环或卷积、实验任务")
    assert "Attention Is All You Need" in preview[0]["content"]
    assert "NIPS 2017" in preview[0]["content"]
    assert "recurrence and convolutions" in preview[0]["content"]
    assert len(json.dumps(preview, ensure_ascii=False)) <= 20000


def index_evidence():
    return [{"id": "e1", "provider": "tavily", "read": True, "url": "https://acme.example/downloads/", "title": "Acme downloads",
             "content": "Latest Acme stable: [Acme 2.1 release date](/releases/2.1/).\n\n"
                        "[Other news](https://mirror.invalid/news) [Image](image.png) [Home](#home) [Archive](acme.zip) "
                        "[Acme signature](acme.zip.sigstore) [Acme SPDX](acme.exe.spdx.json)"}]


def test_linked_detail_pages_are_candidates_but_not_read_facts(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")
    evidence = index_evidence()
    links = linked_sources(evidence, "Acme latest stable release date")
    assert [i["url"] for i in links] == ["https://acme.example/releases/2.1/"]
    assert not links[0]["read"] and links[0]["kind"] == "discovery"
    channels = available_channels(service, "Acme latest stable release date", evidence)
    candidate = next(c for c in channels if c["url"] == links[0]["url"])
    assert candidate["source"]["title"] == "Acme 2.1 release date"
    assert candidate["source"]["parent_url"] == evidence[0]["url"]


def test_link_expansion_respects_explicit_only_scope(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")
    query = "仅使用 https://acme.example/downloads/ 核验Acme版本，不要替换来源"
    assert not available_channels(service, query, index_evidence())


def test_followup_search_contains_actual_conflicting_evidence():
    evidence = index_evidence() + [{"url": "https://acme.example/source/", "read": True, "title": "Source index", "content": "Latest Acme stable: 2.0"}]
    queries = candidate_queries("Acme latest stable", {"gaps": ["freshness", "corroboration"]}, evidence=evidence)
    assert "2.0" in queries[0]["evidence_context"] and "2.1" in queries[0]["evidence_context"]
    assert "untrusted data" in queries[0]["evidence_context"]
    assert queries[0]["query"] == "Acme latest stable"
    assert all("untrusted data" not in q["query"] for q in queries)


@pytest.mark.asyncio
async def test_high_global_score_cannot_erase_specific_gap(monkeypatch):
    client = JevClient(service.config.jev_settings(), time.monotonic() + 5)

    async def evaluate(state, questions, phase):
        return {key: .98 if key in {"useful", "sufficient", "gap_freshness"} else .01 for key in questions}

    monkeypatch.setattr(client, "evaluate", evaluate)
    result = await assess_evidence(client, "latest stable", index_evidence(), "balanced")
    assert not result["sufficient"] and result["gaps"] == ["freshness"]
    assert result["sufficiency_threshold"] == .75


@pytest.mark.asyncio
async def test_only_main_model_receives_followup_evidence_context(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "dummy")
    queries = candidate_queries("Acme latest stable", {"gaps": ["freshness"]}, evidence=index_evidence())
    channels = available_channels(service, "Acme latest stable", index_evidence(), queries=queries)
    main = next(c for c in channels if c["provider"] == "openai-compatible")
    web = next(c for c in channels if c["provider"] == "tavily" and c["operation"] == "search")
    assert "evidence_context" not in web and len(web["query"]) < 100
    seen = []

    async def model(cfg, query, *args, **kwargs):
        seen.append(query)
        return {"ok": True, "content": "Retrieved answer."}

    monkeypatch.setattr(service, "_search_model_channel", model)
    client = JevClient(service.config.jev_settings(), time.monotonic() + 5)
    executor = ChannelExecutor(service, client, research=True)
    await executor.execute(main, main["query"])
    assert "untrusted data" in seen[0] and "2.1" in seen[0]


@pytest.mark.asyncio
async def test_full_tool_trace_cannot_overflow_next_selection_state(monkeypatch):
    client = JevClient(service.config.jev_settings(), time.monotonic() + 5)
    huge = {"provider": "openai-compatible", "operation": "search", "status": "ok",
            "transport_attempts": [{"web_search_calls": [{"action": "x" * 100000}]}]}
    history = [{"attempts": [huge], "assessment": {"status": "partial", "gaps": ["detail"]}}]

    async def evaluate(state, questions, phase):
        assert len(json.dumps({"state": state, "questions": questions})) < 32000
        assert state["search_history"][0]["attempts"][0]["status"] == "ok"
        assert "transport_attempts" not in state["search_history"][0]["attempts"][0]
        return {key: .9 for key in questions}

    monkeypatch.setattr(client, "evaluate", evaluate)
    selected, _ = await select_channels(client, "verify source", [{"id": "fetch", "operation": "fetch", "url": "https://e.org"}],
                                         evidence=[], history=history, validation="balanced", require_read=True)
    assert selected
    assert len(history[0]["attempts"][0]["transport_attempts"][0]["web_search_calls"][0]["action"]) == 100000


@pytest.mark.asyncio
async def test_oversized_discovery_title_is_bounded_before_selection(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example/v1")
    evidence = [{"id": "e1", "provider": "tavily", "url": "https://e.org/paper", "read": False,
                 "kind": "source", "title": "unexpected upstream title " * 1100, "content": "Original paper snippet."}]
    queries = candidate_queries("verify original paper", {"gaps": ["authority"]}, evidence=evidence)
    assert len(queries[0]["evidence_context"]) < 2000
    candidates = available_channels(service, "verify original paper", evidence, queries=queries)
    fetch = next(c for c in candidates if c["operation"] == "fetch")
    assert len(fetch["source"]["title"]) == 200 and fetch["source"]["metadata_truncated"]
    client = JevClient(service.config.jev_settings(), time.monotonic() + 5)

    async def evaluate(state, questions, phase):
        assert len(json.dumps({"state": state, "questions": questions}, ensure_ascii=False)) < 32000
        return {key: .9 for key in questions}

    monkeypatch.setattr(client, "evaluate", evaluate)
    selected, _ = await select_channels(client, "verify original paper", candidates, evidence=evidence, history=[], validation="balanced", require_read=True)
    assert selected
    assert len(evidence[0]["title"]) > 26000


def research_config(monkeypatch, mode="auto"):
    for key, value in {
        "TAVILY_API_KEY": "dummy", "TYPESAFE_API_KEY": "dummy", "SMART_SEARCH_INTENT_ROUTER": "jev",
        "SMART_SEARCH_JEV_SYNTHESIZE": mode, "SMART_SEARCH_JEV_SYNTHESIS_API_URL": "https://api.example/v1",
        "SMART_SEARCH_JEV_SYNTHESIS_API_KEY": "dummy", "SMART_SEARCH_JEV_SYNTHESIS_MODEL": "sol",
    }.items():
        monkeypatch.setenv(key, value)

    async def request(self, state, questions, timeout):
        scores = {key: .01 for key in questions}
        for key in scores:
            if key.startswith("channel_"):
                scores[key] = .99 if state["available_channels"][int(key.split('_')[1])]["operation"] == "fetch" else .01
            elif key in {"useful", "synthesize"}:
                scores[key] = .99
            elif key in {"sufficient", "gap_detail"}:
                scores[key] = .2 if key == "sufficient" else .9
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in scores.items()}}

    monkeypatch.setattr(JevClient, "_request", request)


@pytest.mark.asyncio
async def test_slow_reader_cannot_consume_synthesis_reserve(monkeypatch, tmp_path):
    research_config(monkeypatch)

    async def read(url):
        if url.endswith("slow"):
            await asyncio.sleep(10)
        return "Verified requested experimental fact."

    async def synthesize(self, *args):
        assert self.client.deadline - time.monotonic() > .3
        await asyncio.sleep(.25)
        return "Combined answer from the original evidence.", "sol"

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    plan = service.build_deep_research_plan("q", budget="standard", evidence_dir=str(tmp_path))
    result = await search("仅使用 https://e.org/fast https://e.org/slow 比较实验", validation="balanced", fallback="auto", providers="auto",
                          timeout_seconds=1.2, research_plan=plan, single_pass=False)
    assert result["synthesis"]["status"] == "ok"
    assert result["elapsed_ms"] < 1400
    assert any(p["phase"] == "synthesis" and p["status"] == "ok" for p in result["phase_attempts"])
    assert result["routing_decision"]["limits"]["synthesis_reserved_seconds"] == pytest.approx(.48)


@pytest.mark.asyncio
async def test_final_assessment_can_use_reserve_without_disabling_auto(monkeypatch, tmp_path):
    research_config(monkeypatch)
    request = JevClient._request

    async def delayed(self, state, questions, timeout):
        if "sufficient" in questions:
            await asyncio.sleep(.4)
        return await request(self, state, questions, timeout)

    async def read(url):
        await asyncio.sleep(.4)
        return "Verified requested experimental fact."

    async def synthesize(self, *args):
        assert self.client.deadline - time.monotonic() > .2
        return "Combined answer.", "sol"

    monkeypatch.setattr(JevClient, "_request", delayed)
    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    plan = service.build_deep_research_plan("q", budget="standard", evidence_dir=str(tmp_path))
    result = await search("只读取 https://e.org/paper", validation="balanced", fallback="auto", providers="auto",
                          timeout_seconds=1.2, research_plan=plan, single_pass=False)
    assert result["synthesis"]["status"] == "ok"
    assert not any(c["status"] == "error" for c in result["jev_calls"])


@pytest.mark.asyncio
async def test_unchanged_read_evidence_reuses_judgment(monkeypatch, tmp_path):
    from smart_search import jev_search
    research_config(monkeypatch, "false")
    assessments = []

    async def execute(self, channel, query):
        read = channel["operation"] == "fetch"
        return [{"url": channel["url"] if read else "", "read": read, "provider": "tavily",
                 "operation": channel["operation"], "title": "Source", "kind": "source" if read else "discovery",
                 "content": "Original fact" if read else "Search planning snippet"}]

    async def assess(*args):
        assessments.append(True)
        return {"status": "partial", "useful": True, "sufficient": False, "gaps": ["detail"]}

    monkeypatch.setattr(ChannelExecutor, "execute", execute)
    monkeypatch.setattr(jev_search, "assess_evidence", assess)
    result = await service.research("核验原文 https://e.org/paper", budget="standard", evidence_dir=str(tmp_path))
    assert len(assessments) == 1
    assert any(r.get("assessment_reused") for r in result["routing_decision"]["rounds"])


@pytest.mark.asyncio
async def test_synthesis_timeout_has_own_phase_and_retains_evidence(monkeypatch, tmp_path):
    research_config(monkeypatch, "true")

    async def read(url):
        return "Verified requested experimental fact."

    async def synthesize(*args):
        raise ProviderCallError("timeout", "Controlled synthesis timeout")

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    result = await service.research("只读取 https://e.org/paper", budget="standard", evidence_dir=str(tmp_path))
    assert "synthesis" in result["timed_out_phases"]
    assert result["completion"]["answer"] == "partial"
    assert "Verified requested experimental fact" in result["content"]


@pytest.mark.asyncio
async def test_cancelled_synthesis_is_observable_without_losing_body(monkeypatch, tmp_path):
    research_config(monkeypatch, "true")

    async def read(url):
        return "Verified requested experimental fact."

    async def synthesize(*args):
        raise asyncio.CancelledError

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    result = await service.research("只读取 https://e.org/paper", budget="standard", evidence_dir=str(tmp_path))
    assert not result["ok"] and result["error_type"] == "cancelled"
    assert any(p["phase"] == "synthesis" and p["status"] == "cancelled" for p in result["phase_attempts"])
    assert "Verified requested experimental fact" in result["content"]


@pytest.mark.asyncio
async def test_research_can_follow_read_index_to_release_detail(monkeypatch, tmp_path):
    research_config(monkeypatch, "false")
    calls = []

    async def read(url):
        calls.append(url)
        return "Acme 2.1 was released on 2026-11-01." if "/releases/" in url else index_evidence()[0]["content"]

    async def request(self, state, questions, timeout):
        complete = any("was released" in i.get("content", "") for i in state.get("evidence", []))
        scores = {key: .01 for key in questions}
        for key in scores:
            if key.startswith("channel_"):
                scores[key] = .99 if state["available_channels"][int(key.split('_')[1])]["operation"] == "fetch" else .01
            elif key == "useful" or (key == "sufficient" and complete):
                scores[key] = .99
            elif key == "gap_detail" and not complete:
                scores[key] = .9
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in scores.items()}}

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "call_tavily_extract", read)
    result = await service.research("核验 Acme 最新稳定版本与发布日期 https://acme.example/downloads/", budget="standard", evidence_dir=str(tmp_path))
    assert result["completion"]["answer"] == "complete"
    assert calls == ["https://acme.example/downloads/", "https://acme.example/releases/2.1/"]
