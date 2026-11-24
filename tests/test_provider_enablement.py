"""Provider switches affect real request planning without deleting credentials."""
import httpx
import pytest

from smart_search import jev_search, service, ui_api
from smart_search.config import config


PROVIDERS = [
    ("xai-responses", "XAI_ENABLED", "XAI_API_KEY", "main_search"),
    ("openai-compatible", "OPENAI_COMPATIBLE_ENABLED", "OPENAI_COMPATIBLE_API_KEY", "main_search"),
    ("context7", "CONTEXT7_ENABLED", "CONTEXT7_API_KEY", "docs_search"),
    ("exa", "EXA_ENABLED", "EXA_API_KEY", "docs_search"),
    ("zhipu", "ZHIPU_ENABLED", "ZHIPU_API_KEY", "web_search"),
    ("zhipu-mcp", "ZHIPU_MCP_ENABLED", "ZHIPU_MCP_API_KEY", "web_search"),
    ("zhipu-mcp-reader", "ZHIPU_MCP_READER_ENABLED", "ZHIPU_MCP_API_KEY", "web_fetch"),
    ("tavily", "TAVILY_ENABLED", "TAVILY_API_KEY", "web_fetch"),
    ("firecrawl", "FIRECRAWL_ENABLED", "FIRECRAWL_API_KEY", "web_fetch"),
    ("tinyfish", "TINYFISH_ENABLED", "TINYFISH_API_KEY", "web_fetch"),
    ("deepseek", "DEEPSEEK_ENABLED", "DEEPSEEK_API_KEY", "web_fetch"),
    ("specstream", "SPECSTREAM_ENABLED", "SPECSTREAM_API_KEY", "web_fetch"),
    ("jina", "JINA_ENABLED", "JINA_API_KEY", "web_fetch"),
    ("anysearch", "ANYSEARCH_ENABLED", "ANYSEARCH_API_KEY", "vertical_search"),
    ("sciverse", "SCIVERSE_ENABLED", "SCIVERSE_API_TOKEN", "vertical_search"),
]


@pytest.fixture
def configured_providers():
    values = {credential: "synthetic-preserved-key" for _, _, credential, _ in PROVIDERS}
    values["OPENAI_COMPATIBLE_API_URL"] = "https://example.invalid/v1"
    assert config.update_config_values(values)["ok"]
    return values


@pytest.mark.parametrize("provider,enabled_key,credential,capability", PROVIDERS)
def test_saved_switch_removes_channel_and_reenable_restores_it(configured_providers, provider, enabled_key, credential, capability):
    state = ui_api.state()
    assert provider in state["capability_status"][capability]["configured"]
    preview = ui_api.preview({"values": {enabled_key: "false"}})
    assert provider not in preview["capability_status"][capability]["configured"]
    assert provider in service.get_capability_status()[capability]["configured"]
    result = ui_api.apply_config({"set": {enabled_key: "false"}, "revision": state["revision"]})
    assert result["ok"]
    assert result["status"]["provider_profiles"][provider]["enabled"] is False
    assert provider not in result["status"]["capability_status"][capability]["configured"]
    assert provider not in {item["provider"] for item in jev_search.available_channels(service, "search docs", [])}
    assert config.get_saved_config(masked=False)[credential] == configured_providers[credential]
    assert ui_api.apply_config({"set": {enabled_key: "true"}, "revision": result["status"]["revision"]})["ok"]
    assert provider in service.get_capability_status()[capability]["configured"]


@pytest.mark.asyncio
async def test_disabled_primary_is_removed_before_model_resolution(configured_providers):
    config.set_config_value("XAI_ENABLED", "false")
    config.set_config_value("XAI_TOOLS", "web_search")
    configs = service._main_search_provider_configs()
    assert [item["provider"] for item in configs] == ["openai-compatible"]
    config.set_config_value("OPENAI_COMPATIBLE_ENABLED", "false")
    assert not service._main_search_provider_configs()
    result = await service.search("test query", providers="xai,openai")
    assert result["ok"] is False and result["error_type"] == "config_error"


