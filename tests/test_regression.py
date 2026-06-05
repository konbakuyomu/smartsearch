from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SKILL_DIR = ROOT / "skills" / "smart-search-cli"
PACKAGED_SKILL_DIR = ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"


def test_regression_does_not_create_repo_log_file():
    log_dir = ROOT / "logs"
    if not log_dir.exists():
        return
    assert not list(log_dir.glob("smart_search_*.log"))


def test_smart_search_skill_contract_enforces_cli_first():
    skill_dir = Path.home() / ".codex" / "skills" / "smart-search-cli"
    if not skill_dir.exists():
        return
    skill_files = [
        p
        for p in skill_dir.rglob("*")
        if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}
    ]
    if not skill_files:
        return

    text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in skill_files
    )

    forbidden_text = [
        "mcp__smart-search__",
        "get_sources",
        "get_config_info",
        "toggle_builtin_tools",
        "native web search fallback",
        "silently fallback",
    ]
    for phrase in forbidden_text:
        assert phrase not in text

    assert "native `web_search` is disabled" in text or "native web search is disabled" in text
    assert "do not silently fall back" in text


def _read_skill_tree(path: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(path.rglob("*"))
        if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}
    )


def test_deep_research_skill_contract_public_and_packaged_assets_match():
    public_text = _read_skill_tree(PUBLIC_SKILL_DIR)
    packaged_text = _read_skill_tree(PACKAGED_SKILL_DIR)
    required_markers = [
        "Deep Research Mode",
        "深度搜索",
        "深度调研",
        "deep search",
        "deep research",
        "research_plan",
        "capability-based orchestration",
        "intent_signals",
        "capability_plan",
        "gap_check",
        "fetch_before_claim",
        "smart-search skills status",
        "smart-search skills update",
        "Do not treat Exa as the universal second hop",
        "Prefer Context7 before Exa",
        "smart-search deep",
        "decomposition",
        "usage_boundary",
        "search`, `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`, and `map`",
        "doctor` is preflight",
        "fixed topic recipe",
        "深度搜索一下最近的比特币行情",
        "C:\\tmp\\smart-search-evidence",
        "mock-full plus live-limited",
        "public planner entrypoint",
        "public live executor entrypoint",
        "not an executor",
        "does not change default `smart-search search`",
        "does not depend on an MCP session",
        "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS",
        "provider advantage routing",
    ]
    for marker in required_markers:
        assert marker in public_text
        assert marker in packaged_text


