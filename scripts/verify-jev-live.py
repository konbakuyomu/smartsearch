"""Opt-in live acceptance. Credentials are read from normal user configuration."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from smart_search import service
from smart_search.jev import JevClient, assess_evidence, decide_synthesis, filter_evidence
from smart_search.jev_search import ChannelExecutor


async def verify(include_synthesis: bool) -> dict:
    os.environ["SMART_SEARCH_INTENT_ROUTER"] = "jev"
    os.environ["SMART_SEARCH_JEV_SYNTHESIZE"] = "false"
    os.environ["SMART_SEARCH_JEV_FILTER_RESULTS"] = "false"
    settings = service.config.jev_settings()
    cases = []

    fetched = await service.search(
        "请读取 https://www.iana.org/help/example-domains，说明示例域名的用途，以及能否注册或转移。",
        providers="tavily", timeout_seconds=60,
    )
    cases.append({"name": "live_url_fetch", "passed": fetched["ok"] and any(
        attempt["operation"] == "fetch" and attempt["status"] == "ok" for attempt in fetched["provider_attempts"]
    ), "result": fetched})
    print("live_url_fetch:", cases[-1]["passed"], flush=True)

    # Controlled inputs, not claimed to be live search results. The real model
    # must retain relevant facts at both ends and discard unrelated documents.
    question = "React useEffect 的 cleanup 什么时候运行？"
    texts = [
        "React runs an Effect's cleanup before running it again when dependencies change, and on unmount.",
        "Summer shoes: buy two pairs and receive a discount coupon.",
        "This restaurant's lunch menu includes noodles, dumplings, and soup.",
        "The football team won its game by two goals last weekend.",
        "Hotel check-in opens at 3 PM. Breakfast is served until 10 AM.",
        "Weather tomorrow: cloudy with showers in the evening.",
        "Cookie preferences: accept advertising cookies or manage analytics settings.",
        "In development Strict Mode, React additionally runs a setup and cleanup cycle to check the Effect's cleanup logic.",
    ]
    evidence = [
        {"id": f"e{i}", "provider": "controlled_fixture", "url": f"https://example.org/fixture/{i}",
         "title": f"Controlled fixture {i}", "content": text, "kind": "source"}
        for i, text in enumerate(texts)
    ]
    client = JevClient(settings, time.monotonic() + 45, verify=service.config.ssl_verify_enabled)
    assessment = await assess_evidence(client, question, evidence, "balanced")
    retained, filtering = await filter_evidence(client, question, evidence)
    ids = {item["id"] for item in retained}
    cases.append({
        "name": "live_jev_controlled_filter", "passed": assessment["sufficient"] and {"e0", "e7"} <= ids and len(ids) < len(evidence),
        "assessment": assessment, "filter": filtering, "retained_ids": sorted(ids), "usage": client.usage(),
    })
    print("live_jev_controlled_filter:", cases[-1]["passed"], "retained", sorted(ids), flush=True)

    if include_synthesis:
        executor = ChannelExecutor(service, JevClient(settings, time.monotonic() + 60))
        try:
            content, model = await executor.synthesize(question, retained, "auto")
            cases.append({"name": "live_optional_synthesis", "passed": bool(content.strip()), "model": model, "content": content})
        except Exception as exc:
            error_type, error = service.classify_provider_exception(exc)
            cases.append({"name": "live_optional_synthesis", "passed": False, "error_type": error_type, "error": error})
        print("live_optional_synthesis:", cases[-1]["passed"], flush=True)
    return {"ok": all(case["passed"] for case in cases), "cases": cases}


async def verify_auto_synthesis(include_synthesis: bool) -> dict:
    """Controlled retained evidence with real Jev decisions and optional synthesis."""
    os.environ["SMART_SEARCH_JEV_SYNTHESIZE"] = "auto"
    settings = service.config.jev_settings()
    evidence = [
        {"id": "e0", "provider": "controlled_fixture", "url": "https://example.org/fixture/a", "title": "方案 A",
         "content": "在此固定测试样本中，方案 A 延迟为 10 毫秒，内存占用为 2 GB。"},
        {"id": "e1", "provider": "controlled_fixture", "url": "https://example.org/fixture/b", "title": "方案 B",
         "content": "在此固定测试样本中，方案 B 延迟为 30 毫秒，内存占用为 0.5 GB。"},
    ]
    cases = []
    for query, expected in [
        ("只返回材料中的来源链接，不要解释，也不要汇总。", False),
        ("请综合两份材料，对比方案 A 和 B 的延迟与内存开销，并给出完整结论。", True),
    ]:
        client = JevClient(settings, time.monotonic() + 60, verify=service.config.ssl_verify_enabled)
        decision = await decide_synthesis(client, query, evidence, {"status": "sufficient", "useful": True, "sufficient": True, "gaps": []})
        case = {"query": query, "passed": decision["enabled"] is expected, "decision": decision, "usage": client.usage(), "synthesis_called": False}
        if decision["enabled"] and include_synthesis:
            executor = ChannelExecutor(service, client)
            try:
                case["synthesis_called"] = True
                case["content"], case["model"] = await executor.synthesize(query, evidence, "auto")
            except Exception as exc:
                case["error_type"], case["error"] = service.classify_provider_exception(exc)
                case["passed"] = False
        cases.append(case)
        print("auto_synthesis:", case["passed"], "decision", decision["enabled"], "probability", decision["probability"], flush=True)
    return {"ok": all(case["passed"] for case in cases), "mode": "auto", "controlled_evidence": True, "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthesis", action="store_true", help="Also call the configured main model for evidence-only synthesis")
    parser.add_argument("--auto-synthesis-only", action="store_true", help="Verify automatic synthesis judgments using controlled retained evidence")
    parser.add_argument("--output", default=".smart-search/jev-tests/live-report.json")
    args = parser.parse_args()
    report = asyncio.run(verify_auto_synthesis(args.synthesis) if args.auto_synthesis_only else verify(args.synthesis))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {path.resolve()}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
