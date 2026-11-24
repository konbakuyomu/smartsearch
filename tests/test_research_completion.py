"""Research completion: the delivery reservation, unchanged exit codes, an
answer status that never reads as plain OK when it is partial, and truthful
cancellation results, for the CLI and the desktop worker."""

import asyncio
import json
import time
import uuid

import pytest

from smart_search import cli, desktop_worker, service
from smart_search.i18n import render_messages, use_language
from smart_search.jev import JevClient
from smart_search.jev_search import ChannelExecutor, search


URL = "https://e.org/paper"


def configure_readers(monkeypatch, *, firecrawl=True):
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    if firecrawl:
        monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl")
    monkeypatch.setenv("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "0")


def stub_jev(monkeypatch, scores=None, *, delays=None):
    """Answer Jev at its HTTP boundary: read first, then the supplied scores."""
    scores = {"useful": .99, "sufficient": .99, "synthesize": .99, **(scores or {})}
    delays = delays or {}

    async def request(self, state, questions, timeout):
        phase = next(iter(questions)).split("_")[0]
        if phase in delays:
            await delays[phase]()
        answers = {}
        for key in questions:
            if key.startswith("channel_"):
                channel = state["available_channels"][int(key.split("_")[1])]
                answers[key] = .99 if channel["operation"] == "fetch" else .6
            elif key.startswith("group_"):
                answers[key] = .99
            else:
                answers[key] = scores.get(key, .01)
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in answers.items()}}

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-jev")


def synthesis_model(monkeypatch, mode):
    for key, value in {"SMART_SEARCH_JEV_SYNTHESIZE": mode, "SMART_SEARCH_JEV_SYNTHESIS_API_URL": "https://api.example/v1",
                       "SMART_SEARCH_JEV_SYNTHESIS_API_KEY": "test-synthesis", "SMART_SEARCH_JEV_SYNTHESIS_MODEL": "sol"}.items():
        monkeypatch.setenv(key, value)


# The delivery phase keeps its reserved time.

@pytest.mark.asyncio
async def test_filter_reaching_the_retrieval_cutoff_leaves_the_delivery_reserve_usable(monkeypatch, tmp_path):
    configure_readers(monkeypatch, firecrawl=False)

    async def slow_filter():
        await asyncio.sleep(10)

    stub_jev(monkeypatch, delays={"group": slow_filter})
    synthesis_model(monkeypatch, "auto")
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    decisions = []

    async def read(url):
        return "Verified requested experimental fact."

    async def synthesize(self, *args):
        return "Combined answer.", "sol"

    from smart_search import jev_search
    original_decide = jev_search.decide_synthesis

    async def decide(client, *args):
        decisions.append(client.deadline - time.monotonic())
        return await original_decide(client, *args)

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    monkeypatch.setattr(jev_search, "decide_synthesis", decide)
    plan = service.build_deep_research_plan("q", budget="standard", evidence_dir=str(tmp_path))
    result = await search("只读取 " + URL, validation="balanced", fallback="auto", providers="auto",
                          timeout_seconds=1.2, research_plan=plan, single_pass=False)
    assert result["result_filter"]["status"] == "retained"
    assert decisions and decisions[0] > .3
    assert result["synthesis"]["decision_source"] == "jev" and result["synthesis"]["status"] == "ok"
    assert any(p["phase"] == "synthesis_decision" and p["status"] == "ok" for p in result["phase_attempts"])
    assert result["completion"]["answer"] == "complete"
    assert result["elapsed_ms"] < 1400


@pytest.mark.asyncio
async def test_reassessing_filtered_evidence_can_use_the_delivery_reserve(monkeypatch, tmp_path):
    configure_readers(monkeypatch, firecrawl=False)
    stub_jev(monkeypatch)
    synthesis_model(monkeypatch, "auto")
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")
    assessments = []

    async def request(self, state, questions, timeout):
        if "sufficient" in questions:
            assessments.append(True)
            if len(assessments) == 2:
                await asyncio.sleep(.8)  # Past the 0.72 s retrieval cutoff, inside the 1.2 s deadline.
        answers = {}
        for key in questions:
            if key.startswith("channel_"):
                answers[key] = .99 if state["available_channels"][int(key.split("_")[1])]["operation"] == "fetch" else .01
            elif key.startswith("group_"):
                group = state["groups"][int(key.split("_")[1])]
                answers[key] = .01 if all("Unrelated" in unit["content"] for unit in group) else .99
            else:
                answers[key] = .99 if key in {"useful", "sufficient", "synthesize"} else .01
        return {"answers": {key: {"type": "noul", "noul": value} for key, value in answers.items()}}

    async def read(url):
        return "Unrelated navigation text." if url.endswith("/b") else "Verified requested experimental fact."

    async def synthesize(self, *args):
        return "Combined answer.", "sol"

    monkeypatch.setattr(JevClient, "_request", request)
    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)
    plan = service.build_deep_research_plan("q", budget="standard", evidence_dir=str(tmp_path))
    result = await search("只读取 https://e.org/a https://e.org/b", validation="balanced", fallback="auto", providers="auto",
                          timeout_seconds=1.2, research_plan=plan, single_pass=False)
    assert len(assessments) == 2 and result["result_filter"]["dropped_chunk_ids"]
    assert result["routing_decision"]["stop_reason"] == "sufficient"
    assert result["evidence_assessment"]["sufficient"] and not result["degraded"]
    assert result["synthesis"]["status"] == "ok" and result["completion"]["answer"] == "complete"