def test_deep_research_cli_contract_documents_plan_and_smoke_matrix():
    public_contract = (PUBLIC_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    packaged_contract = (PACKAGED_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    required_markers = [
        "Deep Research Skill Contract",
        "`smart-search deep` is the public offline planner command",
        "`smart-search research` is the public live executor command",
        "must not change default `smart-search search` behavior",
        "`mode`: always `deep_research`",
        "`query_mode`: always `deep`",
        "`question`: the user's research question",
        "`trigger_source`: usually `explicit_cli`",
        "`difficulty`: `standard` or `high`",
        "`intent_signals`: dimensional signals",
        "`decomposition`: subquestions for complex research",
        "`capability_plan`: the selected capability needs",
        "`evidence_policy`: default `fetch_before_claim`",
        "`preflight`: `doctor` guidance",
        "`steps`: ordered CLI command steps",
        "`gap_check`: how the agent verifies",
        "`final_answer_policy`: how to cite fetched evidence",
        "`usage_boundary`: user-facing distinction",
        "Allowed `tool` values are `search`, `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`, and `map`",
        "`doctor` is a `preflight` action, not a `steps[]` item",
        "must not require fixed topic recipe ids",
        "fixed topic recipe ids are not required schema",
        "Mock-full coverage should cover trigger phrases",
        "research provider advantage routing",
        "`research --fallback auto` permits same-capability fallback",
        "Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch`",
        "`smart-search skills status --targets codex,claude,cursor,hermes --format json`",
        "`smart-search skills update --targets codex,claude,cursor,hermes --format json`",
        "Status values are `missing`, `up_to_date`, `stale`, `extra_files`, and",
        "must not change provider keys, run setup",
        "Prefer `skills status` and",
        "rerun the affected smoke until it passes or is proven to be an external provider blocker",
        "Budget limits must not break evidence policy",
        "Even `--budget quick` plans must retain at least one `fetch` step",
        "`steps[].command` and `steps[].output_path` are one contract",
        "Prefer PowerShell-safe quoted commands",
    ]
    for marker in required_markers:
        assert marker in public_contract
        assert marker in packaged_contract


def test_search_timeout_retry_policy_is_distributable():
    public_text = _read_skill_tree(PUBLIC_SKILL_DIR)
    packaged_text = _read_skill_tree(PACKAGED_SKILL_DIR)
    public_contract = (PUBLIC_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    packaged_contract = (PACKAGED_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")

    skill_markers = [
        "Timeout Retry Policy",
        "error_type: \"network_error\"",
        "Retry up to 3 total attempts with `--timeout 180`",
        "`--extra-sources 1` during retry attempts",
        "Always use the CLI's `--timeout` option",
        "Do not wrap `smart-search` in a shell-level `timeout` command",
        "Do not rely on `SMART_SEARCH_RETRY_*` settings",
        "fall back to source-first evidence",
        "Run `exa-search` with the original query",
        "`fetch` the top 1-2 relevant URLs",
        "source_mode: \"fallback\"",
    ]
    contract_markers = [
        "Agent timeout handling contract",
        "`smart-search search ... --timeout 180 --extra-sources 1 --format json --output PATH`",
        "not a shell-level `timeout` wrapper",
        "`SMART_SEARCH_RETRY_*` settings are not the contract",
        "switch to source-first fallback",
        "`exa-search --include-domains`",
        "`source_mode: \"fallback\"`",
    ]

    for marker in skill_markers:
        assert marker in public_text
        assert marker in packaged_text
    for marker in contract_markers:
        assert marker in public_contract
        assert marker in packaged_contract


def test_deep_research_readme_documents_capability_orchestration():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    english_markers = [
        "Deep Research is not a fixed topic recipe system",
        "smart-search research",
        "`route_policy_version`",
        "provider-advantage",
        "`intent_signals`",
        "`decomposition`",
        "`capability_plan`",
        "`gap_check`",
        "`usage_boundary`",
        "smart-search deep",
        "`exa-similar`",
        "`context7-library`",
        "smart-search skills status",
        "smart-search skills update",
        "`doctor` is preflight, not a research step",
        "Unsupported key claims must be fetched or downgraded to unverified candidates",
    ]
    chinese_markers = [
        "Deep Research 不是固定题材配方",
        "smart-search research",
        "`route_policy_version`",
        "provider 优势",
        "`intent_signals`",
        "`decomposition`",
        "`capability_plan`",
        "`gap_check`",
        "`usage_boundary`",
        "smart-search deep",
        "`exa-similar`",
        "`context7-library`",
        "smart-search skills status",
        "smart-search skills update",
        "`doctor` 只是配置预检",
        "没有 fetch 的来源标为未验证候选",
    ]
    for marker in english_markers:
        assert marker in readme
    for marker in chinese_markers:
        assert marker in readme_zh


def test_readme_language_split_and_provider_links_are_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    package_json = (ROOT / "package.json").read_text(encoding="utf-8")

    assert "[简体中文](README.zh-CN.md) | English" in readme
    assert "简体中文 | [English](README.md)" in readme_zh
    assert "## 中文" not in readme
    assert "## English" not in readme
    assert "README.zh-CN.md" in package_json

    provider_markers = [
        "https://docs.x.ai/docs",
        "https://console.x.ai/team/default/api-keys",
        "https://platform.openai.com/docs",
        "https://platform.openai.com/api-keys",
        "https://docs.exa.ai/",
        "https://dashboard.exa.ai/api-keys",
        "https://context7.com/docs",
        "https://docs.bigmodel.cn/cn/guide/tools/web-search",
        "https://open.bigmodel.cn/usercenter/apikeys",
        "https://docs.tavily.com/",
        "https://app.tavily.com/home",
        "https://docs.firecrawl.dev/",
        "https://www.firecrawl.dev/app/api-keys",
    ]
    for marker in provider_markers:
        assert marker in readme
        assert marker in readme_zh


def test_deep_research_shared_skill_files_are_synchronized():
    shared_files = [
        "SKILL.md",
        "references/cli-contract.md",
    ]
    for relative in shared_files:
        assert (PUBLIC_SKILL_DIR / relative).read_text(encoding="utf-8") == (
            PACKAGED_SKILL_DIR / relative
        ).read_text(encoding="utf-8")


def test_zhipu_setup_contract_public_and_packaged_assets_match():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    public_text = _read_skill_tree(PUBLIC_SKILL_DIR)
    packaged_text = _read_skill_tree(PACKAGED_SKILL_DIR)
    public_contract = (PUBLIC_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    packaged_contract = (PACKAGED_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    required_markers = [
        "--zhipu-api-url",
        "--zhipu-search-engine",
        "ZHIPU_API_URL",
        "ZHIPU_SEARCH_ENGINE",
        "search_std",
        "search_pro",
        "search_pro_sogou",
        "search_pro_quark",
        "Web Search API",
        "TAVILY_API_URL",
        "does not proxy Zhipu",
        "not Zhipu Chat Completions",
        "not the MCP Server",
    ]
    for marker in required_markers:
        assert marker in readme
        assert marker in public_text
        assert marker in packaged_text
    zh_required_markers = [
        "--zhipu-api-url",
        "--zhipu-search-engine",
        "ZHIPU_API_URL",
        "ZHIPU_SEARCH_ENGINE",
        "search_std",
        "search_pro",
        "search_pro_sogou",
        "search_pro_quark",
        "Web Search API",
        "TAVILY_API_URL",
        "不会代理智谱",
        "不是 Chat Completions",
        "不是 MCP Server",
    ]
    for marker in zh_required_markers:
        assert marker in readme_zh
    for marker in ["--zhipu-api-url", "--zhipu-search-engine"]:
        assert marker in public_contract
        assert marker in packaged_contract


def test_jina_and_zhipu_mcp_contract_public_and_packaged_assets_match():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    public_text = _read_skill_tree(PUBLIC_SKILL_DIR)
    packaged_text = _read_skill_tree(PACKAGED_SKILL_DIR)
    public_contract = (PUBLIC_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    packaged_contract = (PACKAGED_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")

    required_markers = [
        "JINA_API_KEY",
        "JINA_READER_API_URL",
        "JINA_RESPOND_WITH",
        "Jina Reader is `web_fetch` only",
        "Anonymous Jina Reader calls",
        "ZHIPU_MCP_API_KEY",
        "ZHIPU_MCP_SEARCH_API_URL",
        "ZHIPU_MCP_READER_API_URL",
        "ZHIPU_MCP_ZREAD_API_URL",
        "web_search_prime",
        "webReader",
        "search_doc",
        "get_repo_structure",
        "read_file",
        "Remote MCP",
        "Do not route it through the existing `/paas/v4/web_search`",
        "Coding Plan entitlement",
        "does not affect the standard minimum profile",
    ]
    for marker in required_markers:
        assert marker in public_text
        assert marker in packaged_text
        assert marker in public_contract
        assert marker in packaged_contract

    readme_markers = [
        "JINA_API_KEY",
        "Zhipu Coding Plan Remote MCP",
        "zhipu-mcp-search",
        "zhipu-mcp-reader",
        "not mixed into the existing `/paas/v4/web_search`",
        "Jina Reader is not a general search provider",
        "A normal `ZHIPU_API_KEY` for Web Search API does not prove `zhipu-mcp-search` or zread access",
    ]
    for marker in readme_markers:
        assert marker in readme

    zh_markers = [
        "JINA_API_KEY",
        "智谱 Coding Plan Remote MCP",
        "zhipu-mcp-search",
        "zhipu-mcp-reader",
        "不会混进现有 `/paas/v4/web_search`",
        "Jina Reader 不是通用搜索 provider",
        "普通 `ZHIPU_API_KEY` 能用 Web Search API，不代表能用 `zhipu-mcp-search` 或 zread",
    ]
    for marker in zh_markers:
        assert marker in readme_zh


def test_streaming_and_anysearch_contract_public_and_packaged_assets_match():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    public_text = _read_skill_tree(PUBLIC_SKILL_DIR)
    packaged_text = _read_skill_tree(PACKAGED_SKILL_DIR)
    public_contract = (PUBLIC_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")
    packaged_contract = (PACKAGED_SKILL_DIR / "references" / "cli-contract.md").read_text(encoding="utf-8")

    required_markers = [
        "OPENAI_COMPATIBLE_STREAM",
        "--stream",
        "--no-stream",
        "ANYSEARCH_API_URL",
        "ANYSEARCH_API_KEY",
        "ANYSEARCH_TIMEOUT_SECONDS",
        "anysearch-domains",
        "anysearch-search",
        "anysearch-extract",
        "anysearch-batch",
        "vertical_search",
        "not part of the `web_search` fallback",
        "not required by the `standard` minimum profile",
    ]
    for marker in required_markers:
        assert marker in readme
        assert marker in public_text
        assert marker in packaged_text
        assert marker in public_contract
        assert marker in packaged_contract

    zh_required_markers = [
        "OPENAI_COMPATIBLE_STREAM",
        "ANYSEARCH_API_URL",
        "ANYSEARCH_API_KEY",
        "ANYSEARCH_TIMEOUT_SECONDS",
        "anysearch-domains",
        "anysearch-search",
        "vertical_search",
        "不进入 `web_search` 兜底链",
        "不是 `standard` 最低配置要求",
    ]
    for marker in zh_required_markers:
        assert marker in readme_zh
