"""Research scheduling: one call per reader and URL, and URL restrictions
that bind to the URLs they name."""

import asyncio

import pytest

from smart_search import service
from smart_search.jev import JevClient
from smart_search.jev_search import _source_scope, available_channels


URL = "https://e.org/paper"


def configure_readers(monkeypatch, *, firecrawl=True):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    if firecrawl:
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "0")


def stub_jev(monkeypatch, scores=None, *, delays=None, channel_score=None):
    """Answer Jev at its HTTP boundary: read first, then the supplied scores."""
    scores = {"useful": .99, "sufficient": .99, "synthesize": .99, **(scores or {})}
    delays = delays or {}
    channel_score = channel_score or (lambda channel: .99 if channel["operation"] == "fetch" else .6)

    async def request(self, state, questions, timeout):
        phase = next(iter(questions)).split("_")[0]
        if phase in delays:
            await delays[phase]()
        answers = {}
        for key in questions:
            if key.startswith("channel_"):
                answers[key] = channel_score(state["available_channels"][int(key.split("_")[1])])
            elif key.startswith("group_"):
                answers[key] = .99
            else:
                answers[key] = scores.get(key, .01)
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in answers.items()}}

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-jev")


def fetch_calls(result):
    return [(a["provider"], a["url"]) for a in result["provider_attempts"] if a.get("operation") == "fetch"]


# One reader is called at most once for one URL in a run.

@pytest.mark.asyncio
async def test_local_routing_calls_each_reader_once_for_two_slots_on_one_url(monkeypatch, tmp_path):
    configure_readers(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    calls = []

    async def tavily(url):
        calls.append(("tavily", url))
        return ""

    async def firecrawl(url):
        calls.append(("firecrawl", url))
        await asyncio.sleep(.01)
        return "Original page body."

    monkeypatch.setattr(service, "call_tavily_extract", tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", firecrawl)
    result = await service.research("只读取 " + URL, budget="standard", evidence_dir=str(tmp_path))
    selected = result["routing_decision"]["rounds"][0]["selected_channels"]
    assert [(c["provider"], c["url"]) for c in selected] == [("tavily", URL), ("firecrawl", URL)]
    assert sorted(calls) == [("firecrawl", URL), ("tavily", URL)]
    assert sorted(fetch_calls(result)) == [("firecrawl", URL), ("tavily", URL)]
    assert result["evidence_items"][0]["provider"] == "firecrawl"


@pytest.mark.asyncio
async def test_retry_with_an_untried_reader_does_not_repeat_an_earlier_reader(monkeypatch, tmp_path):
    configure_readers(monkeypatch)
    # The paper outranks the second URL, so the next round retries the paper
    # with Firecrawl while Tavily stays allowed for the other URL.
    stub_jev(monkeypatch, {"useful": .01, "sufficient": .01},
             channel_score=lambda channel: .99 if channel["url"] == URL else .6 if channel["operation"] == "fetch" else .01)
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "false")
    calls = []

    async def tavily(url):
        calls.append(("tavily", url))
        return "Sign in | Menu | Copyright."

    async def firecrawl(url):
        calls.append(("firecrawl", url))
        return ""

    monkeypatch.setattr(service, "call_tavily_extract", tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", firecrawl)
    result = await service.research("只读取 " + URL + " https://e.org/other", budget="quick", evidence_dir=str(tmp_path))
    rounds = result["routing_decision"]["rounds"]
    assert [[(c["provider"], c["url"]) for c in r["selected_channels"]] for r in rounds] == [[("tavily", URL)], [("firecrawl", URL)]]
    assert calls == [("tavily", URL), ("firecrawl", URL)]


# A restriction binds to the URLs it names; a kind of source does not.

@pytest.mark.parametrize("query, expected", [
    ("Only use https://e.org/paper to answer what changed.", {"https://e.org/paper"}),
    ("只用 https://e.org/paper 回答这个问题", {"https://e.org/paper"}),
    ("Use only https://a.example/1 and https://b.example/2 for the comparison", {"https://a.example/1", "https://b.example/2"}),
    ("Answer based only on the supplied page https://e.org/paper", {"https://e.org/paper"}),
    ("Read https://e.org/paper. Use only these sources.", {"https://e.org/paper"}),
    ("仅使用这个链接，不要替换来源 https://example.invalid/paper", {"https://example.invalid/paper"}),
    ("仅使用 https://e.org/fast https://e.org/slow 比较实验", {"https://e.org/fast", "https://e.org/slow"}),
    ("只读取 https://e.org/paper", {"https://e.org/paper"}),
    ("Use https://a.example/1 and https://b.example/2 only.", {"https://a.example/1", "https://b.example/2"}),
    ("Only use the docs at https://docs.example/x", {"https://docs.example/x"}),
    ("只基于以下两篇论文：https://a.example/1、https://b.example/2", {"https://a.example/1", "https://b.example/2"}),
    ("以 https://e.org/paper 为唯一来源回答", {"https://e.org/paper"}),
    ("Use only official sources. What does https://blog.example/post claim?", None),
    ("Use only official sources to check the claim in https://blog.example/post", None),
    ("What changed in https://blog.example/post? Only official sources, please.", None),
    ("只用官方来源核验 https://blog.example/post 里的说法", None),
    ("仅使用官方来源。参考 https://blog.example/post", None),
    ("Only use official sources, starting from https://docs.example/", None),
    ("Use only this approach for docs: https://x.example/a", None),
])
def test_url_restriction_binds_to_urls(query, expected):
    assert _source_scope(service, query) == expected


def test_generic_official_source_preference_keeps_discovery(monkeypatch):
    configure_readers(monkeypatch)
    channels = available_channels(service, "Use only official sources. What does https://blog.example/post claim?", [])
    assert any(c["operation"] == "search" for c in channels)
    restricted = available_channels(service, "Only use https://e.org/paper to answer what changed.", [{"url": "https://elsewhere.org/a"}])
    assert restricted and all(c["operation"] == "fetch" and c["url"] == "https://e.org/paper" for c in restricted)
