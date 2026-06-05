import json
import asyncio
from pathlib import Path
from smart_search import cli
from smart_search import skill_installer


class GbkStdout:
    encoding = "gbk"
    errors = "strict"

    def __init__(self):
        self.parts = []

    def write(self, text):
        text.encode(self.encoding, errors=self.errors)
        self.parts.append(text)
        return len(text)

    def getvalue(self):
        return "".join(self.parts)


def test_help_contains_commands(capsys):
    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "search" in out
    assert "doctor" in out
    assert "regression" in out


def test_version_flags_exit_successfully(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_version", lambda: "9.9.9-test")

    for flag in ["--version", "--v", "-v"]:
        try:
            cli.main([flag])
        except SystemExit as exc:
            assert exc.code == 0

        assert capsys.readouterr().out.strip() == "smart-search 9.9.9-test"


def test_each_subcommand_help_exits_successfully(capsys):
    commands = [
        ["search", "--help"],
        ["fetch", "--help"],
        ["map", "--help"],
        ["exa-search", "--help"],
        ["exa-similar", "--help"],
        ["zhipu-search", "--help"],
        ["zhipu-mcp-search", "--help"],
        ["zhipu-mcp-reader", "--help"],
        ["zhipu-mcp-search-doc", "--help"],
        ["zhipu-mcp-repo-structure", "--help"],
        ["zhipu-mcp-read-file", "--help"],
        ["anysearch-domains", "--help"],
        ["anysearch-search", "--help"],
        ["anysearch-extract", "--help"],
        ["anysearch-batch", "--help"],
        ["context7-library", "--help"],
        ["context7-docs", "--help"],
        ["deep", "--help"],
        ["smoke", "--help"],
        ["doctor", "--help"],
        ["diagnose", "--help"],
        ["diagnose", "openai-compatible", "--help"],
        ["skills", "--help"],
        ["skills", "status", "--help"],
        ["skills", "update", "--help"],
        ["setup", "--help"],
        ["config", "--help"],
        ["config", "path", "--help"],
        ["config", "list", "--help"],
        ["config", "set", "--help"],
        ["config", "unset", "--help"],
        ["model", "--help"],
        ["model", "set", "--help"],
        ["model", "current", "--help"],
        ["regression", "--help"],
    ]

    for command in commands:
        try:
            cli.main(command)
        except SystemExit as exc:
            assert exc.code == 0

    out = capsys.readouterr().out
    assert "usage: smart-search search" in out
    assert "usage: smart-search regression" in out


def test_command_aliases_parse_to_canonical_commands():
    parser = cli.build_parser()

    command_cases = [
        (["s", "query"], "search"),
        (["f", "https://example.com"], "fetch"),
        (["m", "https://example.com"], "map"),
        (["exa", "query"], "exa-search"),
        (["x", "query"], "exa-search"),
        (["xs", "https://example.com"], "exa-similar"),
        (["z", "query"], "zhipu-search"),
        (["zp", "query"], "zhipu-search"),
        (["zmcp-search", "query"], "zhipu-mcp-search"),
        (["zmcp-reader", "https://example.com"], "zhipu-mcp-reader"),
        (["zmcp-doc", "owner/repo", "install"], "zhipu-mcp-search-doc"),
        (["zmcp-tree", "owner/repo"], "zhipu-mcp-repo-structure"),
        (["zmcp-file", "owner/repo", "README.md"], "zhipu-mcp-read-file"),
        (["as-domains"], "anysearch-domains"),
        (["as-search", "query"], "anysearch-search"),
        (["as", "query"], "anysearch-search"),
        (["as-extract", "https://example.com"], "anysearch-extract"),
        (["as-batch", "a", "b"], "anysearch-batch"),
        (["c7", "react"], "context7-library"),
        (["ctx7", "react"], "context7-library"),
        (["c7d", "/facebook/react", "hooks"], "context7-docs"),
        (["c7docs", "/facebook/react", "hooks"], "context7-docs"),
        (["ctx7-docs", "/facebook/react", "hooks"], "context7-docs"),
        (["dr", "query"], "deep"),
        (["sm"], "smoke"),
        (["d"], "doctor"),
        (["diag", "openai-compatible"], "diagnose"),
        (["skill", "status"], "skills"),
        (["init", "--non-interactive"], "setup"),
        (["cfg", "ls"], "config"),
        (["mdl", "cur"], "model"),
        (["reg"], "regression"),
    ]

    for argv, command in command_cases:
        assert parser.parse_args(argv).command == command

    config_cases = [
        (["cfg", "p"], "path"),
        (["cfg", "ls"], "list"),
        (["cfg", "l"], "list"),
        (["cfg", "s", "XAI_MODEL", "grok"], "set"),
        (["cfg", "rm", "XAI_MODEL"], "unset"),
        (["cfg", "u", "XAI_MODEL"], "unset"),
    ]
    for argv, config_command in config_cases:
        assert parser.parse_args(argv).config_command == config_command

    model_cases = [
        (["mdl", "s", "grok"], "set"),
        (["mdl", "cur"], "current"),
        (["mdl", "c"], "current"),
    ]
    for argv, model_command in model_cases:
        assert parser.parse_args(argv).model_command == model_command

    skills_cases = [
        (["skills", "st"], "status"),
        (["skills", "up"], "update"),
    ]
    for argv, skills_command in skills_cases:
        assert parser.parse_args(argv).skills_command == skills_command


def test_search_help_exposes_timeout(capsys):
    try:
        cli.main(["search", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "--timeout SECONDS" in out
    assert "--stream" in out
    assert "--no-stream" in out


def test_diagnose_openai_compatible_defaults_to_markdown(monkeypatch, capsys):
    async def fake_diagnose(timeout_seconds=30.0):
        return {
            "ok": False,
            "provider": "openai-compatible",
            "summary": "小请求能通，但真实 search 形态超时。",
            "recommendation": "建议换模型/中转，或把本诊断报告贴给维护者。",
            "api_url": "https://relay.example.com/v1",
            "api_key": "sk-T********cret",
            "model": "relay-model",
            "configured_stream": True,
            "timeout_seconds": timeout_seconds,
            "config_file": "C:/tmp/config.json",
            "config_dir_source": "environment",
            "checks": [
                {"name": "轻量 chat 请求", "status": "ok", "response_time_ms": 10.0, "has_content": True, "message": "chat ok"},
                {
                    "name": "真实 search 请求 (stream=false)",
                    "status": "timeout",
                    "response_time_ms": 30000.0,
                    "has_content": False,
                    "message": "请求超时",
                },
            ],
            "next_command": "smart-search diagnose openai-compatible --format markdown",
            "error_type": "network_error",
            "error": "小请求能通，但真实 search 形态超时。",
        }

    monkeypatch.setattr(cli.service, "diagnose_openai_compatible", fake_diagnose)

    code = cli.main(["diagnose", "openai-compatible"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_NETWORK_ERROR
    assert out.startswith("# Smart Search Diagnose")
    assert "小请求能通" in out
    assert "真实 search 请求" in out
    assert "smart-search diagnose openai-compatible --format markdown" in out


def test_diagnose_openai_compatible_json(monkeypatch, capsys):
    async def fake_diagnose(timeout_seconds=30.0):
        return {"ok": True, "provider": "openai-compatible", "summary": "ok", "timeout_seconds": timeout_seconds}

    monkeypatch.setattr(cli.service, "diagnose_openai_compatible", fake_diagnose)

    code = cli.main(["diagnose", "openai-compatible", "--timeout", "5", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert data["provider"] == "openai-compatible"
    assert data["timeout_seconds"] == 5


def test_search_outputs_json_and_file(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "query": query,
            "content": "Answer",
            "sources": [{"url": "https://example.com", "title": "Example"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", fake_search)
    written = {}

    def fake_write_output(path, content):
        written["path"] = path
        written["content"] = content

    monkeypatch.setattr(cli.service, "write_output", fake_write_output)
    output = "C:/tmp/smart-search-cli-test-result.json"

    code = cli.main(["search", "query", "--output", output])

    assert code == cli.EXIT_OK
    stdout_data = json.loads(capsys.readouterr().out)
    file_data = json.loads(written["content"])
    assert written["path"] == output
    assert stdout_data["sources_count"] == 1
    assert file_data["content"] == "Answer"


def test_search_stream_flags_override_only_when_present(monkeypatch, capsys):
    captured = []

    async def fake_search(query, **kwargs):
        captured.append(kwargs)
        return {"ok": True, "content": "Answer", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    assert cli.main(["search", "query"]) == cli.EXIT_OK
    json.loads(capsys.readouterr().out)
    assert cli.main(["search", "query", "--stream"]) == cli.EXIT_OK
    json.loads(capsys.readouterr().out)
    assert cli.main(["search", "query", "--no-stream"]) == cli.EXIT_OK
    json.loads(capsys.readouterr().out)

    assert "stream" not in captured[0]
    assert captured[1]["stream"] is True
    assert captured[2]["stream"] is False


def test_search_json_outputs_readable_chinese(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {"ok": True, "content": "中文NBA战报", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "nba战报", "--format", "json"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "中文NBA战报" in out
    assert "\\u4e2d\\u6587" not in out
    assert json.loads(out)["content"] == "中文NBA战报"


def test_search_content_format_outputs_content_only(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {"ok": True, "content": "中文NBA战报", "sources": [{"url": "https://example.com"}], "sources_count": 1}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "nba战报", "--format", "content"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "中文NBA战报\n"


def test_fetch_content_format_matches_markdown_body(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": True, "url": url, "content": "# 中文页面"}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    content_code = cli.main(["fetch", "https://example.com", "--format", "content"])
    content_out = capsys.readouterr().out
    markdown_code = cli.main(["fetch", "https://example.com", "--format", "markdown"])
    markdown_out = capsys.readouterr().out

    assert content_code == cli.EXIT_OK
    assert markdown_code == cli.EXIT_OK
    assert content_out == "# 中文页面\n"
    assert markdown_out == content_out


def test_context7_docs_content_format_outputs_content(monkeypatch, capsys):
    async def fake_context7_docs(library_id, query):
        return {"ok": True, "provider": "context7-docs", "library_id": library_id, "query": query, "content": "中文文档内容"}

    monkeypatch.setattr(cli.service, "context7_docs", fake_context7_docs)

    code = cli.main(["context7-docs", "/facebook/react", "hooks", "--format", "content"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "中文文档内容\n"


def test_doctor_markdown_outputs_human_health_report(monkeypatch, capsys):
    long_message = "provider detail " + ("x" * 220)

    async def fake_doctor():
        return {
            "ok": True,
            "config_file": "C:/tmp/config.json",
            "config_dir": "C:/tmp",
            "config_dir_source": "environment",
            "default_config_file": "C:/Users/example/AppData/Local/smart-search/config.json",
            "legacy_windows_config_file": "C:/Users/example/.config/smart-search/config.json",
            "legacy_windows_config_exists": True,
            "config_dir_override_value": "C:/Users/example/AppData/Local/smart-search",
            "config_dir_override_matches_default": True,
            "log_dir_config_value": "logs",
            "resolved_log_dir": "C:/tmp/logs",
            "file_logging_enabled": False,
            "config_status": "ok: complete",
            "XAI_API_KEY": "未配置",
            "SMART_SEARCH_LOG_DIR": "logs",
            "config_sources": {
                "XAI_API_KEY": "default",
                "SMART_SEARCH_LOG_DIR": "default",
            },
            "minimum_profile_ok": True,
            "minimum_profile_missing": [],
            "capability_status": {
                "main_search": {"ok": True, "configured": ["openai-compatible"], "fallback_chain": ["xai-responses", "openai-compatible"]},
                "docs_search": {"ok": True, "configured": ["context7"], "fallback_chain": ["context7", "exa"]},
                "web_fetch": {"ok": True, "configured": ["tavily", "jina"], "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"]},
            },
            "main_search_connection_tests": {
                "openai-compatible": {
                    "status": "ok",
                    "message": long_message,
                    "response_time_ms": 123.45,
                    "available_models": ["relay-model"],
                    "chat_completion_test": {"status": "ok", "message": "chat ok", "response_time_ms": 100.0},
                    "models_endpoint_test": {"status": "ok", "message": "models ok", "response_time_ms": 23.45},
                }
            },
            "exa_connection_test": {"status": "ok", "message": "Exa ok", "response_time_ms": 11.1},
            "tavily_connection_test": {"status": "ok", "message": "Tavily ok", "response_time_ms": 22.2},
            "jina_connection_test": {"status": "ok", "message": "Jina ok", "response_time_ms": 10.0},
            "firecrawl_connection_test": {"status": "configured", "message": "key configured"},
            "zhipu_connection_test": {"status": "warning", "message": "HTTP 429"},
            "zhipu_mcp_connection_test": {"status": "not_configured", "message": "missing"},
            "context7_connection_test": {"status": "not_configured", "message": "missing"},
        }

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["doctor", "--format", "markdown"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert not out.lstrip().startswith("{")
    assert "# Smart Search Doctor" in out
    assert "Overall: OK" in out
    assert "Config dir source: `environment`" in out
    assert "Default config file: `C:/Users/example/AppData/Local/smart-search/config.json`" in out
    assert "Legacy Windows config file: `C:/Users/example/.config/smart-search/config.json`" in out
    assert "Legacy Windows config exists: OK" in out
    assert "SMART_SEARCH_CONFIG_DIR: `C:/Users/example/AppData/Local/smart-search`" in out
    assert "Override matches default: YES" in out
    assert "override matches the current Windows default path" in out
    assert "Log dir config value: `logs`" in out
    assert "Resolved log dir: `C:/tmp/logs`" in out
    assert "File logging enabled: NO" in out
    assert "## Configuration Values" in out
    assert "| XAI_API_KEY | default | 未配置 |" in out
    assert "## Capabilities" in out
    assert "## Main Search Providers" in out
    assert "openai-compatible" in out
    assert "## Provider Details" in out
    assert long_message in out
    assert "relay-model" in out
    assert "Tavily ok" in out


def test_doctor_content_outputs_non_empty_summary(monkeypatch, capsys):
    async def fake_doctor():
        return {
            "ok": False,
            "config_status": "missing config",
            "minimum_profile_ok": False,
            "capability_status": {
                "main_search": {"ok": False, "configured": [], "fallback_chain": ["xai-responses", "openai-compatible"]}
            },
            "error": "Missing required capability: main_search",
            "error_type": "config_error",
        }

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["doctor", "--format", "content"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_CONFIG_ERROR
    assert out.strip()
    assert "Doctor FAIL" in out
    assert "Minimum profile: FAIL" in out
    assert "Missing required capability" in out


def test_search_alias_uses_canonical_command(monkeypatch, capsys):
    captured = {}

    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        captured["query"] = query
        return {"ok": True, "content": "Answer", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["s", "alias query"])

    assert code == cli.EXIT_OK
    assert captured["query"] == "alias query"
    assert json.loads(capsys.readouterr().out)["content"] == "Answer"


def test_fetch_alias_uses_canonical_command(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": True, "url": url, "content": "Page"}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    code = cli.main(["f", "https://example.com"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["url"] == "https://example.com"


def test_deep_outputs_offline_plan(monkeypatch, capsys):
    captured = {}

    def fake_plan(query, budget="standard", evidence_dir=""):
        captured["query"] = query
        captured["budget"] = budget
        captured["evidence_dir"] = evidence_dir
        return {
            "ok": True,
            "mode": "deep_research",
            "query_mode": "deep",
            "question": query,
            "trigger_source": "explicit_cli",
            "difficulty": "standard",
            "intent_signals": {},
            "decomposition": [],
            "capability_plan": [],
            "evidence_policy": "fetch_before_claim",
            "preflight": {"executed_by_deep_command": False},
            "steps": [],
            "gap_check": {"required": True},
            "final_answer_policy": "cite fetched evidence",
            "usage_boundary": {"deep": "offline planner"},
        }

    async def should_not_run_provider(*args, **kwargs):
        raise AssertionError("deep planner must not call providers")

    monkeypatch.setattr(cli.service, "build_deep_research_plan", fake_plan)
    monkeypatch.setattr(cli.service, "search", should_not_run_provider)
    monkeypatch.setattr(cli.service, "doctor", should_not_run_provider)

    code = cli.main([
        "deep",
        "深度搜索一下最近的比特币行情",
        "--budget",
        "deep",
        "--evidence-dir",
        "C:/tmp/custom-evidence",
        "--format",
        "json",
    ])

    data = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert captured == {
        "query": "深度搜索一下最近的比特币行情",
        "budget": "deep",
        "evidence_dir": "C:/tmp/custom-evidence",
    }
    assert data["mode"] == "deep_research"
    assert data["preflight"]["executed_by_deep_command"] is False


def test_deep_alias_and_markdown_output(monkeypatch, capsys):
    def fake_plan(query, budget="standard", evidence_dir=""):
        return {
            "ok": True,
            "mode": "deep_research",
            "question": query,
            "difficulty": "standard",
            "evidence_policy": "fetch_before_claim",
            "usage_boundary": {"search": "fast", "deep": "planner", "execution": "execute steps"},
            "decomposition": [{"id": "sq1", "question": "Subquestion"}],
            "steps": [
                {
                    "id": "s1",
                    "subquestion_id": "sq1",
                    "tool": "fetch",
                    "purpose": "fetch evidence",
                    "command": "smart-search fetch \"https://example.com\" --format markdown",
                }
            ],
            "gap_check": {"rule": "fetch missing evidence"},
        }

    monkeypatch.setattr(cli.service, "build_deep_research_plan", fake_plan)

    code = cli.main(["dr", "React useEffect 最新文档", "--format", "markdown"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "# Deep Research Plan" in out
    assert "React useEffect 最新文档" in out
    assert "smart-search fetch" in out


def test_research_command_uses_service_and_outputs_json(monkeypatch, capsys, tmp_path):
    captured = {}

    async def fake_research(query, budget="deep", evidence_dir="", fallback="auto"):
        captured.update({"query": query, "budget": budget, "evidence_dir": evidence_dir, "fallback": fallback})
        return {
            "ok": True,
            "mode": "deep_research_execution",
            "query_mode": "research",
            "question": query,
            "final_answer": "Evidence answer",
            "content": "Evidence answer",
            "citations": [{"url": "https://example.com", "title": "Example", "provider": "jina"}],
            "evidence_items": [{"url": "https://example.com", "provider": "jina", "content": "Evidence"}],
            "gap_check": {"status": "closed", "gaps": []},
            "provider_attempts": [],
            "fallback_used": False,
            "degraded": False,
            "route_policy_version": "research-router-v1",
            "evidence_dir": evidence_dir,
        }

    monkeypatch.setattr(cli.service, "research", fake_research)

    code = cli.main([
        "research",
        "React docs",
        "--budget",
        "standard",
        "--evidence-dir",
        str(tmp_path),
        "--fallback",
        "off",
        "--format",
        "json",
    ])

    assert code == cli.EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert captured == {"query": "React docs", "budget": "standard", "evidence_dir": str(tmp_path), "fallback": "off"}
    assert data["query_mode"] == "research"
    assert data["final_answer"] == "Evidence answer"


def test_research_markdown_and_content_output(monkeypatch, capsys):
    async def fake_research(query, budget="deep", evidence_dir="", fallback="auto"):
        return {
            "ok": True,
            "question": query,
            "final_answer": "Evidence answer",
            "content": "Evidence answer",
            "citations": [{"url": "https://example.com", "title": "Example", "provider": "jina"}],
            "gap_check": {"gaps": []},
            "fallback_used": True,
            "degraded": False,
            "route_policy_version": "research-router-v1",
            "evidence_dir": "C:/tmp/evidence",
        }

    monkeypatch.setattr(cli.service, "research", fake_research)

    assert cli.main(["rs", "React docs", "--format", "markdown"]) == cli.EXIT_OK
    markdown = capsys.readouterr().out
    assert "# Research Report" in markdown
    assert "Evidence answer" in markdown
    assert "https://example.com" in markdown

    assert cli.main(["research", "React docs", "--format", "content"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "Evidence answer\n"


def test_exa_search_passes_powershell_split_domains(monkeypatch, capsys):
    captured = {}

    async def fake_exa_search(
        query,
        num_results=5,
        search_type="neural",
        include_text=False,
        include_highlights=False,
        start_published_date="",
        include_domains="",
        exclude_domains="",
        category="",
    ):
        captured["query"] = query
        captured["include_domains"] = include_domains
        return {"ok": True, "query": query, "results": []}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)

    code = cli.main(["exa-search", "query", "--include-domains", "github.com", "freertos.org"])

    assert code == cli.EXIT_OK
    assert captured["include_domains"] == ["github.com", "freertos.org"]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_doctor_alias_uses_canonical_command(monkeypatch, capsys):
    async def fake_doctor():
        return {"ok": True, "config_status": "ok"}

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["d"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["config_status"] == "ok"


def test_search_timeout_respects_requested_format_and_exit_4(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "relay-timeout-model")
    monkeypatch.setenv("OPENAI_COMPATIBLE_STREAM", "true")

    async def slow_search(query, **kwargs):
        await asyncio.sleep(1)
        return {
            "ok": True,
            "query": query,
            "content": "late answer",
            "sources": [{"url": "https://example.com"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", slow_search)

    code = cli.main(["search", "slow query", "--timeout", "0.01", "--format", "markdown"])

    assert code == cli.EXIT_NETWORK_ERROR
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.startswith("\n## Errors") or "## Errors" in out.out
    assert "network_error" in out.out
    assert "0.01" in out.out
    assert "seconds" in out.out
    assert "relay-timeout-model" in out.out
    assert "Stream: YES" in out.out
    assert "smart-search diagnose openai-compatible --format markdown" in out.out

    code = cli.main(["search", "slow query", "--timeout", "0.01", "--format", "content"])
    assert code == cli.EXIT_NETWORK_ERROR
    content_out = capsys.readouterr().out
    assert "network_error" in content_out
    assert "Search timed out after 0.01 seconds" in content_out

    code = cli.main(["search", "slow query", "--timeout", "0.01", "--format", "json"])
    assert code == cli.EXIT_NETWORK_ERROR
    data = json.loads(capsys.readouterr().out)
    assert data["sources_count"] == 0
    assert data["primary_sources"] == []
    assert data["primary_sources_count"] == 0
    assert data["extra_sources"] == []
    assert data["extra_sources_count"] == 0
    assert data["source_warning"] == ""
    assert data["diagnose_command"] == "smart-search diagnose openai-compatible --format markdown"
    assert data["model"] == "relay-timeout-model"
    assert data["stream"] is True
    assert data["recommendation"]


def test_markdown_search_includes_sources(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "content": "Answer",
            "sources": [{"url": "https://example.com", "title": "Example"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "query", "--format", "markdown"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Answer" in out
    assert "[Example](https://example.com)" in out


def test_markdown_search_labels_primary_and_extra_sources(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "content": "Answer",
            "primary_sources": [{"url": "https://primary.example.com", "title": "Primary"}],
            "primary_sources_count": 1,
            "extra_sources": [{"url": "https://extra.example.com", "title": "Extra"}],
            "extra_sources_count": 1,
            "sources": [
                {"url": "https://primary.example.com", "title": "Primary"},
                {"url": "https://extra.example.com", "title": "Extra"},
            ],
            "sources_count": 2,
            "source_warning": "extra_sources are retrieved in parallel",
        }

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "query", "--format", "markdown"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "## Primary Sources" in out
    assert "[Primary](https://primary.example.com)" in out
    assert "## Extra Sources" in out
    assert "[Extra](https://extra.example.com)" in out
    assert "extra_sources are retrieved in parallel" in out


def test_config_error_exit_code(monkeypatch, capsys):
    async def fake_doctor():
        return {"ok": False, "error_type": "config_error", "XAI_API_KEY": "未配置"}

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["doctor"])

    assert code == cli.EXIT_CONFIG_ERROR
    assert json.loads(capsys.readouterr().out)["XAI_API_KEY"] == "未配置"


def test_network_error_exit_code(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": False, "error_type": "network_error", "error": "upstream timeout", "url": url}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    code = cli.main(["fetch", "https://example.com"])

    assert code == cli.EXIT_NETWORK_ERROR
    assert json.loads(capsys.readouterr().out)["error"] == "upstream timeout"


def test_stdout_falls_back_for_gbk_unencodable_unicode(monkeypatch):
    fake_stdout = GbkStdout()
    monkeypatch.setattr(cli.sys, "stdout", fake_stdout)

    code = cli._print_result("exa-search", {"ok": True, "content": "A\u2060B"}, "json")

    assert code == cli.EXIT_OK
    out = fake_stdout.getvalue()
    assert "\\u2060" in out
    assert json.loads(out)["content"] == "A\u2060B"


def test_gbk_stdout_keeps_json_parseable_with_chinese_and_unencodable_unicode(monkeypatch):
    fake_stdout = GbkStdout()
    monkeypatch.setattr(cli.sys, "stdout", fake_stdout)

    code = cli._print_result("search", {"ok": True, "content": "中文A\u2060B📅"}, "json")

    assert code == cli.EXIT_OK
    out = fake_stdout.getvalue()
    assert "中文" in out
    assert "\\u2060" in out
    assert "\\ud83d\\udcc5" in out
    assert json.loads(out)["content"] == "中文A\u2060B📅"


def test_real_doctor_ignores_legacy_primary_env_and_returns_config_exit(monkeypatch, capsys):
    secret = "placeholder-test-secret"
    monkeypatch.setenv("SMART_SEARCH_API_URL", "https://api.example.com/v1")
    monkeypatch.setenv("SMART_SEARCH_API_KEY", secret)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_URL", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == cli.EXIT_CONFIG_ERROR
    assert data["ok"] is False
    assert data["error_type"] == "config_error"
    assert "SMART_SEARCH_API_URL" not in data
    assert "SMART_SEARCH_API_KEY" not in data
    assert data["capability_status"]["main_search"]["configured"] == []
    assert secret not in out


def test_model_set_returns_parameter_error(monkeypatch, capsys):
    def fake_set_model(model):
        return {
            "ok": False,
            "error_type": "parameter_error",
            "error": "Use XAI_MODEL or OPENAI_COMPATIBLE_MODEL.",
            "config_file": "C:/tmp/smart-search-config.json",
        }

    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    code = cli.main(["model", "set", "grok-4-fast"])

    assert code == cli.EXIT_PARAMETER_ERROR
    assert json.loads(capsys.readouterr().out)["error_type"] == "parameter_error"


def test_model_aliases_use_canonical_commands(monkeypatch, capsys):
    def fake_current_model():
        return {"ok": True, "current_model": "grok-4-fast"}

    def fake_set_model(model):
        return {"ok": False, "error_type": "parameter_error", "error": "Use explicit provider model keys."}

    monkeypatch.setattr(cli.service, "current_model", fake_current_model)
    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    assert cli.main(["mdl", "cur"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["current_model"] == "grok-4-fast"
    assert cli.main(["mdl", "s", "grok-4-fast"]) == cli.EXIT_PARAMETER_ERROR
    assert json.loads(capsys.readouterr().out)["error_type"] == "parameter_error"


def test_config_set_masks_value(monkeypatch, capsys):
    def fake_config_set(key, value):
        return {"ok": True, "key": key, "value": "xai-********cret", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)

    code = cli.main(["config", "set", "XAI_API_KEY", "xai-test-secret"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "xai-test-secret" not in out
    assert json.loads(out)["value"] == "xai-********cret"


def test_config_list_does_not_request_secrets(monkeypatch, capsys):
    captured = {}

    def fake_config_list(show_secrets=False):
        captured["show_secrets"] = show_secrets
        return {"ok": True, "values": {"XAI_API_KEY": "xai-********cret"}}

    monkeypatch.setattr(cli.service, "config_list", fake_config_list)

    code = cli.main(["config", "list"])

    assert code == cli.EXIT_OK
    assert captured["show_secrets"] is False
    assert json.loads(capsys.readouterr().out)["values"]["XAI_API_KEY"].endswith("cret")


def test_config_aliases_use_canonical_commands(monkeypatch, capsys):
    captured = {}

    def fake_config_list(show_secrets=False):
        captured["show_secrets"] = show_secrets
        return {"ok": True, "values": {"XAI_MODEL": "grok"}}

    def fake_config_set(key, value):
        captured["set"] = (key, value)
        return {"ok": True, "key": key, "value": value}

    def fake_config_unset(key):
        captured["unset"] = key
        return {"ok": True, "key": key}

    monkeypatch.setattr(cli.service, "config_list", fake_config_list)
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_unset", fake_config_unset)

    assert cli.main(["cfg", "ls"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["values"]["XAI_MODEL"] == "grok"
    assert captured["show_secrets"] is False

    assert cli.main(["cfg", "s", "XAI_MODEL", "grok-4-fast"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["value"] == "grok-4-fast"
    assert captured["set"] == ("XAI_MODEL", "grok-4-fast")

    assert cli.main(["cfg", "rm", "XAI_MODEL"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["key"] == "XAI_MODEL"
    assert captured["unset"] == "XAI_MODEL"


def test_config_set_legacy_main_search_key_returns_parameter_error(monkeypatch, capsys):
    def fake_config_set(key, value):
        return {
            "ok": False,
            "error_type": "parameter_error",
            "error": f"Unsupported config key: {key}",
        }

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)

    code = cli.main(["config", "set", "SMART_SEARCH_API_KEY", "sk-test-secret"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert data["error_type"] == "parameter_error"
    assert "Unsupported config key: SMART_SEARCH_API_KEY" in data["error"]


def test_smoke_markdown_and_content_are_human_readable(monkeypatch, capsys):
    async def fake_smoke(mode="mock"):
        return {
            "ok": True,
            "mode": mode,
            "failed_cases": [],
            "degraded_cases": ["zhipu search"],
            "cases": [
                {"name": "doctor minimum profile", "ok": True},
                {"name": "zhipu search", "ok": False, "severity": "degraded", "error": "HTTP 429"},
            ],
        }

    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    markdown_code = cli.main(["smoke", "--mock", "--format", "markdown"])
    markdown_out = capsys.readouterr().out
    content_code = cli.main(["smoke", "--mock", "--format", "content"])
    content_out = capsys.readouterr().out

    assert markdown_code == cli.EXIT_OK
    assert "# Smart Search Smoke" in markdown_out
    assert "zhipu search" in markdown_out
    assert not markdown_out.lstrip().startswith("{")
    assert content_code == cli.EXIT_OK
    assert "Smoke mock OK" in content_out
    assert "2 cases" in content_out


def test_config_markdown_and_content_are_masked_and_non_json(monkeypatch, capsys):
    def fake_config_path():
        return {
            "ok": True,
            "config_file": "C:/tmp/config.json",
            "config_dir": "C:/tmp",
            "config_dir_source": "environment",
            "default_config_file": "C:/Users/example/AppData/Local/smart-search/config.json",
            "legacy_windows_config_file": "C:/Users/example/.config/smart-search/config.json",
            "legacy_windows_config_exists": False,
            "config_dir_override_value": "C:/tmp",
            "config_dir_override_matches_default": False,
            "exists": True,
        }

    def fake_config_list(show_secrets=False):
        return {"ok": True, "config_file": "C:/tmp/config.json", "values": {"XAI_API_KEY": "xai-********cret", "XAI_MODEL": "grok"}}

    def fake_config_set(key, value):
        return {"ok": True, "config_file": "C:/tmp/config.json", "key": key, "value": "xai-********cret"}

    def fake_config_unset(key):
        return {"ok": True, "config_file": "C:/tmp/config.json", "key": key}

    monkeypatch.setattr(cli.service, "config_path", fake_config_path)
    monkeypatch.setattr(cli.service, "config_list", fake_config_list)
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_unset", fake_config_unset)

    assert cli.main(["config", "path", "--format", "markdown"]) == cli.EXIT_OK
    path_out = capsys.readouterr().out
    assert "# Smart Search Config" in path_out
    assert "C:/tmp/config.json" in path_out
    assert "Config dir source: `environment`" in path_out
    assert "SMART_SEARCH_CONFIG_DIR: `C:/tmp`" in path_out

    assert cli.main(["config", "list", "--format", "markdown"]) == cli.EXIT_OK
    list_out = capsys.readouterr().out
    assert "xai-test-secret" not in list_out
    assert "xai-********cret" in list_out
    assert not list_out.lstrip().startswith("{")

    assert cli.main(["config", "set", "XAI_API_KEY", "xai-test-secret", "--format", "markdown"]) == cli.EXIT_OK
    set_out = capsys.readouterr().out
    assert "xai-test-secret" not in set_out
    assert "XAI_API_KEY" in set_out

    assert cli.main(["config", "unset", "XAI_API_KEY", "--format", "content"]) == cli.EXIT_OK
    unset_out = capsys.readouterr().out
    assert "Config OK" in unset_out
    assert "key=XAI_API_KEY" in unset_out


def test_model_markdown_and_content_are_human_readable(monkeypatch, capsys):
    def fake_current_model():
        return {
            "ok": True,
            "xai_model": "grok-4-fast",
            "openai_compatible_model": "relay-model",
            "config_file": "C:/tmp/config.json",
        }

    def fake_set_model(model):
        return {"ok": False, "error_type": "parameter_error", "error": "Use explicit provider model keys."}

    monkeypatch.setattr(cli.service, "current_model", fake_current_model)
    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    assert cli.main(["model", "current", "--format", "markdown"]) == cli.EXIT_OK
    markdown_out = capsys.readouterr().out
    assert "# Smart Search Model" in markdown_out
    assert "grok-4-fast" in markdown_out
    assert "relay-model" in markdown_out

    assert cli.main(["model", "set", "grok", "--format", "content"]) == cli.EXIT_PARAMETER_ERROR
    content_out = capsys.readouterr().out
    assert "Model FAIL" in content_out
    assert "Use explicit provider model keys." in content_out


def test_provider_markdown_outputs_result_lists(monkeypatch, capsys):
    async def fake_exa_search(*args, **kwargs):
        return {"ok": True, "query": "query", "provider": "exa", "results": [{"title": "Example", "url": "https://example.com", "text": "body"}]}

    async def fake_exa_similar(*args, **kwargs):
        return {"ok": True, "url": "https://source.example.com", "results": [{"title": "Similar", "url": "https://similar.example.com"}]}

    async def fake_zhipu_search(*args, **kwargs):
        return {"ok": True, "query": "news", "provider": "zhipu", "results": [{"title": "News", "url": "https://news.example.com", "description": "desc"}]}

    async def fake_zhipu_mcp_search(*args, **kwargs):
        return {"ok": True, "query": "news", "provider": "zhipu-mcp", "tool": "web_search_prime", "results": [{"title": "MCP News", "url": "https://mcp.example.com"}]}

    async def fake_zhipu_mcp_reader(*args, **kwargs):
        return {"ok": True, "url": "https://source.example.com", "provider": "zhipu-mcp-reader", "tool": "webReader", "content": "# MCP Page"}

    async def fake_context7_library(*args, **kwargs):
        return {"ok": True, "query": "react", "provider": "context7", "results": [{"id": "/facebook/react", "title": "React", "description": "docs"}]}

    async def fake_map_site(*args, **kwargs):
        return {"ok": True, "url": "https://docs.example.com", "base_url": "https://docs.example.com", "results": ["https://docs.example.com/api"]}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)
    monkeypatch.setattr(cli.service, "exa_find_similar", fake_exa_similar)
    monkeypatch.setattr(cli.service, "zhipu_search", fake_zhipu_search)
    monkeypatch.setattr(cli.service, "zhipu_mcp_search", fake_zhipu_mcp_search)
    monkeypatch.setattr(cli.service, "zhipu_mcp_reader", fake_zhipu_mcp_reader)
    monkeypatch.setattr(cli.service, "context7_library", fake_context7_library)
    monkeypatch.setattr(cli.service, "map_site", fake_map_site)

    cases = [
        (["exa-search", "query", "--format", "markdown"], "Example", "https://example.com"),
        (["exa-similar", "https://source.example.com", "--format", "markdown"], "Similar", "https://similar.example.com"),
        (["zhipu-search", "news", "--format", "markdown"], "News", "https://news.example.com"),
        (["zhipu-mcp-search", "news", "--format", "markdown"], "MCP News", "https://mcp.example.com"),
        (["zhipu-mcp-reader", "https://source.example.com", "--format", "markdown"], "MCP Page", "Zhipu Coding Plan MCP Reader"),
        (["context7-library", "react", "--format", "markdown"], "React", "/facebook/react"),
        (["map", "https://docs.example.com", "--format", "markdown"], "https://docs.example.com/api", "Site Map"),
    ]
    for argv, first, second in cases:
        assert cli.main(argv) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert not out.lstrip().startswith("{")
        assert first in out
        assert second in out


def test_provider_content_outputs_plain_result_list(monkeypatch, capsys):
    async def fake_exa_search(*args, **kwargs):
        return {"ok": True, "query": "query", "results": [{"title": "Example", "url": "https://example.com", "text": "body"}]}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)

    code = cli.main(["exa-search", "query", "--format", "content"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert out.startswith("1. Example - https://example.com")
    assert not out.lstrip().startswith("{")


def test_provider_markdown_empty_results_are_clear(monkeypatch, capsys):
    async def fake_exa_search(*args, **kwargs):
        return {"ok": True, "query": "query", "results": []}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)

    code = cli.main(["exa-search", "query", "--format", "markdown"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "No results." in out


def test_all_formatted_commands_have_non_json_markdown(monkeypatch):
    async def fake_search(*args, **kwargs):
        return {"ok": True, "content": "Answer", "sources": []}

    async def fake_fetch(*args, **kwargs):
        return {"ok": True, "content": "Page"}

    async def fake_map(*args, **kwargs):
        return {"ok": True, "results": ["https://example.com/api"]}

    async def fake_exa(*args, **kwargs):
        return {"ok": True, "results": [{"title": "Example", "url": "https://example.com"}]}

    async def fake_zhipu(*args, **kwargs):
        return {"ok": True, "results": [{"title": "News", "url": "https://news.example.com"}]}

    async def fake_zhipu_mcp(*args, **kwargs):
        return {"ok": True, "provider": "zhipu-mcp", "tool": "web_search_prime", "results": [{"title": "MCP", "url": "https://mcp.example.com"}]}

    async def fake_zhipu_mcp_reader(*args, **kwargs):
        return {"ok": True, "provider": "zhipu-mcp-reader", "tool": "webReader", "content": "MCP Page"}

    async def fake_c7_library(*args, **kwargs):
        return {"ok": True, "results": [{"id": "/lib", "title": "Library"}]}

    async def fake_c7_docs(*args, **kwargs):
        return {"ok": True, "library_id": "/lib", "query": "hooks", "content": "Docs"}

    async def fake_doctor():
        return {"ok": True, "config_status": "ok", "minimum_profile_ok": True}

    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": [{"name": "case", "ok": True}]}

    async def fake_research(query, budget="deep", evidence_dir="", fallback="auto"):
        return {"ok": True, "question": query, "content": "Research", "final_answer": "Research", "citations": [], "gap_check": {"gaps": []}}

    def fake_plan(*args, **kwargs):
        return {"ok": True, "mode": "deep_research", "question": "q", "difficulty": "standard", "evidence_policy": "fetch_before_claim"}

    def fake_config_path():
        return {"ok": True, "config_file": "C:/tmp/config.json"}

    def fake_config_list(show_secrets=False):
        return {"ok": True, "values": {"XAI_MODEL": "grok"}}

    def fake_config_set(key, value):
        return {"ok": True, "key": key, "value": "***"}

    def fake_config_unset(key):
        return {"ok": True, "key": key}

    def fake_current_model():
        return {"ok": True, "xai_model": "grok"}

    def fake_set_model(model):
        return {"ok": False, "error_type": "parameter_error", "error": "Use explicit provider model keys."}

    monkeypatch.setattr(cli.service, "search", fake_search)
    monkeypatch.setattr(cli.service, "fetch", fake_fetch)
    monkeypatch.setattr(cli.service, "map_site", fake_map)
    monkeypatch.setattr(cli.service, "exa_search", fake_exa)
    monkeypatch.setattr(cli.service, "exa_find_similar", fake_exa)
    monkeypatch.setattr(cli.service, "zhipu_search", fake_zhipu)
    monkeypatch.setattr(cli.service, "zhipu_mcp_search", fake_zhipu_mcp)
    monkeypatch.setattr(cli.service, "zhipu_mcp_reader", fake_zhipu_mcp_reader)
    monkeypatch.setattr(cli.service, "zhipu_mcp_search_doc", fake_zhipu_mcp)
    monkeypatch.setattr(cli.service, "zhipu_mcp_repo_structure", fake_zhipu_mcp)
    monkeypatch.setattr(cli.service, "zhipu_mcp_read_file", fake_zhipu_mcp)
    monkeypatch.setattr(cli.service, "context7_library", fake_c7_library)
    monkeypatch.setattr(cli.service, "context7_docs", fake_c7_docs)
    monkeypatch.setattr(cli.service, "doctor", fake_doctor)
    monkeypatch.setattr(cli.service, "smoke", fake_smoke)
    monkeypatch.setattr(cli.service, "research", fake_research)
    monkeypatch.setattr(cli.service, "build_deep_research_plan", fake_plan)
    monkeypatch.setattr(cli.service, "config_path", fake_config_path)
    monkeypatch.setattr(cli.service, "config_list", fake_config_list)
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_unset", fake_config_unset)
    monkeypatch.setattr(cli.service, "current_model", fake_current_model)
    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    command_cases = [
        ("search", ["search", "query", "--format", "markdown"]),
        ("fetch", ["fetch", "https://example.com", "--format", "markdown"]),
        ("map", ["map", "https://example.com", "--format", "markdown"]),
        ("exa-search", ["exa-search", "query", "--format", "markdown"]),
        ("exa-similar", ["exa-similar", "https://example.com", "--format", "markdown"]),
        ("zhipu-search", ["zhipu-search", "query", "--format", "markdown"]),
        ("zhipu-mcp-search", ["zhipu-mcp-search", "query", "--format", "markdown"]),
        ("zhipu-mcp-reader", ["zhipu-mcp-reader", "https://example.com", "--format", "markdown"]),
        ("zhipu-mcp-search-doc", ["zhipu-mcp-search-doc", "owner/repo", "install", "--format", "markdown"]),
        ("zhipu-mcp-repo-structure", ["zhipu-mcp-repo-structure", "owner/repo", "--format", "markdown"]),
        ("zhipu-mcp-read-file", ["zhipu-mcp-read-file", "owner/repo", "README.md", "--format", "markdown"]),
        ("context7-library", ["context7-library", "react", "--format", "markdown"]),
        ("context7-docs", ["context7-docs", "/lib", "hooks", "--format", "markdown"]),
        ("deep", ["deep", "query", "--format", "markdown"]),
        ("research", ["research", "query", "--format", "markdown"]),
        ("smoke", ["smoke", "--format", "markdown"]),
        ("doctor", ["doctor", "--format", "markdown"]),
        ("diagnose", ["diagnose", "openai-compatible", "--format", "markdown"]),
        ("skills-status", ["skills", "status", "--targets", "codex", "--format", "markdown"]),
        ("config-path", ["config", "path", "--format", "markdown"]),
        ("config-list", ["config", "list", "--format", "markdown"]),
        ("config-set", ["config", "set", "XAI_MODEL", "grok", "--format", "markdown"]),
        ("config-unset", ["config", "unset", "XAI_MODEL", "--format", "markdown"]),
        ("model-current", ["model", "current", "--format", "markdown"]),
        ("model-set", ["model", "set", "grok", "--format", "markdown"]),
    ]

    for name, argv in command_cases:
        command = cli.build_parser().parse_args(argv).command
        data = {
            "search": {"ok": True, "content": "Answer", "sources": []},
            "fetch": {"ok": True, "content": "Page"},
            "map": {"ok": True, "results": ["https://example.com/api"]},
            "exa-search": {"ok": True, "results": [{"title": "Example", "url": "https://example.com"}]},
            "exa-similar": {"ok": True, "results": [{"title": "Example", "url": "https://example.com"}]},
            "zhipu-search": {"ok": True, "results": [{"title": "News", "url": "https://news.example.com"}]},
            "zhipu-mcp-search": {"ok": True, "provider": "zhipu-mcp", "tool": "web_search_prime", "results": [{"title": "MCP", "url": "https://mcp.example.com"}]},
            "zhipu-mcp-reader": {"ok": True, "provider": "zhipu-mcp-reader", "tool": "webReader", "content": "MCP Page"},
            "zhipu-mcp-search-doc": {"ok": True, "provider": "zhipu-mcp-zread", "tool": "search_doc", "results": [{"title": "Doc", "url": "https://docs.example.com"}]},
            "zhipu-mcp-repo-structure": {"ok": True, "provider": "zhipu-mcp-zread", "tool": "get_repo_structure", "content": "tree"},
            "zhipu-mcp-read-file": {"ok": True, "provider": "zhipu-mcp-zread", "tool": "read_file", "content": "file"},
            "context7-library": {"ok": True, "results": [{"id": "/lib", "title": "Library"}]},
            "context7-docs": {"ok": True, "library_id": "/lib", "query": "hooks", "content": "Docs"},
            "deep": {"ok": True, "mode": "deep_research", "question": "q", "difficulty": "standard", "evidence_policy": "fetch_before_claim"},
            "research": {"ok": True, "question": "q", "content": "Research", "final_answer": "Research", "citations": [], "gap_check": {"gaps": []}},
            "smoke": {"ok": True, "mode": "mock", "failed_cases": [], "cases": [{"name": "case", "ok": True}]},
            "doctor": {"ok": True, "config_status": "ok", "minimum_profile_ok": True},
            "diagnose": {"ok": True, "provider": "openai-compatible", "summary": "ok", "recommendation": "none"},
            "skills": {"ok": True, "targets": [{"target": "codex", "status": "up_to_date"}], "status_counts": {"up_to_date": 1}},
            "config": {"ok": True, "config_file": "C:/tmp/config.json", "values": {"XAI_MODEL": "grok"}},
            "model": {"ok": True, "xai_model": "grok"},
        }[command]
        rendered = cli._render(command, data, "markdown")
        assert rendered.strip(), name
        assert not rendered.lstrip().startswith("{"), name


def test_non_content_commands_have_non_empty_content_fallback():
    cases = {
        "doctor": {"ok": True, "config_status": "ok", "minimum_profile_ok": True},
        "diagnose": {"ok": True, "provider": "openai-compatible", "summary": "ok", "recommendation": "none"},
        "smoke": {"ok": True, "mode": "mock", "cases": [], "failed_cases": []},
        "config": {"ok": True, "config_file": "C:/tmp/config.json"},
        "model": {"ok": True, "xai_model": "grok"},
        "skills": {"ok": True, "targets": [{"target": "codex", "status": "up_to_date"}], "status_counts": {"up_to_date": 1}},
        "exa-search": {"ok": True, "results": [{"title": "Example", "url": "https://example.com"}]},
        "anysearch-search": {"ok": True, "provider": "anysearch", "results": [{"title": "AnySearch", "url": ""}]},
    }
    for command, data in cases.items():
        rendered = cli._render(command, data, "content")
        assert rendered.strip(), command
        assert not rendered.lstrip().startswith("{"), command


def test_skills_status_reports_missing_and_update_writes_target(tmp_path, capsys):
    status_code = cli.main(["skills", "status", "--targets", "codex", "--skills-root", str(tmp_path), "--format", "json"])
    status = json.loads(capsys.readouterr().out)

    assert status_code == cli.EXIT_OK
    assert status["selected"] == ["codex"]
    assert status["targets"][0]["status"] == "missing"
    assert status["targets"][0]["hash_match"] is False

    update_code = cli.main(["skills", "update", "--targets", "codex", "--skills-root", str(tmp_path), "--format", "json"])
    update = json.loads(capsys.readouterr().out)

    assert update_code == cli.EXIT_OK
    assert update["installed_count"] == 1
    assert (tmp_path / ".codex" / "skills" / "smart-search-cli" / "SKILL.md").is_file()

    status_code = cli.main(["skills", "status", "--targets", "codex", "--skills-root", str(tmp_path), "--format", "json"])
    status = json.loads(capsys.readouterr().out)

    assert status_code == cli.EXIT_OK
    assert status["targets"][0]["status"] == "up_to_date"
    assert status["targets"][0]["hash_match"] is True


def test_skills_update_all_selects_every_target(tmp_path, capsys):
    code = cli.main(["skills", "update", "--all", "--skills-root", str(tmp_path), "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert data["installed_count"] == len(skill_installer.SKILL_TARGETS)
    assert set(data["selected"]) == {target.target_id for target in skill_installer.SKILL_TARGETS}


def test_skills_unknown_target_returns_parameter_error(tmp_path, capsys):
    code = cli.main(["skills", "status", "--targets", "unknown", "--skills-root", str(tmp_path), "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert data["error_type"] == "parameter_error"
    assert "Unknown skill target" in data["error"]
    assert not (tmp_path / ".codex" / "skills" / "smart-search-cli").exists()


def test_setup_non_interactive_saves_values(monkeypatch, capsys):
    saved = {}

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--xai-api-key",
        "xai-test-secret",
        "--xai-model",
        "xai-model",
        "--xai-tools-explicit",
        "web_search",
        "--openai-compatible-api-url",
        "https://relay.example.com/v1",
        "--openai-compatible-api-key",
        "relay-test-secret",
        "--openai-compatible-model",
        "relay-model",
        "--openai-compatible-stream",
        "true",
        "--validation-level",
        "balanced",
        "--fallback-mode",
        "auto",
        "--minimum-profile",
        "standard",
        "--zhipu-key",
        "zhipu-secret",
        "--zhipu-api-url",
        "zhipu.example.com/api",
        "--zhipu-search-engine",
        "search_pro",
        "--zhipu-mcp-key",
        "zmcp-secret",
        "--zhipu-mcp-search-api-url",
        "https://zmcp.example.com/search",
        "--zhipu-mcp-reader-api-url",
        "https://zmcp.example.com/reader",
        "--zhipu-mcp-zread-api-url",
        "https://zmcp.example.com/zread",
        "--zhipu-mcp-timeout",
        "8",
        "--jina-key",
        "jina-secret",
        "--jina-reader-api-url",
        "r.jina.ai",
        "--jina-respond-with",
        "readerlm-v2",
        "--jina-timeout",
        "10",
        "--context7-key",
        "ctx-secret",
        "--tavily-api-url",
        "pool.example.com",
        "--tavily-key",
        "th-test-secret",
        "--firecrawl-api-url",
        "firecrawl.example.com/v2",
        "--firecrawl-key",
        "firecrawl-secret",
        "--anysearch-api-url",
        "anysearch.example.com/mcp",
        "--anysearch-key",
        "as-test-secret",
        "--anysearch-timeout",
        "9",
    ])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert saved["XAI_API_KEY"] == "xai-test-secret"
    assert saved["XAI_MODEL"] == "xai-model"
    assert saved["XAI_TOOLS"] == "web_search"
    assert saved["OPENAI_COMPATIBLE_API_URL"] == "https://relay.example.com/v1"
    assert saved["OPENAI_COMPATIBLE_API_KEY"] == "relay-test-secret"
    assert saved["OPENAI_COMPATIBLE_MODEL"] == "relay-model"
    assert saved["OPENAI_COMPATIBLE_STREAM"] == "true"
    assert saved["SMART_SEARCH_VALIDATION_LEVEL"] == "balanced"
    assert saved["SMART_SEARCH_FALLBACK_MODE"] == "auto"
    assert saved["SMART_SEARCH_MINIMUM_PROFILE"] == "standard"
    assert saved["ZHIPU_API_KEY"] == "zhipu-secret"
    assert saved["ZHIPU_API_URL"] == "https://zhipu.example.com/api"
    assert saved["ZHIPU_SEARCH_ENGINE"] == "search_pro"
    assert saved["ZHIPU_MCP_API_KEY"] == "zmcp-secret"
    assert saved["ZHIPU_MCP_SEARCH_API_URL"] == "https://zmcp.example.com/search"
    assert saved["ZHIPU_MCP_READER_API_URL"] == "https://zmcp.example.com/reader"
    assert saved["ZHIPU_MCP_ZREAD_API_URL"] == "https://zmcp.example.com/zread"
    assert saved["ZHIPU_MCP_TIMEOUT_SECONDS"] == "8"
    assert saved["JINA_API_KEY"] == "jina-secret"
    assert saved["JINA_READER_API_URL"] == "https://r.jina.ai"
    assert saved["JINA_RESPOND_WITH"] == "readerlm-v2"
    assert saved["JINA_TIMEOUT_SECONDS"] == "10"
    assert saved["CONTEXT7_API_KEY"] == "ctx-secret"
    assert saved["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"
    assert saved["TAVILY_API_KEY"] == "th-test-secret"
    assert saved["FIRECRAWL_API_URL"] == "https://firecrawl.example.com/v2"
    assert saved["FIRECRAWL_API_KEY"] == "firecrawl-secret"
    assert saved["ANYSEARCH_API_URL"] == "https://anysearch.example.com/mcp"
    assert saved["ANYSEARCH_API_KEY"] == "as-test-secret"
    assert saved["ANYSEARCH_TIMEOUT_SECONDS"] == "9"
    assert "xai-test-secret" not in out
    assert "th-test-secret" not in out
    assert "jina-secret" not in out
    assert "zmcp-secret" not in out
    assert "as-test-secret" not in out


def test_setup_non_interactive_rejects_legacy_flags(capsys):
    for flag, value in [
        ("--api-url", "https://api.example.com/v1"),
        ("--api-key", "sk-test-secret"),
        ("--api-mode", "chat-completions"),
        ("--model", "test-model"),
        ("--xai-tools", "web_search"),
    ]:
        try:
            cli.main(["setup", "--non-interactive", flag, value])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"{flag} should be rejected by argparse")
        capsys.readouterr()


def test_setup_non_interactive_installs_selected_skills_under_user_root_override(monkeypatch, tmp_path, capsys):
    saved = {}

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--install-skills",
        "codex,claude,cursor",
        "--skills-root",
        str(tmp_path),
    ])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert saved == {}
    assert data["skills"]["installed_count"] == 3
    assert (tmp_path / ".codex" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "smart-search-cli" / "SKILL.md").is_file()


def test_setup_non_interactive_installs_skill_under_home_by_default(monkeypatch, tmp_path, capsys):
    fake_home = tmp_path / "home"

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(skill_installer.Path, "home", lambda: fake_home)

    code = cli.main([
        "setup",
        "--non-interactive",
        "--install-skills",
        "codex,hermes-agent",
    ])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert data["skills"]["installed_count"] == 2
    assert {item["target"] for item in data["skills"]["installed"]} == {"codex", "hermes"}
    assert (fake_home / ".codex" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (fake_home / ".hermes" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert not (tmp_path / "project" / ".codex" / "skills" / "smart-search-cli").exists()
    assert not (tmp_path / "project" / ".hermes" / "skills" / "smart-search-cli").exists()


def test_setup_skip_skills_writes_no_skill_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--skip-skills",
        "--install-skills",
        "codex",
        "--skills-root",
        str(tmp_path),
    ])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert "skills" not in data
    assert not (tmp_path / ".codex" / "skills" / "smart-search-cli").exists()


def test_setup_unknown_skill_target_returns_parameter_error(monkeypatch, capsys):
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main(["setup", "--non-interactive", "--install-skills", "unknown"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert data["error_type"] == "parameter_error"
    assert "Unknown skill target" in data["error"]


def test_setup_guided_installs_tui_selected_skill_targets(monkeypatch, tmp_path, capsys):
    saved = {}
    answers = iter(["skip", "skip", "skip", "n"])
    checkbox_calls = []

    def fake_checkbox(message, choices):
        checkbox_calls.append((message, choices))
        if "AI tools" in message:
            return ["codex", "cursor"]
        return []

    monkeypatch.setattr(cli, "_checkbox_with_tui", fake_checkbox)
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--lang", "en", "--skills-root", str(tmp_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert data["skills"]["installed_count"] == 2
    assert (tmp_path / ".codex" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    skill_choices = next(choices for message, choices in checkbox_calls if "AI tools" in message)
    skill_choice_names = [choice["name"] for choice in skill_choices]
    assert "Codex (~/.codex/skills)" in skill_choice_names
    assert "Cursor (~/.cursor/skills)" in skill_choice_names
    assert not any("project/" in name for name in skill_choice_names)
    assert "Install the smart-search-cli skill" in captured.err
    assert "user-level AI tools" in captured.err
    assert "Skill install result" in captured.err


def test_setup_banner_falls_back_when_pyfiglet_unavailable(monkeypatch, capsys):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "pyfiglet":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    cli._write_setup_banner("en")
    captured = capsys.readouterr()

    assert "Smart Search" in captured.err
    assert "CLI-first multi-source search" in captured.err


def test_skill_installer_parse_aliases_and_all(tmp_path):
    assert skill_installer.parse_skill_targets("claude-code,github-copilot,agentskills,hermes-agent") == [
        "claude",
        "copilot",
        "codex",
        "hermes",
    ]
    assert len(skill_installer.parse_skill_targets("all")) == len(skill_installer.SKILL_TARGETS)

    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: smart-search-cli\n---\n", encoding="utf-8")
    result = skill_installer.install_skill_targets(
        ["codex"],
        project_root=tmp_path / "project",
        source_root=source,
    )

    assert result["ok"] is True
    assert result["installed_count"] == 1
    assert (tmp_path / "project" / ".codex" / "skills" / "smart-search-cli" / "SKILL.md").is_file()


def test_skill_installer_pi_target_uses_agent_skill_root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: smart-search-cli\n---\n", encoding="utf-8")

    result = skill_installer.install_skill_targets(
        ["pi"],
        project_root=tmp_path / "project",
        source_root=source,
    )

    assert result["ok"] is True
    assert result["installed_count"] == 1
    assert Path(result["installed"][0]["path"]).as_posix().endswith(".pi/agent/skills/smart-search-cli")
    assert (tmp_path / "project" / ".pi" / "agent" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert not (tmp_path / "project" / ".pi" / "skills" / "smart-search-cli").exists()


def test_skill_installer_status_detects_stale_and_extra_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("new", encoding="utf-8")
    root = tmp_path / "project"
    dest = root / ".codex" / "skills" / "smart-search-cli"
    dest.mkdir(parents=True)

    (dest / "SKILL.md").write_text("old", encoding="utf-8")
    stale = skill_installer.status_skill_targets(["codex"], project_root=root, source_root=source)
    assert stale["targets"][0]["status"] == "stale"
    assert stale["targets"][0]["stale_files"] == ["SKILL.md"]

    (dest / "SKILL.md").write_text("new", encoding="utf-8")
    (dest / "OLD.md").write_text("old leftover", encoding="utf-8")
    extra = skill_installer.status_skill_targets(["codex"], project_root=root, source_root=source)
    assert extra["targets"][0]["status"] == "extra_files"
    assert extra["targets"][0]["extra_files"] == ["OLD.md"]
    assert extra["targets"][0]["managed_hash_match"] is True
    assert extra["targets"][0]["hash_match"] is False


def test_tavily_url_normalization_cases():
    cases = {
        "pool.example.com": "https://pool.example.com/api/tavily",
        "https://pool.example.com": "https://pool.example.com/api/tavily",
        "https://pool.example.com/mcp": "https://pool.example.com/api/tavily",
        "https://pool.example.com/api/tavily": "https://pool.example.com/api/tavily",
        "https://api.tavily.com": "https://api.tavily.com",
    }

    for raw, expected in cases.items():
        assert cli._normalize_tavily_api_url(raw) == expected
    assert cli._normalize_tavily_api_url("https://custom.example.com", hikari=False) == "https://custom.example.com"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com", "tvly-key") == "https://custom.example.com"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com/mcp", "tvly-key") == "https://custom.example.com/api/tavily"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com", "th-key") == "https://custom.example.com/api/tavily"


def test_tavily_hikari_key_recommends_hikari_endpoint(monkeypatch):
    values = {"TAVILY_API_KEY": "th-test-secret"}
    seen = {}

    def fake_prompt_select(message, choices, default):
        seen["default"] = default
        return "hikari"

    monkeypatch.setattr(cli, "_prompt_select", fake_prompt_select)
    monkeypatch.setattr(cli, "_prompt_value", lambda *args, **kwargs: "https://pool.example.com/mcp")

    cli._prompt_tavily_api_url(values, {}, "en")

    assert seen["default"] == "hikari"
    assert values["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"


def test_tavily_hikari_prompt_shows_beginner_url_example(monkeypatch, capsys):
    values = {"TAVILY_API_KEY": "th-test-secret"}

    monkeypatch.setattr(cli, "_prompt_select", lambda message, choices, default: "hikari")
    monkeypatch.setattr(cli, "_prompt_value", lambda *args, **kwargs: "https://pool.example.com")

    cli._prompt_tavily_api_url(values, {}, "zh")
    captured = capsys.readouterr()

    assert values["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"
    assert "例如 https://pool.example.com" in captured.err
    assert "api/tavily" in captured.err


def test_zhipu_prompt_saves_official_api_url_and_search_engine(monkeypatch):
    values = {}
    selections = iter(["official", "search_pro_sogou"])

    monkeypatch.setattr(cli, "_prompt_select", lambda message, choices, default: next(selections))

    cli._prompt_zhipu_api_url(values, {}, "zh")
    cli._prompt_zhipu_search_engine(values, {}, "zh")

    assert values["ZHIPU_API_URL"] == "https://open.bigmodel.cn/api"
    assert values["ZHIPU_SEARCH_ENGINE"] == "search_pro_sogou"


def test_zhipu_prompt_allows_custom_search_engine(monkeypatch):
    values = {}
    selections = iter(["custom"])

    monkeypatch.setattr(cli, "_prompt_select", lambda message, choices, default: next(selections))
    monkeypatch.setattr(cli, "_prompt_value", lambda *args, **kwargs: "search_future")

    cli._prompt_zhipu_search_engine(values, {}, "en")

    assert values["ZHIPU_SEARCH_ENGINE"] == "search_future"


def test_setup_guided_zh_groups_minimum_capabilities(monkeypatch, capsys):
    saved = {}
    answers = iter(["xai", "", "context7", "tavily", "", "n", "n"])
    secrets = iter(["xai-test-secret", "context7-test-secret", "tavily-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "zh"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {
        "XAI_API_KEY": "xai-test-secret",
        "CONTEXT7_API_KEY": "context7-test-secret",
        "TAVILY_API_URL": "https://api.tavily.com",
        "TAVILY_API_KEY": "tavily-test-secret",
    }
    assert data["minimum_profile_ok"] is True
    assert data["minimum_profile_missing"] == []
    assert captured.out.lstrip().startswith("{")
    assert "Smart Search" in captured.err
    assert "不知道怎么填" in captured.err
    assert "main_search + docs_search + web_fetch" in captured.err
    assert "[1/3" in captured.err
    assert "main_search" in captured.err
    assert "pool.example.com" not in captured.out
    assert "xai-test-secret" not in captured.err
    assert "xai-test-secret" not in captured.out


def test_setup_guided_zhipu_optional_reinforcement_saves_url_and_engine(monkeypatch, capsys):
    saved = {}
    answers = iter(["skip", "skip", "skip", "zhipu", "official", "search_pro_quark", "n"])
    secrets = iter(["zhipu-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "zh"])
    captured = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert saved["ZHIPU_API_KEY"] == "zhipu-test-secret"
    assert saved["ZHIPU_API_URL"] == "https://open.bigmodel.cn/api"
    assert saved["ZHIPU_SEARCH_ENGINE"] == "search_pro_quark"
    assert "智谱搜索服务" in captured.err
    assert "zhipu-test-secret" not in captured.out
    assert "zhipu-test-secret" not in captured.err


def test_setup_guided_uses_tui_defaults_for_configured_providers(monkeypatch, capsys):
    current = {
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-old-secret",
        "CONTEXT7_API_KEY": "ctx-old-secret",
        "FIRECRAWL_API_KEY": "firecrawl-old-secret",
        "FIRECRAWL_API_URL": "https://firecrawl.example.com/v2",
    }
    saved = {}
    checkbox_calls = []

    def fake_checkbox(message, choices):
        selected = [choice["value"] for choice in choices if choice.get("enabled")]
        checkbox_calls.append((message, selected))
        return selected

    monkeypatch.setattr(cli, "_checkbox_with_tui", fake_checkbox)
    monkeypatch.setattr(cli, "_select_with_tui", lambda message, choices, default=None: default)
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": {**current, **saved}})
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert data["minimum_profile_ok"] is True
    assert saved == {}
    assert "https://relay.example.com/v1" not in captured.err
    assert "https://firecrawl.example.com/v2" not in captured.err
    assert "configured" in captured.err
    assert checkbox_calls[:3] == [
        ("Choose main_search providers", ["openai-compatible"]),
        ("Choose docs_search providers", ["context7"]),
        ("Choose web_fetch providers", ["firecrawl"]),
    ]


def test_setup_guided_en_reports_missing_minimum(monkeypatch, capsys):
    saved = {}
    answers = iter(["skip", "skip", "skip", "n", "n"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {}
    assert data["minimum_profile_ok"] is False
    assert data["minimum_profile_missing"] == ["main_search", "docs_search", "web_fetch"]
    assert "Smart Search setup wizard" in captured.err
    assert "If unsure" in captured.err
    assert "main_search + docs_search + web_fetch" in captured.err
    assert "[MISSING] main_search primary search" in captured.err
    assert "will fail closed" in captured.err
    assert "your-relay.example.com" not in captured.out


def test_setup_guided_masks_configured_url_defaults(monkeypatch, capsys):
    current = {
        "OPENAI_COMPATIBLE_API_URL": "https://private-relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-old-secret",
    }
    answers = iter(["openai", "", "", "", "skip", "skip", "n", "n"])
    secrets = iter([""])

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": current.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert "https://private-relay.example.com/v1" not in captured.err
    assert "configured, press Enter to keep" in captured.err


def test_setup_guided_main_search_can_save_openai_compatible_peer(monkeypatch, capsys):
    saved = {}
    answers = iter(["openai", "https://relay.example.com/v1", "", "", "skip", "skip", "n", "n"])
    secrets = iter(["relay-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-test-secret",
    }
    assert data["capability_status"]["main_search"]["configured"] == ["openai-compatible"]
    assert data["minimum_profile_missing"] == ["docs_search", "web_fetch"]
    assert "relay-test-secret" not in captured.out
    assert "relay-test-secret" not in captured.err


def test_setup_guided_main_search_can_save_both_peer_providers(monkeypatch, capsys):
    saved = {}
    answers = iter(["both", "", "https://relay.example.com/v1", "", "", "skip", "skip", "n", "n"])
    secrets = iter(["xai-test-secret", "relay-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert saved == {
        "XAI_API_KEY": "xai-test-secret",
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-test-secret",
    }
    assert data["capability_status"]["main_search"]["configured"] == ["xai-responses", "openai-compatible"]
    assert data["capability_status"]["main_search"]["fallback_chain"] == ["xai-responses", "openai-compatible"]


def test_setup_interactive_language_prompt(monkeypatch, capsys):
    saved = {}
    answers = iter(["en", "skip", "skip", "skip", "n", "n"])

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--skip-skills"])
    captured = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert "Smart Search setup wizard" in captured.err


def test_search_passes_routing_options(monkeypatch, capsys):
    captured = {}

    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        captured.update({"validation": validation, "fallback": fallback, "providers": providers})
        return {"ok": True, "content": "Answer", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main([
        "search",
        "query",
        "--validation",
        "strict",
        "--fallback",
        "off",
        "--providers",
        "grok,zhipu",
    ])

    assert code == cli.EXIT_OK
    assert captured == {"validation": "strict", "fallback": "off", "providers": "grok,zhipu"}
    assert json.loads(capsys.readouterr().out)["content"] == "Answer"


def test_smoke_command_uses_service(monkeypatch, capsys):
    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    async def fake_research(*args, **kwargs):
        return {"ok": True, "query_mode": "research", "content": "Research"}

    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    code = cli.main(["smoke", "--mode", "mock"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"


def test_anysearch_commands_use_service_wrappers(monkeypatch, capsys):
    calls = []

    async def fake_domains(domain=""):
        calls.append(("domains", domain))
        return {"ok": True, "provider": "anysearch", "tool": "list_domains", "results": []}

    async def fake_search(query, domain="", sub_domain="", max_results=5):
        calls.append(("search", query, domain, sub_domain, max_results))
        return {"ok": True, "provider": "anysearch", "tool": "search", "query": query, "results": []}

    async def fake_extract(url, max_length=20000):
        calls.append(("extract", url, max_length))
        return {"ok": True, "provider": "anysearch", "tool": "extract", "url": url, "content": "# Page"}

    async def fake_batch(queries, max_results=3):
        calls.append(("batch", queries, max_results))
        return {"ok": True, "provider": "anysearch", "tool": "batch_search", "results": []}

    monkeypatch.setattr(cli.service, "anysearch_domains", fake_domains)
    monkeypatch.setattr(cli.service, "anysearch_search", fake_search)
    monkeypatch.setattr(cli.service, "anysearch_extract", fake_extract)
    monkeypatch.setattr(cli.service, "anysearch_batch", fake_batch)

    assert cli.main(["anysearch-domains", "security"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "list_domains"
    assert cli.main(["as", "CVE-2024-3094", "--domain", "security.cve", "--sub-domain", "xz", "--max-results", "2"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["query"] == "CVE-2024-3094"
    assert cli.main(["as-extract", "https://example.com", "--max-length", "123"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["url"] == "https://example.com"
    assert cli.main(["as-batch", "a", "b", "--max-results", "1"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "batch_search"

    assert calls == [
        ("domains", "security"),
        ("search", "CVE-2024-3094", "security.cve", "xz", 2),
        ("extract", "https://example.com", 123),
        ("batch", ["a", "b"], 1),
    ]


def test_zhipu_mcp_commands_use_service_wrappers(monkeypatch, capsys):
    calls = []

    async def fake_search(query, count=5):
        calls.append(("search", query, count))
        return {"ok": True, "provider": "zhipu-mcp", "tool": "web_search_prime", "results": []}

    async def fake_reader(url):
        calls.append(("reader", url))
        return {"ok": True, "provider": "zhipu-mcp-reader", "tool": "webReader", "content": "# Page"}

    async def fake_search_doc(repo, query, max_results=5):
        calls.append(("search_doc", repo, query, max_results))
        return {"ok": True, "provider": "zhipu-mcp-zread", "tool": "search_doc", "results": []}

    async def fake_repo_structure(repo, ref=""):
        calls.append(("repo_structure", repo, ref))
        return {"ok": True, "provider": "zhipu-mcp-zread", "tool": "get_repo_structure", "content": "tree"}

    async def fake_read_file(repo, path, ref=""):
        calls.append(("read_file", repo, path, ref))
        return {"ok": True, "provider": "zhipu-mcp-zread", "tool": "read_file", "content": "file"}

    monkeypatch.setattr(cli.service, "zhipu_mcp_search", fake_search)
    monkeypatch.setattr(cli.service, "zhipu_mcp_reader", fake_reader)
    monkeypatch.setattr(cli.service, "zhipu_mcp_search_doc", fake_search_doc)
    monkeypatch.setattr(cli.service, "zhipu_mcp_repo_structure", fake_repo_structure)
    monkeypatch.setattr(cli.service, "zhipu_mcp_read_file", fake_read_file)

    assert cli.main(["zhipu-mcp-search", "news", "--count", "2"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "web_search_prime"
    assert cli.main(["zmcp-reader", "https://example.com"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "webReader"
    assert cli.main(["zmcp-doc", "owner/repo", "install", "--max-results", "3"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "search_doc"
    assert cli.main(["zmcp-tree", "owner/repo", "--ref", "main"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "get_repo_structure"
    assert cli.main(["zmcp-file", "owner/repo", "README.md", "--ref", "main"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "read_file"

    assert calls == [
        ("search", "news", 2),
        ("reader", "https://example.com"),
        ("search_doc", "owner/repo", "install", 3),
        ("repo_structure", "owner/repo", "main"),
        ("read_file", "owner/repo", "README.md", "main"),
    ]


def test_provider_and_smoke_aliases_use_canonical_commands(monkeypatch, capsys):
    async def fake_exa_search(*args, **kwargs):
        return {"ok": True, "provider": "exa"}

    async def fake_zhipu_search(*args, **kwargs):
        return {"ok": True, "provider": "zhipu"}

    async def fake_context7_library(*args, **kwargs):
        return {"ok": True, "provider": "context7-library"}

    async def fake_context7_docs(*args, **kwargs):
        return {"ok": True, "provider": "context7-docs"}

    async def fake_anysearch_domains(*args, **kwargs):
        return {"ok": True, "provider": "anysearch", "tool": "list_domains"}

    async def fake_anysearch_search(*args, **kwargs):
        return {"ok": True, "provider": "anysearch", "tool": "search"}

    async def fake_anysearch_extract(*args, **kwargs):
        return {"ok": True, "provider": "anysearch", "tool": "extract"}

    async def fake_anysearch_batch(*args, **kwargs):
        return {"ok": True, "provider": "anysearch", "tool": "batch_search"}

    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    async def fake_research(*args, **kwargs):
        return {"ok": True, "query_mode": "research", "content": "Research"}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)
    monkeypatch.setattr(cli.service, "zhipu_search", fake_zhipu_search)
    monkeypatch.setattr(cli.service, "context7_library", fake_context7_library)
    monkeypatch.setattr(cli.service, "context7_docs", fake_context7_docs)
    monkeypatch.setattr(cli.service, "anysearch_domains", fake_anysearch_domains)
    monkeypatch.setattr(cli.service, "anysearch_search", fake_anysearch_search)
    monkeypatch.setattr(cli.service, "anysearch_extract", fake_anysearch_extract)
    monkeypatch.setattr(cli.service, "anysearch_batch", fake_anysearch_batch)
    monkeypatch.setattr(cli.service, "smoke", fake_smoke)
    monkeypatch.setattr(cli.service, "research", fake_research)

    assert cli.main(["exa", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "exa"
    assert cli.main(["z", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "zhipu"
    assert cli.main(["as-domains"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "list_domains"
    assert cli.main(["as-search", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "search"
    assert cli.main(["as-extract", "https://example.com"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "extract"
    assert cli.main(["as-batch", "a", "b"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["tool"] == "batch_search"
    assert cli.main(["c7", "react"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "context7-library"
    assert cli.main(["c7docs", "/facebook/react", "hooks"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "context7-docs"
    assert cli.main(["rs", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["query_mode"] == "research"
    assert cli.main(["sm"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"


def test_smoke_command_accepts_mock_and_live_flags(monkeypatch, capsys):
    captured = []

    async def fake_smoke(mode="mock"):
        captured.append(mode)
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    assert cli.main(["smoke", "--mock"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"
    assert cli.main(["smoke", "--live"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "live"
    assert captured == ["mock", "live"]


def test_setup_interactive_does_not_print_current_secret(monkeypatch, capsys):
    prompts = []

    def fake_config_set(key, value):
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    def fake_getpass(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(
        cli.service,
        "config_list",
        lambda show_secrets=False: {
            "ok": True,
            "values": {
                "XAI_API_KEY": "xai-test-secret",
                "XAI_MODEL": "test-model",
                "EXA_API_KEY": "exa-test-secret",
            },
        },
    )
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)

    code = cli.main(["setup", "--advanced", "--lang", "en"])
    captured = capsys.readouterr()
    prompt_text = "\n".join(prompts)

    assert code == cli.EXIT_OK
    assert "xai-test-secret" not in captured.out
    assert "xai-test-secret" not in captured.err
    assert "xai-test-secret" not in prompt_text
    assert "exa-test-secret" not in prompt_text
    assert "xAI API key optional [configured, press Enter to keep]" in prompt_text


def test_setup_advanced_mode_keeps_low_level_prompts(monkeypatch, capsys):
    prompts = []
    saved = {}

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    def fake_getpass(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(
        cli.service,
        "config_list",
        lambda show_secrets=False: {"ok": True, "values": {"XAI_API_URL": "https://api.x.ai/v1"}},
    )
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)

    code = cli.main(["setup", "--advanced", "--lang", "en"])

    assert code == cli.EXIT_OK
    captured = capsys.readouterr()
    assert "Legacy primary API URL optional" not in captured.err
    assert "xAI Responses API URL optional" in captured.err
    assert "OpenAI-compatible API URL optional" in captured.err
    assert "Zhipu Web Search API URL optional" in captured.err
    assert "Zhipu search service" in captured.err
    assert "Advanced mode" in captured.err


def test_regression_invokes_pytest(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    code = cli.main(["regression"])

    assert code == 0
    assert "-m" in captured["cmd"]
    assert "pytest" in captured["cmd"]
    assert "tests/test_cli.py" in captured["cmd"]
    assert "tests/test_smoke.py" in captured["cmd"]
    assert "tests/test_release_workflow.py" in captured["cmd"]


def test_regression_alias_invokes_pytest(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    code = cli.main(["reg"])

    assert code == 0
    assert "pytest" in captured["cmd"]


def test_regression_uses_mock_smoke_when_packaged_tests_missing(monkeypatch, capsys):
    class MissingPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, other):
            return MissingPath(f"{self.value}/{other}")

        @property
        def parents(self):
            return [self, self, self]

        def exists(self):
            return False

        def read_text(self, encoding="utf-8"):
            return '{"version": "0.1.test"}'

        def __str__(self):
            return self.value

    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    def should_not_call_pytest(cmd, cwd):
        raise AssertionError("packaged regression fallback should not require pytest")

    monkeypatch.setattr(cli.Path, "resolve", lambda self: MissingPath("pkg/src/smart_search/cli.py"))
    monkeypatch.setattr(cli.subprocess, "call", should_not_call_pytest)
    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    code = cli.main(["regression"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "Packaged install has no test files" in captured.err
    assert json.loads(captured.out)["mode"] == "mock"