@pytest.mark.asyncio
async def test_docs_fallback_skips_disabled_provider(configured_providers, monkeypatch):
    config.set_config_value("CONTEXT7_ENABLED", "false")
    calls = []

    async def context7(*args, **kwargs):
        calls.append("context7")
        return {"ok": True, "results": [{"id": "/pytest-dev/pytest"}]}

    async def exa(*args, **kwargs):
        calls.append("exa")
        return {"ok": True, "results": [{"url": "https://docs.pytest.org/", "title": "pytest"}]}

    monkeypatch.setattr(service, "context7_library", context7)
    monkeypatch.setattr(service, "exa_search", exa)
    result = await service.search("pytest API docs", providers="context7,exa")
    sources, attempts = result["sources"], result["provider_attempts"]
    assert calls == ["exa"]
    assert sources[0]["url"] == "https://docs.pytest.org/"
    assert [item["provider"] for item in attempts] == ["exa"]


def test_mcp_reader_switch_is_independent_of_search_with_shared_key(configured_providers):
    config.set_config_value("ZHIPU_MCP_ENABLED", "false")
    capabilities = service.get_capability_status()
    assert "zhipu-mcp" not in capabilities["web_search"]["configured"]
    assert "zhipu-mcp-reader" in capabilities["web_fetch"]["configured"]
    config.update_config_values({"ZHIPU_MCP_ENABLED": "true", "ZHIPU_MCP_READER_ENABLED": "false"})
    capabilities = service.get_capability_status()
    assert "zhipu-mcp" in capabilities["web_search"]["configured"]
    assert "zhipu-mcp-reader" not in capabilities["web_fetch"]["configured"]


DIRECT_REQUESTS = [
    ("exa_search", ("query",)), ("exa_find_similar", ("https://example.com",)),
    ("context7_library", ("pytest",)), ("context7_docs", ("/pytest-dev/pytest", "fixtures")),
    ("zhipu_search", ("query",)), ("zhipu_mcp_search", ("query",)),
    ("zhipu_mcp_reader", ("https://example.com",)), ("zhipu_mcp_search_doc", ("owner/repo", "query")),
    ("zhipu_mcp_repo_structure", ("owner/repo",)), ("zhipu_mcp_read_file", ("owner/repo", "README.md")),
    ("anysearch_domains", ()), ("anysearch_search", ("query",)),
    ("anysearch_extract", ("https://example.com",)), ("anysearch_batch", (["query"],)),
    ("sciverse_catalog", ()), ("sciverse_search", ("query",)),
    ("sciverse_semantic", ("query",)), ("sciverse_read", ("doc",)), ("sciverse_relations", ("doc",)),
    ("jina_fetch", ("https://example.com",)), ("call_tinyfish_fetch", ("https://example.com",)),
    ("call_specstream_fetch", ("https://example.com",)),
    ("map_site", ("https://example.com",)), ("diagnose_openai_compatible", ()),
]


@pytest.fixture
def all_disabled(configured_providers, monkeypatch):
    assert config.update_config_values({key: "false" for _, key, _, _ in PROVIDERS})["ok"]
    calls = []

    async def network_forbidden(*args, **kwargs):
        calls.append("network")
        raise AssertionError("Disabled providers must not send HTTP requests")

    monkeypatch.setattr(httpx.AsyncClient, "send", network_forbidden)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("name,args", DIRECT_REQUESTS)
async def test_direct_commands_do_not_bypass_disabled_state(all_disabled, name, args):
    result = await getattr(service, name)(*args)
    assert result.get("disabled") is True
    assert result["error_type"] == "config_error"
    assert all_disabled == []


@pytest.mark.asyncio
async def test_doctor_and_manual_probes_make_no_requests_when_disabled(all_disabled):
    for provider in [item[0] for item in PROVIDERS]:
        result = await service.test_provider_connection(provider)
        assert result["status"] == "disabled", provider
        assert result["probe"] == "none" and result["recorded_as"] == ""
    await service.doctor()
    assert all_disabled == []


def test_switch_respects_environment_and_invalid_values(configured_providers, monkeypatch):
    monkeypatch.setenv("EXA_ENABLED", "false")
    assert "exa" not in service.get_capability_status()["docs_search"]["configured"]
    result = ui_api.apply_config({"set": {"EXA_ENABLED": "true"}})
    assert not result["ok"] and result["shadowed"] == ["EXA_ENABLED"]
    before = config.config_file.read_bytes()
    result = config.update_config_values({"CONTEXT7_ENABLED": "sometimes"})
    assert not result["ok"] and config.config_file.read_bytes() == before