@pytest.mark.asyncio
async def test_skipped_synthesis_decision_is_not_a_complete_answer(monkeypatch, tmp_path):
    from smart_search.provider_errors import ProviderCallError
    configure_readers(monkeypatch, firecrawl=False)

    async def broken_filter():
        raise ProviderCallError("provider_error", "Controlled filter outage")

    stub_jev(monkeypatch, delays={"group": broken_filter})
    synthesis_model(monkeypatch, "auto")
    monkeypatch.setenv("SMART_SEARCH_JEV_FILTER_RESULTS", "true")

    async def read(url):
        return "Verified requested experimental fact."

    monkeypatch.setattr(service, "call_tavily_extract", read)
    result = await service.research("只读取 " + URL, budget="standard", evidence_dir=str(tmp_path))
    assert result["synthesis"]["status"] == "skipped" and result["synthesis"]["reason"] == "judgment_unavailable"
    assert result["completion"]["answer"] == "partial"
    assert result["completion"]["reason"] == "synthesis_decision_skipped"
    assert result["ok"]


# Exit codes keep their mapping; the answer status is stated.

def run_cli(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr().out


def test_item_gap_lowers_answer_but_keeps_strict_exit_code(monkeypatch, capsys, tmp_path):
    configure_readers(monkeypatch, firecrawl=False)
    stub_jev(monkeypatch, {"gap_freshness": .9})

    async def read(url):
        return "Original requested fact."

    monkeypatch.setattr(service, "call_tavily_extract", read)
    code, out = run_cli(["research", "只读取 " + URL, "--budget", "deep", "--evidence-dir", str(tmp_path), "--format", "json"], capsys)
    data = json.loads(out)
    assert code == cli.EXIT_OK and data["ok"]
    assert data["validation_level"] == "strict"
    assert data["completion"]["answer"] == "partial" and data["completion"]["evidence"] == "degraded"
    assert data["completion"]["reason"] == "evidence_gaps"
    assert [gap["reason"] for gap in data["gap_check"]["gaps"]] == ["freshness"]


def test_strict_insufficient_evidence_still_exits_four(monkeypatch, capsys, tmp_path):
    configure_readers(monkeypatch, firecrawl=False)
    stub_jev(monkeypatch, {"sufficient": .2})

    async def read(url):
        return "Original requested fact."

    monkeypatch.setattr(service, "call_tavily_extract", read)
    code, out = run_cli(["research", "只读取 " + URL, "--budget", "deep", "--evidence-dir", str(tmp_path), "--format", "json"], capsys)
    assert code == cli.EXIT_NETWORK_ERROR and not json.loads(out)["ok"]


def research_outcome(monkeypatch, outcome):
    """Configure one controlled research outcome; returns the expected (ok, answer)."""
    configure_readers(monkeypatch, firecrawl=False)
    stub_jev(monkeypatch)
    synthesis_model(monkeypatch, "true")

    async def read(url):
        if outcome == "failed":
            return ""
        return "Original requested fact."

    async def synthesize(self, *args):
        if outcome == "partial":
            from smart_search.provider_errors import ProviderCallError
            raise ProviderCallError("network_error", "Controlled synthesis outage")
        return "Combined answer from the original source.", "sol"

    monkeypatch.setattr(service, "call_tavily_extract", read)
    monkeypatch.setattr(ChannelExecutor, "synthesize", synthesize)


@pytest.mark.parametrize("outcome, code, status", [
    ("complete", cli.EXIT_OK, "**Status:** OK"),
    ("partial", cli.EXIT_OK, "**Status:** OK (answer partial: synthesis failed; the report shows source excerpts)"),
    ("failed", cli.EXIT_NETWORK_ERROR, "**Status:** FAIL"),
])
def test_research_markdown_states_answer_status(monkeypatch, capsys, tmp_path, outcome, code, status):
    research_outcome(monkeypatch, outcome)
    with use_language("en"):
        exit_code, out = run_cli(["research", "只读取 " + URL, "--budget", "standard", "--evidence-dir", str(tmp_path),
                                  "--format", "markdown", "--lang", "en"], capsys)
    assert exit_code == code
    status_line = next(line for line in out.splitlines() if line.startswith("**Status:**"))
    assert status_line == status


def test_research_markdown_states_partial_answer_in_chinese(monkeypatch, capsys, tmp_path):
    research_outcome(monkeypatch, "partial")
    exit_code, out = run_cli(["research", "只读取 " + URL, "--budget", "standard", "--evidence-dir", str(tmp_path),
                              "--format", "markdown", "--lang", "zh"], capsys)
    assert exit_code == cli.EXIT_OK
    assert "**状态：** 成功（答案不完整：总结失败，报告只列出来源摘录）" in out


# Cancelling after discovery keeps the URLs and says what was returned.

def discovery_then_blocked_read(monkeypatch):
    configure_readers(monkeypatch, firecrawl=False)
    stub_jev(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_JEV_SYNTHESIZE", "false")
    reading = asyncio.Event()

    async def discover(query, count):
        return [{"url": "https://e.org/found", "title": "Found page", "content": "Discovery snippet."}]

    async def read(url):
        reading.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "call_tavily_search", discover)
    monkeypatch.setattr(service, "call_tavily_extract", read)
    return reading


@pytest.mark.asyncio
async def test_cancel_after_discovery_only_keeps_partial_success_and_truthful_reason(monkeypatch, tmp_path):
    reading = discovery_then_blocked_read(monkeypatch)
    task = asyncio.create_task(service.research("gallium indium ultrasound experiment", budget="standard", evidence_dir=str(tmp_path)))
    await asyncio.wait_for(reading.wait(), 3)
    task.cancel()
    result = await asyncio.wait_for(task, 3)
    assert result["error_type"] == "cancelled" and not result["ok"]
    assert result["partial_success"] is True
    assert [item["url"] for item in result["discovery_sources"]] == ["https://e.org/found"]
    assert not result["evidence_items"] and result["completion"]["answer"] == "failed"
    assert result["completion"]["reason"] == "cancelled"
    reason = render_messages(result["degraded_reason"], "en")
    assert "excerpt" not in reason and "before any source was read" in reason
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["partial_success"] is True


# Desktop worker: the App-facing envelope for every outcome.

def worker_payload(tmp_path, values):
    return {"method": "run.start", "command": "research", "params": {"arguments": [
        "只读取 " + URL, "--budget", "standard", "--evidence-dir", str(tmp_path / "evidence")]},
        "values": {"TYPESAFE_API_KEY": "synthetic-jev", "TAVILY_API_KEY": "synthetic-tavily",
                   "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS": "0", **values},
        "config_dir": str(tmp_path), "run_id": uuid.uuid4().hex, "language": "en"}


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, status, exit_code, answer, text", [
    ("complete", "finished", 0, "complete", "**Status:** OK\n"),
    ("partial", "finished", 0, "partial", "**Status:** OK (answer partial: synthesis failed; the report shows source excerpts)\n"),
    ("failed", "failed", 4, "failed", "**Status:** FAIL\n"),
])
async def test_worker_envelope_states_answer_status(monkeypatch, tmp_path, outcome, status, exit_code, answer, text):
    research_outcome(monkeypatch, outcome)
    values = {"SMART_SEARCH_JEV_SYNTHESIZE": "true", "SMART_SEARCH_JEV_SYNTHESIS_API_URL": "https://api.example/v1",
              "SMART_SEARCH_JEV_SYNTHESIS_API_KEY": "synthetic-synthesis", "SMART_SEARCH_JEV_SYNTHESIS_MODEL": "sol"}
    with use_language("en"):
        envelope = render_messages(await desktop_worker.execute(worker_payload(tmp_path, values)), "en")
    json.dumps(envelope, ensure_ascii=False)
    assert envelope["status"] == status and envelope["exit_code"] == exit_code
    result = envelope["result"]
    assert result["completion"]["answer"] == answer
    assert text in result["display_text"]


@pytest.mark.asyncio
async def test_worker_envelope_for_cancel_after_discovery(monkeypatch, tmp_path):
    reading = discovery_then_blocked_read(monkeypatch)
    payload = worker_payload(tmp_path, {"SMART_SEARCH_JEV_SYNTHESIZE": "false"})
    payload["params"]["arguments"][0] = "gallium indium ultrasound experiment"
    with use_language("en"):
        task = asyncio.create_task(desktop_worker.execute(payload))
        await asyncio.wait_for(reading.wait(), 3)
        task.cancel()
        envelope = render_messages(await asyncio.wait_for(task, 3), "en")
    result = envelope["result"]
    assert envelope["status"] == "cancelled" and result["error_type"] == "cancelled"
    assert result["partial_success"] is True and result["completion"]["answer"] == "failed"
    assert "before any source was read" in result["degraded_reason"]
    assert "**Status:** FAIL" in result["display_text"]
