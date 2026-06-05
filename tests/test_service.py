import json
import time

import httpx
import pytest

from smart_search import service


def _reset_config(monkeypatch, tmp_path):
    fake_config_file = tmp_path / "config.json"
    monkeypatch.setattr(service.config, "_config_file", fake_config_file)
    monkeypatch.setattr(service.config, "_cached_model", None)
    for key in [
        "XAI_API_URL",
        "XAI_API_KEY",
        "XAI_MODEL",
        "XAI_TOOLS",
        "OPENAI_COMPATIBLE_API_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_STREAM",
        "EXA_API_KEY",
        "EXA_BASE_URL",
        "ANYSEARCH_API_KEY",
        "ANYSEARCH_API_URL",
        "ANYSEARCH_TIMEOUT_SECONDS",
        "ZHIPU_API_KEY",
        "ZHIPU_API_URL",
        "ZHIPU_SEARCH_ENGINE",
        "ZHIPU_TIMEOUT_SECONDS",
        "ZHIPU_MCP_API_KEY",
        "ZHIPU_MCP_SEARCH_API_URL",
        "ZHIPU_MCP_READER_API_URL",
        "ZHIPU_MCP_ZREAD_API_URL",
        "ZHIPU_MCP_TIMEOUT_SECONDS",
        "JINA_API_KEY",
        "JINA_READER_API_URL",
        "JINA_RESPOND_WITH",
        "JINA_TIMEOUT_SECONDS",
        "TAVILY_API_KEY",
        "TAVILY_API_URL",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    return fake_config_file


def test_model_set_is_removed_and_current_reports_explicit_models(monkeypatch, tmp_path):
    fake_config_file = _reset_config(monkeypatch, tmp_path)

    service.config_set("XAI_MODEL", "xai-model")
    service.config_set("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    service.config_set("OPENAI_COMPATIBLE_MODEL", "relay-model")

    set_result = service.set_model("legacy-model")
    current_result = service.current_model()

    assert set_result["ok"] is False
    assert set_result["error_type"] == "parameter_error"
    assert "XAI_MODEL" in set_result["error"]
    assert current_result["xai_model"] == "xai-model"
    assert current_result["openai_compatible_model"] == "relay-model"
    assert current_result["config_file"] == str(fake_config_file)


def test_config_set_list_unset_and_path(monkeypatch, tmp_path):
    fake_config_file = _reset_config(monkeypatch, tmp_path)

    set_result = service.config_set("XAI_API_KEY", "xai-test-secret")
    list_result = service.config_list()
    path_result = service.config_path()

    assert set_result["ok"] is True
    assert set_result["value"].startswith("xai-")
    assert "secret" not in json.dumps(list_result)
    assert list_result["values"]["XAI_API_KEY"].startswith("xai-")
    assert path_result["config_file"] == str(fake_config_file)

    unset_result = service.config_unset("XAI_API_KEY")
    assert unset_result["ok"] is True
    assert "XAI_API_KEY" not in service.config_list()["values"]


def test_config_file_supplies_explicit_main_settings(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    service.config_set("XAI_API_URL", "https://xai.example.com/v1")
    service.config_set("XAI_API_KEY", "xai-config-secret")
    service.config_set("XAI_MODEL", "xai-config-model")
    service.config_set("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    service.config_set("OPENAI_COMPATIBLE_API_KEY", "relay-config-secret")
    service.config_set("OPENAI_COMPATIBLE_MODEL", "relay-config-model")

    assert service.config.xai_api_url == "https://xai.example.com/v1"
    assert service.config.xai_api_key == "xai-config-secret"
    assert service.config.xai_model == "xai-config-model"
    assert service.config.openai_compatible_api_url == "https://relay.example.com/v1"
    assert service.config.openai_compatible_api_key == "relay-config-secret"
    assert service.config.openai_compatible_model == "relay-config-model"


def test_openai_compatible_stream_config_defaults_and_boolean_styles(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    assert service.config.openai_compatible_stream is False

    for value in ["true", "1", "yes"]:
        monkeypatch.setenv("OPENAI_COMPATIBLE_STREAM", value)
        assert service.config.openai_compatible_stream is True

    monkeypatch.setenv("OPENAI_COMPATIBLE_STREAM", "false")
    assert service.config.openai_compatible_stream is False


def test_anysearch_config_defaults_and_saved_values(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    assert service.config.anysearch_api_url == "https://api.anysearch.com/mcp"
    assert service.config.anysearch_api_key is None
    assert service.config.anysearch_timeout == 30.0

    service.config_set("ANYSEARCH_API_URL", "https://anysearch.example.com/mcp")
    service.config_set("ANYSEARCH_API_KEY", "as-test-secret")
    service.config_set("ANYSEARCH_TIMEOUT_SECONDS", "9")

    assert service.config.anysearch_api_url == "https://anysearch.example.com/mcp"
    assert service.config.anysearch_api_key == "as-test-secret"
    assert service.config.anysearch_timeout == 9.0


def test_jina_and_zhipu_mcp_config_defaults_and_saved_values(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    assert service.config.jina_reader_api_url == "https://r.jina.ai"
    assert service.config.jina_api_key is None
    assert service.config.jina_respond_with == ""
    assert service.config.jina_timeout == 30.0
    assert service.config.zhipu_mcp_search_api_url == "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    assert service.config.zhipu_mcp_reader_api_url == "https://open.bigmodel.cn/api/mcp/web_reader/mcp"
    assert service.config.zhipu_mcp_zread_api_url == "https://open.bigmodel.cn/api/mcp/zread/mcp"

    service.config_set("JINA_API_KEY", "jina-test-secret")
    service.config_set("JINA_READER_API_URL", "https://reader.example.com")
    service.config_set("JINA_RESPOND_WITH", "readerlm-v2")
    service.config_set("JINA_TIMEOUT_SECONDS", "11")
    service.config_set("ZHIPU_MCP_API_KEY", "zmcp-test-secret")
    service.config_set("ZHIPU_MCP_SEARCH_API_URL", "https://zmcp.example.com/search")
    service.config_set("ZHIPU_MCP_READER_API_URL", "https://zmcp.example.com/reader")
    service.config_set("ZHIPU_MCP_ZREAD_API_URL", "https://zmcp.example.com/zread")
    service.config_set("ZHIPU_MCP_TIMEOUT_SECONDS", "12")

    assert service.config.jina_api_key == "jina-test-secret"
    assert service.config.jina_reader_api_url == "https://reader.example.com"
    assert service.config.jina_respond_with == "readerlm-v2"
    assert service.config.jina_timeout == 11.0
    assert service.config.zhipu_mcp_api_key == "zmcp-test-secret"
    assert service.config.zhipu_mcp_search_api_url == "https://zmcp.example.com/search"
    assert service.config.zhipu_mcp_reader_api_url == "https://zmcp.example.com/reader"
    assert service.config.zhipu_mcp_zread_api_url == "https://zmcp.example.com/zread"
    assert service.config.zhipu_mcp_timeout == 12.0


def test_environment_overrides_config_file(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    service.config_set("OPENAI_COMPATIBLE_API_URL", "https://config.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://env.example.com/v1")

    assert service.config.openai_compatible_api_url == "https://env.example.com/v1"
    assert service.config.get_config_source("OPENAI_COMPATIBLE_API_URL") == "environment"
    assert service.config.get_config_source("OPENAI_COMPATIBLE_API_KEY") == "default"


def test_config_sources_report_config_file(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    service.config_set("XAI_API_KEY", "xai-config-secret")

    sources = service.config.get_config_sources()

    assert sources["XAI_API_KEY"] == "config_file"
    assert sources["XAI_API_URL"] == "default"


def test_deep_research_plan_current_market_is_offline_and_fetch_before_claim(monkeypatch):
    async def should_not_run_provider(*args, **kwargs):
        raise AssertionError("build_deep_research_plan must not call live providers")

    monkeypatch.setattr(service, "search", should_not_run_provider)
    monkeypatch.setattr(service, "fetch", should_not_run_provider)
    monkeypatch.setattr(service, "exa_search", should_not_run_provider)
    monkeypatch.setattr(service, "zhipu_search", should_not_run_provider)

    result = service.build_deep_research_plan(
        "深度搜索一下最近的比特币行情",
        evidence_dir="C:/tmp/smart-search-evidence/test-market",
    )

    assert result["ok"] is True
    assert result["mode"] == "deep_research"
    assert result["query_mode"] == "deep"
    assert result["trigger_source"] == "explicit_cli"
    assert result["intent_signals"]["recency_requirement"] in {"recent", "current"}
    assert result["intent_signals"]["claim_risk"] == "high"
    assert result["evidence_policy"] == "fetch_before_claim"
    assert result["preflight"]["executed_by_deep_command"] is False
    tools = {step["tool"] for step in result["steps"]}
    assert {"search", "fetch"} <= tools
    assert "zhipu-search" in tools
    assert "exa-search" not in tools
    assert tools <= service.DEEP_ALLOWED_TOOLS
    assert all(step["subquestion_id"] for step in result["steps"])


def test_deep_research_plan_complex_docs_query_has_decomposition():
    result = service.build_deep_research_plan(
        "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选",
        budget="deep",
        evidence_dir="C:/tmp/smart-search-evidence/test-openai",
    )

    assert result["difficulty"] == "high"
    assert result["intent_signals"]["docs_api_intent"] is True
    assert len(result["decomposition"]) >= 4
    tools = [step["tool"] for step in result["steps"]]
    assert {"search", "context7-library", "context7-docs", "fetch"} <= set(tools)
    assert "exa-search" not in tools
    assert result["gap_check"]["unsupported_claim_action"] == "downgrade_to_unverified_candidate"


def test_deep_research_plan_docs_official_domain_can_add_exa_after_context7():
    result = service.build_deep_research_plan(
        "React useEffect 官方 API docs",
        budget="deep",
        evidence_dir="C:/tmp/smart-search-evidence/test-react-official",
    )

    tools = [step["tool"] for step in result["steps"]]
    assert {"context7-library", "context7-docs", "exa-search"} <= set(tools)
    assert tools.index("context7-library") < tools.index("exa-search")
    assert tools.index("context7-docs") < tools.index("exa-search")


def test_deep_research_plan_url_first_starts_with_fetch():
    result = service.build_deep_research_plan(
        "https://example.com/source",
        evidence_dir="C:/tmp/smart-search-evidence/test-url",
    )

    assert result["intent_signals"]["known_url"] is True
    assert result["difficulty"] == "standard"
    assert result["steps"][0]["tool"] == "fetch"
    assert "https://example.com/source" in result["steps"][0]["command"]
    assert any(step["tool"] == "exa-similar" for step in result["steps"])


def test_deep_research_claim_verification_does_not_unconditionally_add_exa():
    result = service.build_deep_research_plan(
        "帮我核验这个说法是真是假",
        evidence_dir="C:/tmp/smart-search-evidence/test-claim",
    )

    tools = {step["tool"] for step in result["steps"]}
    assert result["intent_signals"]["cross_validation_need"] == "high"
    assert {"search", "fetch"} <= tools
    assert "exa-search" not in tools


def test_deep_research_quick_budget_keeps_fetch_and_valid_subquestion_links():
    result = service.build_deep_research_plan(
        "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选",
        budget="quick",
        evidence_dir="C:/tmp/smart-search-evidence/test-quick",
    )

    subquestion_ids = {item["id"] for item in result["decomposition"]}
    assert len(result["steps"]) <= 4
    assert any(step["tool"] == "fetch" for step in result["steps"])
    assert all(step["subquestion_id"] in subquestion_ids for step in result["steps"])
    for step in result["steps"]:
        assert step["output_path"] in step["command"]


def _configure_research_minimum(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("CONTEXT7_API_KEY", "ctx-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("JINA_API_KEY", "jina-secret")


def _research_plan(query: str) -> dict:
    return service.build_deep_research_plan(query, budget="deep", evidence_dir="C:/tmp/smart-search-evidence/test")


def test_research_provider_profiles_are_registered_with_capability_boundaries():
    profiles = service.provider_profiles()

    assert profiles["jina"]["capability"] == "web_fetch"
    assert "web_fetch" in profiles["tavily"]["capabilities"]
    assert "web_search" in profiles["firecrawl"]["capabilities"]
    assert profiles["jina"]["fallback_group"] == "web_fetch"
    assert profiles["jina"]["minimum_profile_role"] == "web_fetch_with_key"
    assert "challenge page rejection" in profiles["jina"]["quality_filters"]
    assert "known URL extraction" in profiles["jina"]["route_reasons"]
    assert profiles["anysearch"]["experimental"] is True


def test_research_router_prefers_context7_for_docs_and_keeps_anysearch_out(monkeypatch):
    _configure_research_minimum(monkeypatch)

    routes = service._research_capability_routes("React useEffect API docs", _research_plan("React useEffect API docs"), "auto")

    assert routes["signals"]["docs_api_intent"] is True
    assert routes["capabilities"]["docs_search"]["providers"][:2] == ["context7", "exa"]
    assert routes["capabilities"]["vertical_search"]["providers"] == []


def test_research_router_uses_zhipu_for_chinese_current_policy(monkeypatch):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")

    routes = service._research_capability_routes("今天国内 AI 政策最新公告", _research_plan("今天国内 AI 政策最新公告"), "auto")

    assert routes["signals"]["current_or_locale_intent"] is True
    assert routes["capabilities"]["web_search"]["providers"][0] == "zhipu"


def test_research_router_favors_jina_for_known_url_pdf_and_firecrawl_for_dynamic(monkeypatch):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret")

    assert service._research_fetch_order("summarize https://arxiv.org/pdf/2401.00001.pdf")[0] == "jina"
    assert service._research_fetch_order("抓取这个 dynamic javascript cloudflare 页面", "https://example.com/app")[0] == "firecrawl"


def test_research_router_uses_anysearch_only_for_vertical_intent(monkeypatch):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("ANYSEARCH_API_KEY", "any-secret")

    generic = service._research_capability_routes("React useEffect API docs", _research_plan("React useEffect API docs"), "auto")
    vertical = service._research_capability_routes("CVE-2026 OpenSSL 漏洞影响范围", _research_plan("CVE-2026 OpenSSL 漏洞影响范围"), "auto")

    assert generic["capabilities"]["vertical_search"]["providers"] == []
    assert vertical["capabilities"]["vertical_search"]["providers"] == ["anysearch"]


def test_research_overrides_cannot_move_provider_across_capability(monkeypatch):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", "jina,zhipu,unknown-provider")
    monkeypatch.setenv("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", "tavily")

    routes = service._research_capability_routes("今天国内 AI 新闻", _research_plan("今天国内 AI 新闻"), "auto")

    assert "unknown-provider" in routes["invalid_provider_overrides"]
    assert "jina" not in routes["capabilities"]["web_search"]["providers"]
    assert "tavily" not in routes["capabilities"]["web_fetch"]["providers"]
    assert routes["capabilities"]["web_fetch"]["providers"][0] == "jina"


def test_research_fallback_detection_is_same_capability_only():
    cross_capability_attempts = [
        service._attempt("docs_search", "context7", "empty", time.time()),
        service._attempt("web_fetch", "jina", "ok", time.time(), result_count=1),
    ]
    same_capability_attempts = [
        service._attempt("web_fetch", "jina", "empty", time.time()),
        service._attempt("web_fetch", "firecrawl", "ok", time.time(), result_count=1),
    ]

    assert service._fallback_used(cross_capability_attempts) is False
    assert service._fallback_used(same_capability_attempts) is True


@pytest.mark.asyncio
async def test_research_executes_staged_evidence_only_workflow(monkeypatch, tmp_path):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")

    async def fake_web_search(query, count=5, providers="auto", fallback="auto"):
        return (
            [{"url": "https://evidence.example.com/source", "title": "Source", "provider": "zhipu"}],
            [service._attempt("web_search", "zhipu", "ok", time.time(), result_count=1)],
        )

    async def fake_fetch(url, fallback="auto", preferred_order=None):
        return (
            {"ok": True, "url": url, "provider": "jina", "content": "# Evidence\nFetched body only."},
            [service._attempt("web_fetch", "jina", "ok", time.time(), result_count=1)],
        )

    monkeypatch.setattr(service, "_run_web_search_fallback", fake_web_search)
    monkeypatch.setattr(service, "_run_web_fetch_fallback", fake_fetch)

    result = await service.research("今天国内 AI 新闻", evidence_dir=str(tmp_path), fallback="auto")

    assert result["ok"] is True
    assert result["query_mode"] == "research"
    assert result["route_policy_version"] == service.RESEARCH_ROUTE_POLICY_VERSION
    assert result["evidence_items"][0]["url"] == "https://evidence.example.com/source"
    assert result["citations"] == [{"url": "https://evidence.example.com/source", "title": "Source", "provider": "jina"}]
    assert "Fetched body only" in result["final_answer"]
    assert "zhipu" in [attempt["provider"] for attempt in result["provider_attempts"]]
    assert (tmp_path / "summary.json").exists()


@pytest.mark.asyncio
async def test_research_reports_degraded_gaps_without_citing_discovery_candidates(monkeypatch, tmp_path):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")

    async def fake_web_search(query, count=5, providers="auto", fallback="auto"):
        return (
            [{"url": "https://candidate.example.com", "title": "Candidate", "provider": "zhipu"}],
            [service._attempt("web_search", "zhipu", "ok", time.time(), result_count=1)],
        )

    async def fake_fetch(url, fallback="auto", preferred_order=None):
        return (
            None,
            [
                service._attempt("web_fetch", "jina", "empty", time.time()),
                service._attempt("web_fetch", "tavily", "empty", time.time()),
            ],
        )

    monkeypatch.setattr(service, "_run_web_search_fallback", fake_web_search)
    monkeypatch.setattr(service, "_run_web_fetch_fallback", fake_fetch)

    result = await service.research("今天国内 AI 新闻", evidence_dir=str(tmp_path), fallback="auto")

    assert result["ok"] is False
    assert result["degraded"] is True
    assert result["citations"] == []
    assert result["evidence_items"] == []
    assert result["gap_check"]["status"] == "failed"
    assert result["fallback_used"] is True
    assert "no fetched/read evidence" in result["gap_check"]["gaps"][-1]["reason"]


@pytest.mark.asyncio
async def test_research_fallback_off_limits_same_capability_fetch(monkeypatch, tmp_path):
    _configure_research_minimum(monkeypatch)

    async def fake_fetch(url, fallback="auto", preferred_order=None):
        attempts = [service._attempt("web_fetch", preferred_order[0], "empty", time.time())]
        return None, attempts

    async def should_not_discover(*args, **kwargs):
        raise AssertionError("known URL with fallback off should not need discovery after fetch failure")

    monkeypatch.setattr(service, "_run_web_fetch_fallback", fake_fetch)
    monkeypatch.setattr(service, "_run_web_search_fallback", should_not_discover)

    result = await service.research("https://example.com/source", evidence_dir=str(tmp_path), fallback="off")

    fetch_attempts = [attempt for attempt in result["provider_attempts"] if attempt["capability"] == "web_fetch"]
    assert [attempt["provider"] for attempt in fetch_attempts] == ["jina"]
    assert result["fallback_used"] is False
    assert result["gap_check"]["status"] == "failed"


@pytest.mark.asyncio
async def test_research_fallback_off_does_not_run_supplemental_exa(monkeypatch, tmp_path):
    _configure_research_minimum(monkeypatch)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-secret")

    async def fake_context7_library(*args, **kwargs):
        return {"ok": False, "error_type": "", "error": "", "results": []}

    async def fail_exa(*args, **kwargs):
        raise AssertionError("research --fallback off must not run supplemental Exa outside the selected route")

    async def fake_web_search(query, count=5, providers="auto", fallback="auto"):
        return (
            [{"url": "https://official.example.com/source", "title": "Official", "provider": "zhipu"}],
            [service._attempt("web_search", "zhipu", "ok", time.time(), result_count=1)],
        )

    async def fake_fetch(url, fallback="auto", preferred_order=None):
        return (
            {"ok": True, "url": url, "provider": preferred_order[0], "content": "# Evidence\nOfficial body."},
            [service._attempt("web_fetch", preferred_order[0], "ok", time.time(), result_count=1)],
        )

    monkeypatch.setattr(service, "context7_library", fake_context7_library)
    monkeypatch.setattr(service, "exa_search", fail_exa)
    monkeypatch.setattr(service, "_run_web_search_fallback", fake_web_search)
    monkeypatch.setattr(service, "_run_web_fetch_fallback", fake_fetch)

    result = await service.research("React official API docs", evidence_dir=str(tmp_path), fallback="off")

    assert result["ok"] is True
    assert all(attempt["provider"] != "exa" for attempt in result["provider_attempts"])


def test_legacy_main_search_config_keys_are_rejected(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    for key in [
        "SMART_SEARCH_API_URL",
        "SMART_SEARCH_API_KEY",
        "SMART_SEARCH_API_MODE",
        "SMART_SEARCH_MODEL",
        "SMART_SEARCH_XAI_TOOLS",
    ]:
        result = service.config_set(key, "legacy")
        assert result["ok"] is False
        assert result["error_type"] == "parameter_error"
        assert f"Unsupported config key: {key}" in result["error"]


def test_legacy_main_search_config_keys_are_ignored_from_saved_config(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    service.config._save_config_file(
        {
            "SMART_SEARCH_API_URL": "https://legacy.example.com/v1",
            "SMART_SEARCH_API_KEY": "legacy-secret",
            "XAI_API_KEY": "xai-config-secret",
        }
    )

    saved = service.config_list()["values"]

    assert "SMART_SEARCH_API_URL" not in saved
    assert "SMART_SEARCH_API_KEY" not in saved
    assert saved["XAI_API_KEY"].startswith("xai-")


def test_xai_tools_validation(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    service.config_set("XAI_TOOLS", "web_search,x_search,web_search")
    assert service.config.parse_xai_tools() == ["web_search", "x_search"]

    service.config_set("XAI_TOOLS", "web_search,bad_tool")
    with pytest.raises(ValueError, match="Invalid XAI_TOOLS"):
        service.config.parse_xai_tools()


@pytest.mark.asyncio
async def test_zhipu_search_uses_configured_engine_and_command_override(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)
    service.config_set("ZHIPU_API_KEY", "zhipu-test-secret")
    service.config_set("ZHIPU_API_URL", "https://zhipu.example.com/api")
    service.config_set("ZHIPU_SEARCH_ENGINE", "search_pro")
    calls = []

    class FakeZhipuProvider:
        def __init__(self, api_url, api_key, search_engine, timeout):
            self.api_url = api_url
            self.api_key = api_key
            self.search_engine = search_engine
            self.timeout = timeout
            calls.append({"init_engine": search_engine, "api_url": api_url})

        async def search(self, **kwargs):
            calls[-1]["call_engine"] = kwargs.get("search_engine")
            engine = kwargs.get("search_engine") or self.search_engine
            return json.dumps({"ok": True, "search_engine": engine, "results": [], "elapsed_ms": 1})

    monkeypatch.setattr(service, "ZhipuWebSearchProvider", FakeZhipuProvider)

    configured_result = await service.zhipu_search("test")
    override_result = await service.zhipu_search("test", search_engine="search_pro_quark")

    assert configured_result["search_engine"] == "search_pro"
    assert override_result["search_engine"] == "search_pro_quark"
    assert calls == [
        {"init_engine": "search_pro", "api_url": "https://zhipu.example.com/api", "call_engine": None},
        {"init_engine": "search_pro_quark", "api_url": "https://zhipu.example.com/api", "call_engine": "search_pro_quark"},
    ]


@pytest.mark.asyncio
async def test_search_returns_sources(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return 'Answer.\n\nsources([{"url":"https://example.com","title":"Example"}])'

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "call_tavily_search", lambda *a, **k: None)
    monkeypatch.setattr(service, "call_firecrawl_search", lambda *a, **k: None)

    result = await service.search("what is example")

    assert result["ok"] is True
    assert result["primary_api_mode"] == "chat-completions"
    assert result["content"] == "Answer."
    assert result["sources_count"] == 1
    assert result["primary_sources_count"] == 1
    assert result["extra_sources_count"] == 0
    assert result["sources"][0]["url"] == "https://example.com"
    assert result["primary_sources"][0]["url"] == "https://example.com"
    assert result["extra_sources"] == []
    assert result["source_warning"] == ""


@pytest.mark.asyncio
async def test_search_splits_primary_and_extra_sources(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return 'Answer.\n\nsources([{"url":"https://primary.example.com","title":"Primary"}])'

    async def fake_tavily_search(query, max_results=6):
        return [{"url": "https://extra.example.com", "title": "Extra", "content": "candidate"}]

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "call_tavily_search", fake_tavily_search)
    monkeypatch.setattr(service, "call_firecrawl_search", lambda *a, **k: None)

    result = await service.search("what is example", extra_sources=1)

    assert result["ok"] is True
    assert result["sources_count"] == 2
    assert result["primary_sources_count"] == 1
    assert result["extra_sources_count"] == 1
    assert result["primary_sources"][0]["url"] == "https://primary.example.com"
    assert result["extra_sources"][0]["url"] == "https://extra.example.com"
    assert result["extra_sources"][0]["provider"] == "tavily"
    assert "not automatically used to verify generated content" in result["source_warning"]


@pytest.mark.asyncio
async def test_search_uses_xai_responses_for_explicit_xai_config(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    captured = {}

    async def fake_search(self, query, platform="", ctx=None):
        captured["provider"] = self.__class__.__name__
        captured["tools"] = self.tools
        return "Answer [[1]](https://example.com)."

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "call_tavily_search", lambda *a, **k: None)
    monkeypatch.setattr(service, "call_firecrawl_search", lambda *a, **k: None)

    result = await service.search("what is example")

    assert result["ok"] is True
    assert result["primary_api_mode"] == "xai-responses"
    assert captured["provider"] == "XAIResponsesSearchProvider"
    assert captured["tools"] == ["web_search", "x_search"]
    assert result["sources"][0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_search_fallbacks_from_xai_responses_to_openai_compatible(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    monkeypatch.setenv("XAI_MODEL", "xai-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "relay-model")
    captured = []

    async def failing_xai(self, query, platform="", ctx=None):
        captured.append((self.__class__.__name__, self.api_url, self.api_key, self.model))
        request = httpx.Request("POST", "https://api.x.ai/v1/responses")
        response = httpx.Response(503, text="responses unavailable", request=request)
        raise httpx.HTTPStatusError("responses unavailable", request=request, response=response)

    async def fallback_openai(self, query, platform="", ctx=None):
        captured.append((self.__class__.__name__, self.api_url, self.api_key, self.model))
        return 'Fallback answer.\n\nsources([{"url":"https://fallback.example.com","title":"Fallback"}])'

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", failing_xai)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fallback_openai)

    result = await service.search("what is example")

    assert result["ok"] is True
    assert result["content"] == "Fallback answer."
    assert result["fallback_used"] is True
    assert [a["provider"] for a in result["provider_attempts"][:2]] == ["xAI Responses", "OpenAI-compatible"]
    assert result["provider_attempts"][0]["status"] == "error"
    assert result["provider_attempts"][1]["status"] == "ok"
    assert result["primary_api_mode"] == "chat-completions"
    assert result["model"] == "relay-model"
    assert result["routing_decision"]["main_search_chain"] == ["xai-responses", "openai-compatible"]
    assert captured == [
        ("XAIResponsesSearchProvider", "https://api.x.ai/v1", "xai-test-secret", "xai-model"),
        ("OpenAICompatibleSearchProvider", "https://relay.example.com/v1", "relay-test-secret", "relay-model"),
    ]


@pytest.mark.asyncio
async def test_search_does_not_fake_openai_compatible_fallback_when_only_xai_configured(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")

    async def failing_xai(self, query, platform="", ctx=None):
        request = httpx.Request("POST", "https://api.x.ai/v1/responses")
        response = httpx.Response(503, text="responses unavailable", request=request)
        raise httpx.HTTPStatusError("responses unavailable", request=request, response=response)

    async def should_not_run(self, query, platform="", ctx=None):
        raise AssertionError("OpenAI-compatible fallback requires its own configured URL and key")

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", failing_xai)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", should_not_run)

    result = await service.search("what is example")

    assert result["ok"] is False
    assert result["fallback_used"] is False
    assert [a["provider"] for a in result["provider_attempts"]] == ["xAI Responses"]


@pytest.mark.asyncio
async def test_search_accepts_only_openai_compatible_as_main_provider(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Relay answer."

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)

    result = await service.search("what is example")

    assert result["ok"] is True
    assert result["primary_api_mode"] == "chat-completions"
    assert result["routing_decision"]["main_search_chain"] == ["openai-compatible"]
    assert result["capability_status"]["main_search"]["configured"] == ["openai-compatible"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_stream", "override_stream", "expected_stream"),
    [
        ("true", None, True),
        ("false", True, True),
        ("true", False, False),
    ],
)
async def test_search_passes_openai_compatible_stream_config_and_cli_override(monkeypatch, config_stream, override_stream, expected_stream):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_STREAM", config_stream)
    captured = {}

    async def fake_search(self, query, platform="", ctx=None):
        captured["stream"] = self.stream
        return "Relay answer."

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)

    kwargs = {} if override_stream is None else {"stream": override_stream}
    result = await service.search("what is example", **kwargs)

    assert result["ok"] is True
    assert captured["stream"] is expected_stream
    assert result["routing_decision"]["openai_compatible_stream"] is expected_stream


def test_anysearch_vertical_status_is_experimental_and_not_minimum_required(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")
    monkeypatch.delenv("ANYSEARCH_API_KEY", raising=False)

    without_anysearch = service.validate_minimum_profile()
    assert without_anysearch["ok"] is True
    assert without_anysearch["capability_status"]["vertical_search"]["configured"] == []
    assert without_anysearch["capability_status"]["vertical_search"]["experimental"] is True

    monkeypatch.setenv("ANYSEARCH_API_KEY", "as-test-secret")
    with_anysearch = service.validate_minimum_profile()
    assert with_anysearch["ok"] is True
    assert with_anysearch["missing"] == []
    assert with_anysearch["required"] == ["main_search", "docs_search", "web_fetch"]
    assert with_anysearch["capability_status"]["vertical_search"]["configured"] == ["anysearch"]


def test_jina_key_satisfies_web_fetch_but_anonymous_jina_does_not(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.setenv("JINA_READER_API_URL", "https://r.jina.ai")

    without_key = service.validate_minimum_profile()
    assert without_key["ok"] is False
    assert "web_fetch" in without_key["missing"]
    assert "jina" not in without_key["capability_status"]["web_fetch"]["configured"]

    monkeypatch.setenv("JINA_API_KEY", "jina-test-secret")
    with_key = service.validate_minimum_profile()
    assert with_key["ok"] is True
    assert with_key["missing"] == []
    assert with_key["capability_status"]["web_fetch"]["configured"] == ["jina"]


def test_zhipu_mcp_key_satisfies_web_search_and_reader_fetch_as_separate_provider(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zmcp-test-secret")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    result = service.validate_minimum_profile()

    assert result["ok"] is True
    assert result["missing"] == []
    assert result["capability_status"]["web_search"]["configured"] == ["zhipu-mcp"]
    assert result["capability_status"]["web_search"]["fallback_chain"] == ["zhipu", "zhipu-mcp", "tavily", "firecrawl"]
    assert result["capability_status"]["web_fetch"]["configured"] == ["zhipu-mcp-reader"]


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_error_records_attempt_and_falls_back_same_capability(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_MINIMUM_PROFILE", "standard")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test-secret")
    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zmcp-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Answer."

    async def failing_zhipu_mcp(query, count=5):
        return {
            "ok": False,
            "provider": "zhipu-mcp",
            "tool": "web_search_prime",
            "error_type": "provider_error",
            "error": "provider unavailable",
        }

    async def yes_tavily(query, max_results=6):
        return [{"url": "https://fallback.example.com", "title": "Fallback", "content": "fallback source"}]

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "zhipu_mcp_search", failing_zhipu_mcp)
    monkeypatch.setattr(service, "call_tavily_search", yes_tavily)

    result = await service.search("latest MCP status", validation="strict")

    web_attempts = [attempt for attempt in result["provider_attempts"] if attempt["capability"] == "web_search"]
    assert result["ok"] is True
    assert [attempt["provider"] for attempt in web_attempts[:2]] == ["zhipu-mcp", "tavily"]
    assert web_attempts[0]["status"] == "error"
    assert web_attempts[0]["error_type"] == "provider_error"
    assert web_attempts[1]["status"] == "ok"
    assert result["extra_sources"][0]["provider"] == "tavily"


@pytest.mark.asyncio
async def test_search_provider_filter_can_select_openai_compatible(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def should_not_run(self, query, platform="", ctx=None):
        raise AssertionError("xAI should be filtered out")

    async def fallback_openai(self, query, platform="", ctx=None):
        return "Relay answer."

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", should_not_run)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fallback_openai)

    result = await service.search("what is example", providers="openai-compatible")

    assert result["ok"] is True
    assert result["routing_decision"]["main_search_chain"] == ["openai-compatible"]
    assert [a["provider"] for a in result["provider_attempts"]] == ["OpenAI-compatible"]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["nba战报", "NBA比分", "今日赛程"])
async def test_balanced_current_sports_queries_use_web_search_reinforcement(monkeypatch, query):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Sports answer."

    async def fake_tavily_search(query, max_results=6):
        return [{"url": "https://sports.example.com", "title": "Sports", "content": "score"}]

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "call_tavily_search", fake_tavily_search)

    result = await service.search(query, validation="balanced")

    assert result["ok"] is True
    assert result["routing_decision"]["zh_current_intent"] is True
    assert result["routing_decision"]["web_current_intent"] is True
    assert "web_search" in result["routing_decision"]["supplemental_paths"]
    assert any(attempt["capability"] == "web_search" and attempt["status"] == "ok" for attempt in result["provider_attempts"])
    assert result["extra_sources"][0]["url"] == "https://sports.example.com"


@pytest.mark.asyncio
async def test_chinese_language_request_does_not_trigger_current_web_search(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Language answer."

    async def should_not_run_web_search(query, count=5, providers="auto", fallback="auto"):
        raise AssertionError("generic Chinese-language requests should not trigger current web_search")

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "_run_web_search_fallback", should_not_run_web_search)

    result = await service.search("中文解释 Python 函数", validation="balanced")

    assert result["ok"] is True
    assert result["routing_decision"]["web_current_intent"] is False
    assert "web_search" not in result["routing_decision"]["supplemental_paths"]
    assert all(attempt["capability"] != "web_search" for attempt in result["provider_attempts"])


@pytest.mark.asyncio
async def test_docs_query_routes_docs_without_current_web_search(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Docs answer."

    async def fake_docs_search(query, providers="auto", fallback="auto"):
        return [{"url": "context7:/facebook/react", "provider": "context7"}], [
            {"capability": "docs_search", "provider": "context7", "status": "ok", "elapsed_ms": 1, "result_count": 1}
        ]

    async def should_not_run_web_search(query, count=5, providers="auto", fallback="auto"):
        raise AssertionError("docs query should not trigger current web_search")

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "_run_docs_search_fallback", fake_docs_search)
    monkeypatch.setattr(service, "_run_web_search_fallback", should_not_run_web_search)

    result = await service.search("React useEffect API docs 中文解释", validation="balanced")

    assert result["ok"] is True
    assert result["routing_decision"]["docs_intent"] is True
    assert result["routing_decision"]["web_current_intent"] is False
    assert result["routing_decision"]["supplemental_paths"] == ["docs_search"]
    assert any(attempt["capability"] == "docs_search" for attempt in result["provider_attempts"])
    assert all(attempt["capability"] != "web_search" for attempt in result["provider_attempts"])


@pytest.mark.asyncio
async def test_strict_still_uses_web_search_without_current_keyword(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Strict answer."

    async def fake_tavily_search(query, max_results=6):
        return [{"url": "https://strict.example.com", "title": "Strict", "content": "evidence"}]

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "call_tavily_search", fake_tavily_search)

    result = await service.search("plain evergreen query", validation="strict")

    assert result["ok"] is True
    assert result["routing_decision"]["web_current_intent"] is False
    assert "web_search" in result["routing_decision"]["supplemental_paths"]
    assert any(attempt["capability"] == "web_search" and attempt["status"] == "ok" for attempt in result["provider_attempts"])


@pytest.mark.asyncio
async def test_search_respects_fallback_off_for_main_search(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def failing_xai(self, query, platform="", ctx=None):
        request = httpx.Request("POST", "https://api.x.ai/v1/responses")
        response = httpx.Response(503, text="responses unavailable", request=request)
        raise httpx.HTTPStatusError("responses unavailable", request=request, response=response)

    async def should_not_run(self, query, platform="", ctx=None):
        raise AssertionError("OpenAI-compatible fallback should not run when fallback is off")

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", failing_xai)
    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", should_not_run)

    result = await service.search("what is example", fallback="off")

    assert result["ok"] is False
    assert result["fallback_used"] is False
    assert [a["provider"] for a in result["provider_attempts"]] == ["xAI Responses"]


@pytest.mark.asyncio
async def test_search_reports_invalid_xai_tools_as_parameter_error(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    monkeypatch.setenv("XAI_TOOLS", "web_search,code_interpreter")

    result = await service.search("what is example")

    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert "Invalid XAI_TOOLS" in result["error"]
    assert result["primary_sources"] == []
    assert result["extra_sources"] == []


@pytest.mark.asyncio
async def test_search_reports_primary_provider_http_error(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")

    async def failing_search(self, query, platform="", ctx=None):
        request = httpx.Request("POST", "https://api.x.ai/v1/responses")
        response = httpx.Response(422, text="bad tools", request=request)
        raise httpx.HTTPStatusError("bad response", request=request, response=response)

    async def should_not_hide_failure(*args, **kwargs):
        return [{"url": "https://extra.example.com"}]

    monkeypatch.setattr(service.XAIResponsesSearchProvider, "search", failing_search)
    monkeypatch.setattr(service, "call_tavily_search", should_not_hide_failure)

    result = await service.search("what is example", extra_sources=1, fallback="off")

    assert result["ok"] is False
    assert result["error_type"] == "network_error"
    assert result["primary_api_mode"] == "xai-responses"
    assert "xAI Responses HTTP 422" in result["error"]
    assert "bad tools" in result["error"]
    assert result["sources"] == []
    assert result["primary_sources"] == []
    assert result["extra_sources"] == []


@pytest.mark.asyncio
async def test_fetch_prefers_tavily(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")

    async def yes_tavily(url):
        return "# Tavily Page"

    async def no_firecrawl(url, ctx=None):
        raise AssertionError("Firecrawl should not run when Tavily succeeds")

    monkeypatch.setattr(service, "call_tavily_extract", yes_tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", no_firecrawl)

    result = await service.fetch("https://example.com")

    assert result["ok"] is True
    assert result["provider"] == "tavily"
    assert result["content"] == "# Tavily Page"


@pytest.mark.asyncio
async def test_fetch_fallbacks_to_firecrawl(monkeypatch):
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
    assert result["content"] == "# Page"


@pytest.mark.asyncio
async def test_fetch_uses_shared_chain_and_falls_back_after_jina_quality_error(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("JINA_API_KEY", "jina-secret")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret")

    async def no_tavily(url):
        return None

    async def bad_jina(url):
        return {"ok": False, "provider": "jina", "error_type": "quality_error", "error": "challenge"}

    async def yes_firecrawl(url, ctx=None):
        return "# Page"

    monkeypatch.setattr(service, "call_tavily_extract", no_tavily)
    monkeypatch.setattr(service, "jina_fetch", bad_jina)
    monkeypatch.setattr(service, "call_firecrawl_scrape", yes_firecrawl)

    result = await service.fetch("https://example.com")

    assert result["ok"] is True
    assert result["provider"] == "firecrawl"
    assert [a["provider"] for a in result["provider_attempts"]] == ["tavily", "jina", "firecrawl"]
    assert result["provider_attempts"][1]["error_type"] == "quality_error"


@pytest.mark.asyncio
async def test_search_known_url_uses_same_fetch_chain_as_fetch(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    monkeypatch.setenv("JINA_API_KEY", "jina-secret")

    async def fake_search(self, query, platform="", ctx=None):
        return "Answer."

    captured = {}

    async def yes_jina(url):
        captured["url"] = url
        return {"ok": True, "provider": "jina", "url": url, "content": "# Jina Page"}

    monkeypatch.setattr(service.OpenAICompatibleSearchProvider, "search", fake_search)
    monkeypatch.setattr(service, "jina_fetch", yes_jina)

    result = await service.search("请抓取 https://example.com/docs?x=1 后总结", validation="balanced")

    assert result["ok"] is True
    assert captured["url"] == "https://example.com/docs?x=1"
    attempts = [a for a in result["provider_attempts"] if a["capability"] == "web_fetch"]
    assert [a["provider"] for a in attempts] == ["jina"]
    assert result["extra_sources"][0]["provider"] == "jina"


@pytest.mark.asyncio
async def test_fetch_reports_config_error_without_extract_keys(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    async def no_tavily(url):
        return None

    async def no_firecrawl(url, ctx=None):
        return None

    monkeypatch.setattr(service, "call_tavily_extract", no_tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", no_firecrawl)

    result = await service.fetch("https://example.com")

    assert result["ok"] is False
    assert result["error_type"] == "config_error"


@pytest.mark.asyncio
async def test_fetch_reports_network_error_when_providers_fail(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-secret")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret")

    async def no_tavily(url):
        return None

    async def no_firecrawl(url, ctx=None):
        return None

    monkeypatch.setattr(service, "call_tavily_extract", no_tavily)
    monkeypatch.setattr(service, "call_firecrawl_scrape", no_firecrawl)

    result = await service.fetch("https://example.com")

    assert result["ok"] is False
    assert result["error_type"] == "network_error"


@pytest.mark.asyncio
async def test_tavily_custom_base_is_used_for_search_extract_and_map(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")
    monkeypatch.setenv("TAVILY_API_URL", "https://tavily.example.com/api/tavily")
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls.append((url, json))
            if url.endswith("/search"):
                payload = {"results": [{"title": "Search", "url": "https://example.com", "content": "body", "score": 0.9}]}
            elif url.endswith("/extract"):
                payload = {"results": [{"raw_content": "# Extracted"}], "failed_results": []}
            elif url.endswith("/map"):
                payload = {"base_url": json["url"], "results": ["https://example.com/docs"], "response_time": 0.1}
            else:
                payload = {}
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    search_result = await service.call_tavily_search("query", max_results=1)
    extract_result = await service.call_tavily_extract("https://example.com")
    map_result = await service.call_tavily_map("https://example.com", timeout=1)

    assert [call[0] for call in calls] == [
        "https://tavily.example.com/api/tavily/search",
        "https://tavily.example.com/api/tavily/extract",
        "https://tavily.example.com/api/tavily/map",
    ]
    assert search_result[0]["url"] == "https://example.com"
    assert extract_result == "# Extracted"
    assert map_result["ok"] is True
    assert map_result["results"] == ["https://example.com/docs"]


@pytest.mark.asyncio
async def test_firecrawl_custom_base_is_used_for_search_and_scrape(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test-secret")
    monkeypatch.setenv("FIRECRAWL_API_URL", "https://firecrawl.example.com/v2")
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls.append((url, json))
            if url.endswith("/search"):
                payload = {"data": {"web": [{"title": "Result", "url": "https://example.com", "description": "desc"}]}}
            elif url.endswith("/scrape"):
                payload = {"data": {"markdown": "# Scraped"}}
            else:
                payload = {}
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    search_result = await service.call_firecrawl_search("query", limit=1)
    scrape_result = await service.call_firecrawl_scrape("https://example.com")

    assert [call[0] for call in calls] == [
        "https://firecrawl.example.com/v2/search",
        "https://firecrawl.example.com/v2/scrape",
    ]
    assert search_result[0]["url"] == "https://example.com"
    assert scrape_result == "# Scraped"


@pytest.mark.asyncio
async def test_exa_search_passes_parameters(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)
        return json.dumps({"ok": True, "results": [], "total": 0})

    monkeypatch.setattr(service.ExaSearchProvider, "search", fake_search)

    result = await service.exa_search(
        "python docs",
        num_results=2,
        include_text=True,
        include_domains="docs.python.org,developer.mozilla.org",
    )

    assert result["ok"] is True
    assert captured["num_results"] == 2
    assert captured["include_text"] is True
    assert captured["include_domains"] == ["docs.python.org", "developer.mozilla.org"]


@pytest.mark.asyncio
async def test_exa_search_accepts_powershell_split_domain_filter(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")
    captured = {}

    async def fake_search(self, **kwargs):
        captured.update(kwargs)
        return json.dumps({"ok": True, "results": [], "total": 0})

    monkeypatch.setattr(service.ExaSearchProvider, "search", fake_search)

    result = await service.exa_search(
        "freertos release",
        include_domains="github.com freertos.org",
        exclude_domains=["youtube.com", "x.com linkedin.com"],
    )

    assert result["ok"] is True
    assert captured["include_domains"] == ["github.com", "freertos.org"]
    assert captured["exclude_domains"] == ["youtube.com", "x.com", "linkedin.com"]


@pytest.mark.asyncio
async def test_exa_search_normalizes_error_json(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")

    async def fake_search(self, **kwargs):
        return json.dumps({"ok": False, "error": "exa failed"})

    monkeypatch.setattr(service.ExaSearchProvider, "search", fake_search)

    result = await service.exa_search("python docs")

    assert result["ok"] is False
    assert result["error_type"] == "network_error"
    assert result["error"] == "exa failed"


@pytest.mark.asyncio
async def test_exa_search_preserves_provider_error_type(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-secret")

    async def fake_search(self, **kwargs):
        return json.dumps({"ok": False, "error_type": "parameter_error", "error": "HTTP 400: Bad Request"})

    monkeypatch.setattr(service.ExaSearchProvider, "search", fake_search)

    result = await service.exa_search("python docs")

    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert result["error"] == "HTTP 400: Bad Request"


@pytest.mark.asyncio
async def test_anysearch_service_wrappers_decode_provider_json(monkeypatch):
    calls = []

    class FakeAnySearchProvider:
        def __init__(self, api_url, api_key, timeout):
            calls.append(("init", api_url, api_key, timeout))

        async def list_domains(self, domain=""):
            calls.append(("domains", domain))
            return json.dumps({"ok": True, "provider": "anysearch", "tool": "list_domains", "domain": domain})

        async def vertical_search(self, query, domain="", sub_domain="", max_results=5):
            calls.append(("search", query, domain, sub_domain, max_results))
            return json.dumps({"ok": True, "provider": "anysearch", "tool": "search", "query": query})

        async def extract(self, url, max_length=20000):
            calls.append(("extract", url, max_length))
            return json.dumps({"ok": True, "provider": "anysearch", "tool": "extract", "url": url})

        async def batch_search(self, queries, max_results=3):
            calls.append(("batch", queries, max_results))
            return json.dumps({"ok": True, "provider": "anysearch", "tool": "batch_search", "results": []})

    monkeypatch.setenv("ANYSEARCH_API_URL", "https://anysearch.example.com/mcp")
    monkeypatch.setenv("ANYSEARCH_API_KEY", "as-test-secret")
    monkeypatch.setenv("ANYSEARCH_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr(service, "AnySearchProvider", FakeAnySearchProvider)

    domains = await service.anysearch_domains("security")
    search = await service.anysearch_search("CVE-2024-3094", domain="security.cve", sub_domain="xz", max_results=2)
    extract = await service.anysearch_extract("https://example.com", max_length=123)
    batch = await service.anysearch_batch(["a", "b"], max_results=1)

    assert domains["tool"] == "list_domains"
    assert search["query"] == "CVE-2024-3094"
    assert extract["url"] == "https://example.com"
    assert batch["tool"] == "batch_search"
    assert calls == [
        ("init", "https://anysearch.example.com/mcp", "as-test-secret", 7.0),
        ("domains", "security"),
        ("init", "https://anysearch.example.com/mcp", "as-test-secret", 7.0),
        ("search", "CVE-2024-3094", "security.cve", "xz", 2),
        ("init", "https://anysearch.example.com/mcp", "as-test-secret", 7.0),
        ("extract", "https://example.com", 123),
        ("init", "https://anysearch.example.com/mcp", "as-test-secret", 7.0),
        ("batch", ["a", "b"], 1),
    ]


@pytest.mark.asyncio
async def test_anysearch_service_parse_error(monkeypatch):
    class FakeAnySearchProvider:
        def __init__(self, api_url, api_key, timeout):
            pass

        async def list_domains(self, domain=""):
            return "not json"

    monkeypatch.setattr(service, "AnySearchProvider", FakeAnySearchProvider)

    result = await service.anysearch_domains()

    assert result["ok"] is False
    assert result["error_type"] == "parse_error"
    assert result["provider"] == "anysearch"


@pytest.mark.asyncio
async def test_doctor_redacts_secret_and_reports_config_error(monkeypatch):
    monkeypatch.setenv("UNSUPPORTED_SECRET_KEY", "placeholder-test-secret")

    result = await service.doctor()
    dumped = json.dumps(result, ensure_ascii=False)

    assert "placeholder-test-secret" not in dumped
    assert "❌" not in dumped
    assert "✅" not in dumped
    assert result["ok"] is False
    assert result["error_type"] == "config_error"
    assert result["primary_connection_test"]["status"] == "config_error"


@pytest.mark.asyncio
async def test_diagnose_openai_compatible_reports_missing_config(monkeypatch, tmp_path):
    _reset_config(monkeypatch, tmp_path)

    result = await service.diagnose_openai_compatible()

    assert result["ok"] is False
    assert result["error_type"] == "config_error"
    assert "OPENAI_COMPATIBLE_API_URL" in result["missing"]
    assert "OPENAI_COMPATIBLE_API_KEY" in result["missing"]
    assert result["summary"] == "OpenAI-compatible 配置不完整。"


@pytest.mark.asyncio
async def test_diagnose_openai_compatible_timeout_after_quick_chat(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def fake_quick(api_url, api_key, model):
        return {"status": "ok", "message": "chat ok", "response_time_ms": 12.0}

    async def fake_probe(api_url, api_key, model, *, stream, timeout_seconds):
        return {
            "name": f"真实 search 请求 (stream={'true' if stream else 'false'})",
            "status": "timeout",
            "message": "请求超时",
            "response_time_ms": timeout_seconds * 1000,
            "has_content": False,
            "stream": stream,
        }

    monkeypatch.setattr(service, "_test_primary_chat_completion", fake_quick)
    monkeypatch.setattr(service, "_probe_openai_compatible_search_shape", fake_probe)

    result = await service.diagnose_openai_compatible(timeout_seconds=3)
    dumped = json.dumps(result, ensure_ascii=False)

    assert result["ok"] is False
    assert result["error_type"] == "network_error"
    assert "真实 search 形态超时" in result["summary"]
    assert "上游模型或中转站" in result["recommendation"]
    assert "relay-test-secret" not in dumped
    assert service.config._mask_api_key("relay-test-secret") in dumped


@pytest.mark.asyncio
async def test_diagnose_openai_compatible_recommends_stream_when_only_stream_works(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def fake_quick(api_url, api_key, model):
        return {"status": "ok", "message": "chat ok", "response_time_ms": 12.0}

    async def fake_probe(api_url, api_key, model, *, stream, timeout_seconds):
        return {
            "name": "probe",
            "status": "ok" if stream else "timeout",
            "message": "ok" if stream else "timeout",
            "response_time_ms": 1.0,
            "has_content": stream,
            "stream": stream,
        }

    monkeypatch.setattr(service, "_test_primary_chat_completion", fake_quick)
    monkeypatch.setattr(service, "_probe_openai_compatible_search_shape", fake_probe)

    result = await service.diagnose_openai_compatible()

    assert result["ok"] is False
    assert "流式请求可用" in result["summary"]
    assert "OPENAI_COMPATIBLE_STREAM=true" in result["recommendation"]


@pytest.mark.asyncio
async def test_diagnose_openai_compatible_recommends_no_stream_when_stream_fails(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def fake_quick(api_url, api_key, model):
        return {"status": "ok", "message": "chat ok", "response_time_ms": 12.0}

    async def fake_probe(api_url, api_key, model, *, stream, timeout_seconds):
        return {
            "name": "probe",
            "status": "timeout" if stream else "ok",
            "message": "timeout" if stream else "ok",
            "response_time_ms": 1.0,
            "has_content": not stream,
            "stream": stream,
        }

    monkeypatch.setattr(service, "_test_primary_chat_completion", fake_quick)
    monkeypatch.setattr(service, "_probe_openai_compatible_search_shape", fake_probe)

    result = await service.diagnose_openai_compatible()

    assert result["ok"] is False
    assert "非流式请求可用" in result["summary"]
    assert "OPENAI_COMPATIBLE_STREAM=false" in result["recommendation"]


@pytest.mark.asyncio
async def test_diagnose_openai_compatible_reports_ok_when_both_search_shapes_work(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")

    async def fake_quick(api_url, api_key, model):
        return {"status": "ok", "message": "chat ok", "response_time_ms": 12.0}

    async def fake_probe(api_url, api_key, model, *, stream, timeout_seconds):
        return {"name": "probe", "status": "ok", "message": "ok", "response_time_ms": 1.0, "has_content": True, "stream": stream}

    monkeypatch.setattr(service, "_test_primary_chat_completion", fake_quick)
    monkeypatch.setattr(service, "_probe_openai_compatible_search_shape", fake_probe)

    result = await service.diagnose_openai_compatible()

    assert result["ok"] is True
    assert result["error_type"] == ""
    assert "主链路正常" in result["summary"]


@pytest.mark.asyncio
async def test_doctor_reports_invalid_validation_config(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-test-secret")
    monkeypatch.setenv("SMART_SEARCH_VALIDATION_LEVEL", "banana")

    result = await service.doctor()

    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert "Invalid SMART_SEARCH_VALIDATION_LEVEL" in result["error"]
    assert result["SMART_SEARCH_VALIDATION_LEVEL"] == "banana"


@pytest.mark.asyncio
async def test_primary_connection_checks_chat_even_when_models_endpoint_fails(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            calls.append(("get", url))
            return httpx.Response(
                401,
                json={"error": {"message": "models blocked"}},
                request=httpx.Request("GET", url),
            )

        async def post(self, url, headers, json):
            calls.append(("post", url, json["model"]))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    result = await service._test_primary_connection("https://api.example.com/v1", "sk-test-secret", "grok-4.3")

    assert result["status"] == "ok"
    assert result["chat_completion_test"]["status"] == "ok"
    assert result["models_endpoint_test"]["status"] == "warning"
    assert calls[0] == ("post", "https://api.example.com/v1/chat/completions", "grok-4.3")
    assert calls[1] == ("get", "https://api.example.com/v1/models")


@pytest.mark.asyncio
async def test_primary_connection_keeps_chat_ok_when_models_probe_errors(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            calls.append(("get", url))
            raise httpx.ConnectError("models unavailable", request=httpx.Request("GET", url))

        async def post(self, url, headers, json):
            calls.append(("post", url, json["model"]))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    result = await service._test_primary_connection("https://api.example.com/v1", "sk-test-secret", "grok-4.3")

    assert result["status"] == "ok"
    assert result["chat_completion_test"]["status"] == "ok"
    assert result["models_endpoint_test"]["status"] == "warning"
    assert "模型列表接口请求失败" in result["models_endpoint_test"]["message"]
    assert calls[0] == ("post", "https://api.example.com/v1/chat/completions", "grok-4.3")
    assert calls[1] == ("get", "https://api.example.com/v1/models")


@pytest.mark.asyncio
async def test_doctor_uses_responses_endpoint_for_explicit_xai_config(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls.append((url, json))
            return httpx.Response(
                200,
                json={"output": [{"content": [{"type": "output_text", "text": "ok"}]}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    result = await service.doctor()

    assert result["ok"] is True
    assert result["primary_api_mode"] == "xai-responses"
    assert result["primary_api_mode_source"] == "config_file"
    assert result["primary_connection_test"]["status"] == "ok"
    assert calls[0][0] == "https://api.x.ai/v1/responses"
    assert "tools" not in calls[0][1]


@pytest.mark.asyncio
async def test_doctor_uses_chat_completions_for_only_openai_compatible_config(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            calls.append(("get", url))
            return httpx.Response(
                200,
                json={"data": [{"id": "relay-model"}]},
                request=httpx.Request("GET", url),
            )

        async def post(self, url, headers, json):
            calls.append(("post", url, json))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    result = await service.doctor()

    assert result["primary_api_mode"] == "chat-completions"
    assert result["primary_connection_test"]["status"] == "ok"
    assert result["primary_connection_test"]["chat_completion_test"]["status"] == "ok"
    assert result["primary_connection_test"]["models_endpoint_test"]["status"] == "ok"
    assert list(result["main_search_connection_tests"]) == ["openai-compatible"]
    assert result["capability_status"]["main_search"]["configured"] == ["openai-compatible"]
    assert calls[0][0] == "post"
    assert calls[0][1] == "https://relay.example.com/v1/chat/completions"
    assert calls[1] == ("get", "https://relay.example.com/v1/models")


@pytest.mark.asyncio
async def test_doctor_tests_main_providers_independently(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_URL", "https://relay.example.com/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "relay-test-secret")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")

    async def fake_xai(api_url, api_key, model):
        raise httpx.TimeoutException("xai timeout")

    async def fake_openai(api_url, api_key, model):
        return {"status": "ok", "message": "relay ok"}

    monkeypatch.setattr(service, "_test_primary_responses", fake_xai)
    monkeypatch.setattr(service, "_test_primary_connection", fake_openai)
    async def fake_exa_connection():
        return {"status": "ok", "message": "exa ok"}

    async def fake_tavily_connection():
        return {"status": "ok", "message": "tavily ok"}

    async def fake_jina_connection():
        return {"status": "not_configured", "message": "missing"}

    async def fake_zhipu_mcp_connection():
        return {"status": "not_configured", "message": "missing"}

    monkeypatch.setattr(service, "_test_exa_connection", fake_exa_connection)
    monkeypatch.setattr(service, "_test_tavily_connection", fake_tavily_connection)
    monkeypatch.setattr(service, "_test_jina_connection", fake_jina_connection)
    monkeypatch.setattr(service, "_test_zhipu_mcp_connection", fake_zhipu_mcp_connection)

    result = await service.doctor()

    assert result["ok"] is True
    assert result["primary_connection_test"]["status"] == "timeout"
    assert result["main_search_connection_tests"]["xai-responses"]["status"] == "timeout"
    assert result["main_search_connection_tests"]["openai-compatible"]["status"] == "ok"


@pytest.mark.asyncio
async def test_jina_doctor_reports_readerlm_without_key_as_config_error(monkeypatch):
    monkeypatch.setenv("JINA_RESPOND_WITH", "readerlm-v2")
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    result = await service._test_jina_connection()

    assert result["status"] == "config_error"
    assert "JINA_API_KEY" in result["message"]


@pytest.mark.asyncio
async def test_call_jina_reader_decodes_provider_json(monkeypatch):
    class FakeJinaReaderProvider:
        def __init__(self, reader_api_url, api_key, respond_with, timeout):
            pass

        async def fetch(self, url):
            return json.dumps({"ok": True, "provider": "jina", "url": url, "content": "# Page"})

    monkeypatch.setattr(service, "JinaReaderProvider", FakeJinaReaderProvider)

    result = await service.call_jina_reader("https://example.com")

    assert result == {"ok": True, "provider": "jina", "url": "https://example.com", "content": "# Page"}


@pytest.mark.asyncio
async def test_zhipu_mcp_service_wrappers_decode_provider_json(monkeypatch):
    calls = []

    class FakeZhipuMCPProvider:
        def __init__(self, api_url, api_key, timeout, provider_id="zhipu-mcp"):
            calls.append(("init", provider_id, api_url, api_key, timeout))
            self.provider_id = provider_id

        async def web_search(self, query, count=5):
            calls.append(("web_search", query, count))
            return json.dumps({"ok": True, "provider": self.provider_id, "tool": "web_search_prime", "query": query})

        async def web_reader(self, url):
            calls.append(("web_reader", url))
            return json.dumps({"ok": True, "provider": self.provider_id, "tool": "webReader", "url": url, "content": "# Page"})

        async def search_doc(self, repo, query, max_results=5):
            calls.append(("search_doc", repo, query, max_results))
            return json.dumps({"ok": True, "provider": self.provider_id, "tool": "search_doc", "repo": repo})

        async def get_repo_structure(self, repo, ref=""):
            calls.append(("get_repo_structure", repo, ref))
            return json.dumps({"ok": True, "provider": self.provider_id, "tool": "get_repo_structure", "repo": repo})

        async def read_file(self, repo, path, ref=""):
            calls.append(("read_file", repo, path, ref))
            return json.dumps({"ok": True, "provider": self.provider_id, "tool": "read_file", "path": path})

    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zmcp-test-secret")
    monkeypatch.setenv("ZHIPU_MCP_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr(service, "ZhipuMCPProvider", FakeZhipuMCPProvider)

    search = await service.zhipu_mcp_search("query", count=2)
    reader = await service.zhipu_mcp_reader("https://example.com")
    doc = await service.zhipu_mcp_search_doc("owner/repo", "install", max_results=3)
    tree = await service.zhipu_mcp_repo_structure("owner/repo", ref="main")
    file_data = await service.zhipu_mcp_read_file("owner/repo", "README.md", ref="main")

    assert search["tool"] == "web_search_prime"
    assert reader["content"] == "# Page"
    assert doc["tool"] == "search_doc"
    assert tree["tool"] == "get_repo_structure"
    assert file_data["path"] == "README.md"
    assert calls[0] == (
        "init",
        "zhipu-mcp",
        "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
        "zmcp-test-secret",
        7.0,
    )


@pytest.mark.asyncio
async def test_tavily_doctor_connection_uses_configured_timeout(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-secret")
    monkeypatch.setenv("TAVILY_API_URL", "https://tavily.example.com/api/tavily")
    monkeypatch.setenv("TAVILY_TIMEOUT_SECONDS", "45")
    seen = {}

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects=False, verify=True):
            seen["timeout"] = timeout
            seen["follow_redirects"] = follow_redirects
            seen["verify"] = verify

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            seen["url"] = url
            seen["json"] = json
            return httpx.Response(200, json={"results": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)

    result = await service._test_tavily_connection()

    assert result["status"] == "ok"
    assert seen["url"] == "https://tavily.example.com/api/tavily/search"
    assert seen["timeout"].connect == 6.0
    assert seen["timeout"].read == 45.0
    assert seen["timeout"].write == 10.0
    assert seen["follow_redirects"] is True
    assert seen["verify"] is True
