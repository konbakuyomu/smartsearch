import argparse
import asyncio
import contextlib
import getpass
import json
from importlib import metadata
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import service
from .skill_installer import (
    DEFAULT_SKILL_TARGET_IDS,
    SKILL_TARGETS,
    SkillInstallError,
    install_skill_targets,
    parse_skill_targets,
    status_skill_targets,
)


EXIT_OK = 0
EXIT_PARAMETER_ERROR = 2
EXIT_CONFIG_ERROR = 3
EXIT_NETWORK_ERROR = 4
EXIT_RUNTIME_ERROR = 5

COMMAND_ALIASES = {
    "search": ["s"],
    "fetch": ["f"],
    "map": ["m"],
    "exa-search": ["exa", "x"],
    "exa-similar": ["xs"],
    "zhipu-search": ["z", "zp"],
    "zhipu-mcp-search": ["zmcp-search"],
    "zhipu-mcp-reader": ["zmcp-reader"],
    "zhipu-mcp-search-doc": ["zmcp-doc"],
    "zhipu-mcp-repo-structure": ["zmcp-tree"],
    "zhipu-mcp-read-file": ["zmcp-file"],
    "anysearch-domains": ["as-domains"],
    "anysearch-search": ["as-search", "as"],
    "anysearch-extract": ["as-extract"],
    "anysearch-batch": ["as-batch"],
    "context7-library": ["c7", "ctx7"],
    "context7-docs": ["c7d", "c7docs", "ctx7-docs"],
    "deep": ["dr"],
    "research": ["rs"],
    "smoke": ["sm"],
    "doctor": ["d"],
    "diagnose": ["diag"],
    "model": ["mdl"],
    "setup": ["init"],
    "skills": ["skill"],
    "config": ["cfg"],
    "regression": ["reg"],
}

CONFIG_COMMAND_ALIASES = {
    "path": ["p"],
    "list": ["ls", "l"],
    "set": ["s"],
    "unset": ["rm", "u"],
}

MODEL_COMMAND_ALIASES = {
    "set": ["s"],
    "current": ["cur", "c"],
}

SKILLS_COMMAND_ALIASES = {
    "status": ["st"],
    "update": ["up"],
}


class SmartSearchArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


TAVILY_DEFAULT_API_URL = "https://api.tavily.com"
FIRECRAWL_DEFAULT_API_URL = "https://api.firecrawl.dev/v2"
ZHIPU_DEFAULT_API_URL = "https://open.bigmodel.cn/api"
ZHIPU_SEARCH_ENGINE_CHOICES = [
    "search_std",
    "search_pro",
    "search_pro_sogou",
    "search_pro_quark",
]

_STATIC_SMART_SEARCH_BANNER = r"""
 ____                       _     ____                      _
/ ___| _ __ ___   __ _ _ __| |_  / ___|  ___  __ _ _ __ ___| |__
\___ \| '_ ` _ \ / _` | '__| __| \___ \ / _ \/ _` | '__/ __| '_ \
 ___) | | | | | | (_| | |  | |_   ___) |  __/ (_| | | | (__| | | |
|____/|_| |_| |_|\__,_|_|   \__| |____/ \___|\__,_|_|  \___|_| |_|
""".strip("\n")


def _get_version() -> str:
    root = Path(__file__).resolve().parents[2]
    package_json = root / "package.json"
    try:
        version = json.loads(package_json.read_text(encoding="utf-8")).get("version", "")
        if version:
            return str(version)
    except (OSError, json.JSONDecodeError):
        pass

    pyproject = root / "pyproject.toml"
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass

    try:
        return metadata.version("smart-search")
    except metadata.PackageNotFoundError:
        pass

    return "unknown"


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _json_stdout_safe(data: Any) -> str:
    text = _json(data)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    errors = getattr(sys.stdout, "errors", None) or "strict"
    try:
        text.encode(encoding, errors=errors)
        return text
    except UnicodeEncodeError:
        return "".join(_escape_unencodable_json_char(char, encoding) for char in text)


def _escape_unencodable_json_char(char: str, encoding: str) -> str:
    try:
        char.encode(encoding)
        return char
    except UnicodeEncodeError:
        return json.dumps(char, ensure_ascii=True)[1:-1]


def _format_seconds(seconds: float) -> str:
    return f"{seconds:g}"


def _search_timeout_result(query: str, timeout: float, search_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    seconds = _format_seconds(timeout)
    search_kwargs = search_kwargs or {}
    stream = search_kwargs.get("stream")
    if stream is None:
        stream = service.config.openai_compatible_stream
    model = search_kwargs.get("model") or service.config.openai_compatible_model
    return {
        "ok": False,
        "error_type": "network_error",
        "error": f"Search timed out after {seconds} seconds",
        "query": query,
        "content": "",
        "sources": [],
        "sources_count": 0,
        "primary_sources": [],
        "primary_sources_count": 0,
        "extra_sources": [],
        "extra_sources_count": 0,
        "source_warning": "",
        "routing_decision": {},
        "providers_used": [],
        "provider_attempts": [],
        "fallback_used": False,
        "validation_level": "",
        "timeout_seconds": timeout,
        "provider": search_kwargs.get("providers", "auto"),
        "model": model,
        "stream": stream,
        "diagnose_command": "smart-search diagnose openai-compatible --format markdown",
        "recommendation": "Run `smart-search diagnose openai-compatible --format markdown` to check whether OpenAI-compatible stream/no-stream search requests are hanging upstream.",
    }


def _one_line(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if limit > 0 and len(text) > limit:
        return text[: max(0, limit - 3)].rstrip() + "..."
    return text


def _md_cell(value: Any) -> str:
    return _one_line(value).replace("|", r"\|")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return []
    lines = [
        "| " + " | ".join(_md_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = list(row)[: len(headers)]
        cells.extend([""] * (len(headers) - len(cells)))
        lines.append("| " + " | ".join(_md_cell(cell) for cell in cells) + " |")
    return lines


def _markdown_code_block(value: Any) -> list[str]:
    text = "" if value is None else str(value)
    fence = "```"
    if fence in text:
        text = text.replace(fence, "` ` `")
    return ["```text", text, "```"]


def _status_label(value: Any) -> str:
    if isinstance(value, bool):
        return "OK" if value else "FAIL"
    status = str(value or "").strip()
    normalized = status.lower()
    labels = {
        "ok": "OK",
        "true": "OK",
        "configured": "CONFIGURED",
        "warning": "WARN",
        "timeout": "TIMEOUT",
        "error": "ERROR",
        "config_error": "CONFIG ERROR",
        "not_configured": "NOT CONFIGURED",
        "false": "FAIL",
        "failed": "FAIL",
        "empty": "EMPTY",
        "skipped": "SKIPPED",
    }
    return labels.get(normalized, status.upper() if status else "-")


def _yes_no(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def _latency_text(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.2f} ms"
    return str(value)


def _configured_text(items: Any) -> str:
    if isinstance(items, (list, tuple)):
        return ", ".join(str(item) for item in items) if items else "-"
    return str(items) if items else "-"


def _error_lines(data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if data.get("error_type") or data.get("error"):
        lines.extend(["", "## Errors"])
        if data.get("error_type"):
            lines.append(f"- Type: `{data.get('error_type')}`")
        if data.get("error"):
            lines.append(f"- Message: {data.get('error')}")
    parameter_errors = data.get("config_parameter_errors") or []
    for error in parameter_errors:
        lines.append(f"- Config: {error}")
    return lines


def _error_summary(data: dict[str, Any]) -> str:
    error_type = data.get("error_type")
    error = data.get("error")
    if error_type and error:
        return f"{error_type}: {error}"
    if error:
        return str(error)
    if error_type:
        return str(error_type)
    return ""


def _result_title(item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"Result {index}"
    return (
        item.get("title")
        or item.get("id")
        or item.get("library_id")
        or item.get("url")
        or item.get("provider")
        or f"Result {index}"
    )


def _result_target(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    return item.get("url") or item.get("id") or item.get("library_id") or ""


def _result_summary(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    highlights = item.get("highlights")
    if isinstance(highlights, list):
        highlights = " ".join(str(part) for part in highlights[:2])
    return (
        item.get("description")
        or item.get("content")
        or item.get("snippet")
        or item.get("text")
        or highlights
        or item.get("source")
        or ""
    )


def _result_rows(results: list[Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for index, item in enumerate(results, 1):
        rows.append([index, _result_title(item, index), _result_target(item), _result_summary(item)])
    return rows


def _format_result_markdown(command: str, data: dict[str, Any], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Status: {_status_label(data.get('ok'))}",
    ]
    if data.get("query"):
        lines.append(f"Query: `{data.get('query')}`")
    if data.get("url"):
        lines.append(f"URL: {data.get('url')}")
    if data.get("base_url"):
        lines.append(f"Base URL: {data.get('base_url')}")
    if data.get("provider"):
        lines.append(f"Provider: {data.get('provider')}")
    if data.get("tool"):
        lines.append(f"Tool: `{data.get('tool')}`")
    if data.get("elapsed_ms") is not None:
        lines.append(f"Elapsed: {_latency_text(data.get('elapsed_ms'))}")

    results = data.get("results") or []
    lines.append("")
    if results:
        lines.append("## Results")
        lines.extend(_markdown_table(["#", "Title", "URL / ID", "Summary"], _result_rows(results)))
    elif data.get("content"):
        lines.append("## Content")
        lines.extend(_markdown_code_block(data.get("content")))
    elif data.get("ok"):
        lines.append("No results.")
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_doctor_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Smart Search Doctor",
        "",
        f"Overall: {_status_label(data.get('ok'))}",
        f"Config file: `{data.get('config_file', '')}`",
        f"Config dir: `{data.get('config_dir', '')}`",
        f"Config dir source: `{data.get('config_dir_source', '-')}`",
        f"Default config file: `{data.get('default_config_file', '')}`",
        f"Config status: {data.get('config_status', '-')}",
        f"Minimum profile: {_status_label(data.get('minimum_profile_ok'))}",
        f"Log dir config value: `{data.get('log_dir_config_value', data.get('SMART_SEARCH_LOG_DIR', ''))}`",
        f"Resolved log dir: `{data.get('resolved_log_dir', '')}`",
        f"File logging enabled: {_yes_no(data.get('file_logging_enabled'))}",
    ]
    if data.get("legacy_windows_config_file"):
        lines.append(f"Legacy Windows config file: `{data.get('legacy_windows_config_file')}`")
        lines.append(f"Legacy Windows config exists: {_status_label(data.get('legacy_windows_config_exists'))}")
    if data.get("config_dir_override_value"):
        lines.append(f"SMART_SEARCH_CONFIG_DIR: `{data.get('config_dir_override_value')}`")
        lines.append(f"Override matches default: {_yes_no(data.get('config_dir_override_matches_default'))}")
        if data.get("config_dir_source") == "environment" and data.get("config_dir_override_matches_default"):
            lines.append(
                "The active config path comes from `SMART_SEARCH_CONFIG_DIR`, but that override matches the current Windows default path."
            )
    if data.get("config_dir_source") == "legacy_windows_home":
        lines.append(
            "Active config is using the old Windows `~\\.config\\smart-search` location because the new default file does not exist."
        )
    missing = data.get("minimum_profile_missing") or []
    if missing:
        lines.append(f"Missing: `{', '.join(str(item) for item in missing)}`")

    config_sources = data.get("config_sources") or {}
    if config_sources:
        rows = []
        for key in sorted(config_sources):
            rows.append([key, config_sources.get(key), data.get(key, "-")])
        lines.extend(["", "## Configuration Values"])
        lines.extend(_markdown_table(["Key", "Source", "Value"], rows))

    capability_status = data.get("capability_status") or {}
    if capability_status:
        rows = []
        for capability, status in capability_status.items():
            if isinstance(status, dict):
                rows.append(
                    [
                        capability,
                        _status_label(status.get("ok")),
                        _configured_text(status.get("configured")),
                        _configured_text(status.get("fallback_chain")),
                    ]
                )
        if rows:
            lines.extend(["", "## Capabilities"])
            lines.extend(_markdown_table(["Capability", "Status", "Configured", "Fallback chain"], rows))

    main_tests = data.get("main_search_connection_tests") or {}
    if main_tests:
        rows = []
        for provider, test in main_tests.items():
            if isinstance(test, dict):
                rows.append(
                    [
                        provider,
                        _status_label(test.get("status")),
                        _latency_text(test.get("response_time_ms")),
                        test.get("message", ""),
                    ]
                )
        lines.extend(["", "## Main Search Providers"])
        lines.extend(_markdown_table(["Provider", "Status", "Latency", "Message"], rows))
        lines.extend(_provider_detail_lines("Provider Details", main_tests))

    provider_tests = [
        ("exa", data.get("exa_connection_test") or {}),
        ("tavily", data.get("tavily_connection_test") or {}),
        ("jina", data.get("jina_connection_test") or {}),
        ("firecrawl", data.get("firecrawl_connection_test") or {}),
        ("zhipu", data.get("zhipu_connection_test") or {}),
        ("zhipu-mcp", data.get("zhipu_mcp_connection_test") or {}),
        ("context7", data.get("context7_connection_test") or {}),
    ]
    rows = []
    for provider, test in provider_tests:
        if isinstance(test, dict) and test:
            rows.append(
                [
                    provider,
                    _status_label(test.get("status")),
                    _latency_text(test.get("response_time_ms")),
                    test.get("message", ""),
                ]
            )
    if rows:
        lines.extend(["", "## Provider Checks"])
        lines.extend(_markdown_table(["Provider", "Status", "Latency", "Message"], rows))
        lines.extend(_provider_detail_lines("Provider Check Details", dict(provider_tests)))

    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _provider_detail_lines(title: str, provider_tests: dict[str, Any]) -> list[str]:
    details: list[str] = []
    for provider, test in provider_tests.items():
        if not isinstance(test, dict) or not test:
            continue
        message = test.get("message")
        available_models = test.get("available_models") or []
        nested_checks = [
            ("models_endpoint_test", test.get("models_endpoint_test")),
            ("chat_completion_test", test.get("chat_completion_test")),
        ]
        if not message and not available_models and not any(isinstance(item, dict) for _, item in nested_checks):
            continue
        details.extend(
            [
                "",
                f"### {provider}",
                "",
                f"- Status: {_status_label(test.get('status'))}",
                f"- Latency: {_latency_text(test.get('response_time_ms'))}",
            ]
        )
        if message:
            details.extend(["- Message:"])
            details.extend(_markdown_code_block(message))
        if available_models:
            details.append("- Available models: `" + "`, `".join(str(model) for model in available_models) + "`")
        for name, nested in nested_checks:
            if not isinstance(nested, dict):
                continue
            details.extend(
                [
                    f"- {name}: {_status_label(nested.get('status'))}, {_latency_text(nested.get('response_time_ms'))}",
                ]
            )
            if nested.get("message"):
                details.extend(_markdown_code_block(nested.get("message")))
    if not details:
        return []
    return ["", f"## {title}", *details]


def _format_smoke_markdown(data: dict[str, Any]) -> str:
    cases = data.get("cases") or []
    failed = data.get("failed_cases") or []
    degraded = data.get("degraded_cases") or []
    lines = [
        "# Smart Search Smoke",
        "",
        f"Mode: `{data.get('mode', '')}`",
        f"Overall: {_status_label(data.get('ok'))}",
        f"Cases: {len(cases)} total, {len(failed)} failed, {len(degraded)} degraded",
    ]
    if cases:
        rows = []
        for case in cases:
            rows.append(
                [
                    case.get("name", ""),
                    _status_label(case.get("ok")),
                    case.get("severity", ""),
                    case.get("error") or case.get("error_type") or case.get("skipped", ""),
                ]
            )
        lines.extend(["", "## Cases"])
        lines.extend(_markdown_table(["Case", "Status", "Severity", "Details"], rows))
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_diagnose_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Smart Search Diagnose",
        "",
        f"Provider: `{data.get('provider', '')}`",
        f"Status: {_status_label(data.get('ok'))}",
        f"Summary: {data.get('summary', '-')}",
        f"Recommendation: {data.get('recommendation', '-')}",
        f"Config file: `{data.get('config_file', '')}`",
        f"Config dir source: `{data.get('config_dir_source', '-')}`",
        f"API URL: `{data.get('api_url', '')}`",
        f"API key: `{data.get('api_key', '')}`",
        f"Model: `{data.get('model', '')}`",
        f"Configured stream: {_yes_no(data.get('configured_stream'))}",
        f"Timeout: {_format_seconds(float(data.get('timeout_seconds', 0) or 0))} seconds",
    ]
    checks = data.get("checks") or []
    if checks:
        rows = []
        for check in checks:
            rows.append(
                [
                    check.get("name", ""),
                    _status_label(check.get("status")),
                    _latency_text(check.get("response_time_ms")),
                    check.get("http_status", "-"),
                    check.get("content_type", "-"),
                    _yes_no(check.get("has_content")),
                    check.get("message", ""),
                ]
            )
        lines.extend(["", "## Checks"])
        lines.extend(_markdown_table(["Check", "Status", "Latency", "HTTP", "Content-Type", "Has content", "Message"], rows))
    if data.get("next_command"):
        lines.extend(["", "## Next Command"])
        lines.extend(_markdown_code_block(data.get("next_command")))
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_config_markdown(data: dict[str, Any]) -> str:
    lines = ["# Smart Search Config", "", f"Status: {_status_label(data.get('ok'))}"]
    if data.get("config_file"):
        lines.append(f"Config file: `{data.get('config_file')}`")
    if data.get("config_dir"):
        lines.append(f"Config dir: `{data.get('config_dir')}`")
    if data.get("config_dir_source"):
        lines.append(f"Config dir source: `{data.get('config_dir_source')}`")
    if data.get("default_config_file"):
        lines.append(f"Default config file: `{data.get('default_config_file')}`")
    if data.get("legacy_windows_config_file"):
        lines.append(f"Legacy Windows config file: `{data.get('legacy_windows_config_file')}`")
        lines.append(f"Legacy Windows config exists: {_status_label(data.get('legacy_windows_config_exists'))}")
    if data.get("config_dir_override_value"):
        lines.append(f"SMART_SEARCH_CONFIG_DIR: `{data.get('config_dir_override_value')}`")
        lines.append(f"Override matches default: {_yes_no(data.get('config_dir_override_matches_default'))}")
    if "exists" in data:
        lines.append(f"Exists: {_status_label(bool(data.get('exists')))}")
    if data.get("key"):
        lines.append(f"Key: `{data.get('key')}`")
    if data.get("value"):
        lines.append(f"Value: `{data.get('value')}`")
    values = data.get("values") or {}
    if values:
        lines.extend(["", "## Values"])
        lines.extend(_markdown_table(["Key", "Value"], [[key, value] for key, value in values.items()]))
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_model_markdown(data: dict[str, Any]) -> str:
    lines = ["# Smart Search Model", "", f"Status: {_status_label(data.get('ok'))}"]
    rows = []
    if data.get("xai_model"):
        rows.append(["xai-responses", data.get("xai_model")])
    if data.get("openai_compatible_model"):
        rows.append(["openai-compatible", data.get("openai_compatible_model")])
    if data.get("current_model"):
        rows.append(["current", data.get("current_model")])
    if rows:
        lines.extend(["", "## Models"])
        lines.extend(_markdown_table(["Provider", "Model"], rows))
    if data.get("config_file"):
        lines.extend(["", f"Config file: `{data.get('config_file')}`"])
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_setup_markdown(data: dict[str, Any]) -> str:
    lines = ["# Smart Search Setup", "", f"Status: {_status_label(data.get('ok'))}"]
    if data.get("config_file"):
        lines.append(f"Config file: `{data.get('config_file')}`")
    saved = data.get("saved") or data.get("values") or {}
    if saved:
        lines.extend(["", "## Saved Values"])
        lines.extend(_markdown_table(["Key", "Value"], [[key, value] for key, value in saved.items()]))
    skills = data.get("skills") or {}
    if isinstance(skills, dict) and skills:
        installed = skills.get("installed") or []
        failed = skills.get("failed") or []
        lines.extend(["", "## Skills", f"Installed: {len(installed)}", f"Failed: {len(failed)}"])
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_skills_markdown(data: dict[str, Any]) -> str:
    lines = ["# Smart Search Skills", "", f"Status: {_status_label(data.get('ok'))}"]
    if data.get("root"):
        lines.append(f"Root: `{data.get('root')}`")
    if data.get("skill"):
        lines.append(f"Skill: `{data.get('skill')}`")
    if data.get("bundled_files") is not None:
        lines.append(f"Bundled files: {data.get('bundled_files')}")

    targets = data.get("targets") or data.get("installed") or []
    if targets:
        rows = []
        for item in targets:
            rows.append(
                [
                    item.get("target", ""),
                    item.get("status", "installed"),
                    item.get("files", item.get("installed_files", "")),
                    item.get("installed_files", ""),
                    _yes_no(item.get("hash_match")),
                    len(item.get("extra_files") or []),
                    item.get("path", ""),
                ]
            )
        lines.extend(["", "## Targets"])
        lines.extend(_markdown_table(["Target", "Status", "Files", "Installed", "Hash match", "Extra", "Path"], rows))
    if data.get("failed"):
        lines.extend(["", "## Failed"])
        lines.extend(_markdown_table(["Target", "Path", "Error"], [[item.get("target"), item.get("path"), item.get("error")] for item in data.get("failed", [])]))
    lines.extend(_error_lines(data))
    return "\n".join(lines).strip() + "\n"


def _format_markdown(command: str, data: dict[str, Any]) -> str:
    if command == "search":
        if not data.get("ok", False) and (data.get("error") or data.get("error_type")):
            lines = ["# Smart Search Search", ""]
            if data.get("query"):
                lines.append(f"Query: `{data.get('query')}`")
            if data.get("provider") is not None:
                lines.append(f"Provider: `{data.get('provider')}`")
            if data.get("model") is not None:
                lines.append(f"Model: `{data.get('model')}`")
            if data.get("stream") is not None:
                lines.append(f"Stream: {_yes_no(data.get('stream'))}")
            if data.get("recommendation"):
                lines.extend(["", "## Recommendation", str(data.get("recommendation"))])
            if data.get("diagnose_command"):
                lines.extend(["", "## Next Command"])
                lines.extend(_markdown_code_block(data.get("diagnose_command")))
            lines.extend(_error_lines(data))
            return "\n".join(lines).strip() + "\n"
        lines = [data.get("content", "")]
        primary_sources = data.get("primary_sources") or []
        extra_sources = data.get("extra_sources") or []
        if primary_sources or extra_sources:
            warning = data.get("source_warning") or ""
            if warning:
                lines.append(f"\n> {warning}")
            if primary_sources:
                lines.append("\n## Primary Sources")
                for item in primary_sources:
                    url = item.get("url", "")
                    title = item.get("title") or item.get("provider") or url
                    lines.append(f"- [{title}]({url})")
            if extra_sources:
                lines.append("\n## Extra Sources")
                for item in extra_sources:
                    url = item.get("url", "")
                    title = item.get("title") or item.get("provider") or url
                    lines.append(f"- [{title}]({url})")
            return "\n".join(lines).strip() + "\n"

        sources = data.get("sources") or []
        if sources:
            lines.append("\n## Sources")
            for item in sources:
                url = item.get("url", "")
                title = item.get("title") or item.get("provider") or url
                lines.append(f"- [{title}]({url})")
        return "\n".join(lines).strip() + "\n"
    if command == "fetch":
        return (data.get("content") or "") + ("\n" if data.get("content") else "")
    if command == "context7-docs":
        content = data.get("content") or ""
        lines = [
            "# Context7 Docs",
            "",
            f"Status: {_status_label(data.get('ok'))}",
            f"Library: `{data.get('library_id', '')}`",
            f"Query: `{data.get('query', '')}`",
        ]
        if content:
            lines.extend(["", content])
        lines.extend(_error_lines(data))
        return "\n".join(lines).strip() + "\n"
    if command == "deep":
        lines = [
            "# Deep Research Plan",
            "",
            f"**Question:** {data.get('question', '')}",
            f"**Mode:** {data.get('mode', '')}",
            f"**Difficulty:** {data.get('difficulty', '')}",
            f"**Evidence policy:** {data.get('evidence_policy', '')}",
            "",
            "## Boundary",
        ]
        usage_boundary = data.get("usage_boundary") or {}
        for key in ("search", "deep", "execution"):
            if usage_boundary.get(key):
                lines.append(f"- **{key}:** {usage_boundary[key]}")
        decomposition = data.get("decomposition") or []
        if decomposition:
            lines.extend(["", "## Decomposition"])
            for item in decomposition:
                lines.append(f"- **{item.get('id', '')}:** {item.get('question', '')}")
        steps = data.get("steps") or []
        if steps:
            lines.extend(["", "## Steps"])
            for step in steps:
                lines.append(f"{step.get('id', '')}. `{step.get('tool', '')}` ({step.get('subquestion_id', '')}) - {step.get('purpose', '')}")
                lines.append(f"   ```powershell\n   {step.get('command', '')}\n   ```")
        gap_check = data.get("gap_check") or {}
        if gap_check:
            lines.extend(["", "## Gap Check", gap_check.get("rule", "")])
        return "\n".join(lines).strip() + "\n"
    if command == "research":
        lines = [
            "# Research Report",
            "",
            f"**Question:** {data.get('question', '')}",
            f"**Status:** {_status_label(data.get('ok'))}",
            f"**Route policy:** {data.get('route_policy_version', '')}",
            f"**Evidence dir:** `{data.get('evidence_dir', '')}`",
            f"**Fallback used:** {bool(data.get('fallback_used'))}",
            f"**Degraded:** {bool(data.get('degraded'))}",
            "",
            "## Answer",
            data.get("final_answer") or data.get("content") or "",
        ]
        citations = data.get("citations") or []
        if citations:
            lines.extend(["", "## Citations"])
            for item in citations:
                url = item.get("url", "")
                title = item.get("title") or url
                provider = item.get("provider") or ""
                lines.append(f"- [{title}]({url})" + (f" ({provider})" if provider else ""))
        gaps = (data.get("gap_check") or {}).get("gaps") or []
        if gaps:
            lines.extend(["", "## Gaps"])
            for gap in gaps:
                reason = gap.get("reason", "")
                url = gap.get("url", "")
                lines.append(f"- {reason}" + (f" - {url}" if url else ""))
        return "\n".join(lines).strip() + "\n"
    if command == "doctor":
        return _format_doctor_markdown(data)
    if command == "diagnose":
        return _format_diagnose_markdown(data)
    if command == "smoke":
        return _format_smoke_markdown(data)
    if command == "config":
        return _format_config_markdown(data)
    if command == "model":
        return _format_model_markdown(data)
    if command == "setup":
        return _format_setup_markdown(data)
    if command == "skills":
        return _format_skills_markdown(data)
    titles = {
        "map": "Site Map",
        "exa-search": "Exa Search",
        "exa-similar": "Exa Similar Pages",
        "zhipu-search": "Zhipu Search",
        "zhipu-mcp-search": "Zhipu Coding Plan MCP Search",
        "zhipu-mcp-reader": "Zhipu Coding Plan MCP Reader",
        "zhipu-mcp-search-doc": "Zhipu Coding Plan MCP Search Doc",
        "zhipu-mcp-repo-structure": "Zhipu Coding Plan MCP Repo Structure",
        "zhipu-mcp-read-file": "Zhipu Coding Plan MCP Read File",
        "anysearch-domains": "AnySearch Domains",
        "anysearch-search": "AnySearch Search",
        "anysearch-extract": "AnySearch Extract",
        "anysearch-batch": "AnySearch Batch",
        "context7-library": "Context7 Library Search",
    }
    if command in titles:
        return _format_result_markdown(command, data, titles[command])
    return _format_config_markdown(data)


def _plain_result_lines(data: dict[str, Any]) -> list[str]:
    results = data.get("results") or []
    if not results:
        return ["No results."] if data.get("ok") else []
    lines = []
    for index, item in enumerate(results, 1):
        title = _result_title(item, index)
        target = _result_target(item)
        summary = _one_line(_result_summary(item), 120)
        line = f"{index}. {title}"
        if target:
            line += f" - {target}"
        if summary:
            line += f" - {summary}"
        lines.append(line)
    return lines


def _format_content(command: str, data: dict[str, Any]) -> str:
    if command in {"search", "fetch", "context7-docs", "research"}:
        content = data.get("content")
        if content:
            return str(content) + "\n"
        if data.get("ok"):
            return ""
        error = _error_summary(data)
        if error:
            return f"{_status_label(data.get('ok'))}: {error}\n"
        return ""
    if command == "deep" or data.get("mode") == "deep_research":
        lines = [
            f"Deep Research plan for: {data.get('question', '')}",
            "This command only plans; execute the listed CLI steps to perform live research.",
        ]
        return "\n".join(lines) + "\n"
    if command == "doctor":
        configured = data.get("capability_status", {})
        capability_bits = []
        for name, status in configured.items():
            if isinstance(status, dict):
                capability_bits.append(f"{name}={_status_label(status.get('ok'))}")
        lines = [
            f"Doctor {_status_label(data.get('ok'))}: {data.get('config_status', '')}".strip(),
            f"Minimum profile: {_status_label(data.get('minimum_profile_ok'))}",
        ]
        if capability_bits:
            lines.append("Capabilities: " + ", ".join(capability_bits))
        if data.get("error"):
            lines.append(f"Error: {_error_summary(data)}")
        return "\n".join(lines).strip() + "\n"
    if command == "diagnose":
        lines = [
            f"Diagnose {data.get('provider', '')} {_status_label(data.get('ok'))}: {data.get('summary', '')}".strip(),
        ]
        if data.get("recommendation"):
            lines.append(f"Recommendation: {data.get('recommendation')}")
        if data.get("error"):
            lines.append(f"Error: {_error_summary(data)}")
        return "\n".join(lines).strip() + "\n"
    if command == "smoke":
        cases = data.get("cases") or []
        failed = data.get("failed_cases") or []
        degraded = data.get("degraded_cases") or []
        return f"Smoke {data.get('mode', '')} {_status_label(data.get('ok'))}: {len(cases)} cases, {len(failed)} failed, {len(degraded)} degraded\n"
    if command == "config":
        parts = [f"Config {_status_label(data.get('ok'))}"]
        if data.get("config_file"):
            parts.append(f"file={data.get('config_file')}")
        if data.get("config_dir_source"):
            parts.append(f"source={data.get('config_dir_source')}")
        if data.get("config_dir_override_value"):
            parts.append(f"override={data.get('config_dir_override_value')}")
        if data.get("key"):
            parts.append(f"key={data.get('key')}")
        if data.get("value"):
            parts.append(f"value={data.get('value')}")
        values = data.get("values") or {}
        if values:
            parts.append(f"values={len(values)}")
        if data.get("error"):
            parts.append(f"error={_error_summary(data)}")
        return "; ".join(parts) + "\n"
    if command == "model":
        if data.get("error"):
            return f"Model {_status_label(data.get('ok'))}: {_error_summary(data)}\n"
        rows = []
        if data.get("xai_model"):
            rows.append(f"xai-responses={data.get('xai_model')}")
        if data.get("openai_compatible_model"):
            rows.append(f"openai-compatible={data.get('openai_compatible_model')}")
        if data.get("current_model"):
            rows.append(f"current={data.get('current_model')}")
        return ("Models: " + ", ".join(rows) if rows else f"Model {_status_label(data.get('ok'))}") + "\n"
    if command == "setup":
        if data.get("error"):
            return f"Setup {_status_label(data.get('ok'))}: {_error_summary(data)}\n"
        saved = data.get("saved") or data.get("values") or {}
        return f"Setup {_status_label(data.get('ok'))}: {len(saved)} values saved\n"
    if command == "skills":
        if data.get("error"):
            return f"Skills {_status_label(data.get('ok'))}: {_error_summary(data)}\n"
        targets = data.get("targets") or data.get("installed") or []
        counts = data.get("status_counts") or {}
        if counts:
            summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
            return f"Skills {_status_label(data.get('ok'))}: {summary}\n"
        return f"Skills {_status_label(data.get('ok'))}: {len(targets)} targets\n"
    if command in {
        "map",
        "exa-search",
        "exa-similar",
        "zhipu-search",
        "zhipu-mcp-search",
        "zhipu-mcp-reader",
        "zhipu-mcp-search-doc",
        "zhipu-mcp-repo-structure",
        "zhipu-mcp-read-file",
        "anysearch-domains",
        "anysearch-search",
        "anysearch-extract",
        "anysearch-batch",
        "context7-library",
    }:
        lines = _plain_result_lines(data)
        if data.get("error"):
            lines.append(f"Error: {_error_summary(data)}")
        return "\n".join(lines).strip() + "\n"
    if data.get("error"):
        return f"{_status_label(data.get('ok'))}: {_error_summary(data)}\n"
    return f"{command}: {_status_label(data.get('ok'))}\n"


def _render(command: str, data: dict[str, Any], fmt: str) -> str:
    if fmt == "content":
        return _format_content(command, data)
    if fmt == "markdown":
        return _format_markdown(command, data)
    return _json(data)


def _stdout_safe(text: str) -> str:
    return _stream_safe(sys.stdout, text)


def _stream_safe(stream: Any, text: str) -> str:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    errors = getattr(stream, "errors", None) or "strict"
    try:
        text.encode(encoding, errors=errors)
        return text
    except UnicodeEncodeError:
        return text.encode(encoding, errors="backslashreplace").decode(encoding)


def _write_stdout(text: str) -> None:
    sys.stdout.write(_stdout_safe(text))


def _write_stderr(text: str) -> None:
    sys.stderr.write(_stream_safe(sys.stderr, text))


def _smart_search_banner_text() -> str:
    try:
        import pyfiglet

        banner = pyfiglet.figlet_format("Smart Search", font="slant")
        return banner.rstrip()
    except Exception:
        return _STATIC_SMART_SEARCH_BANNER


def _write_setup_banner(lang: str) -> None:
    banner = _smart_search_banner_text()
    tagline = _t(lang, "CLI-first multi-source search for AI agents", "CLI-first multi-source search for AI agents")
    _write_stderr(f"\n{banner}\n\n   Smart Search\n   {tagline}\n")


def _write_panel(text: str, lang: str) -> None:
    if not _is_interactive_setup_stream():
        _write_stderr(text)
        return
    try:
        from rich.console import Console
        from rich.panel import Panel
    except Exception:
        _write_stderr(text)
        return
    console = Console(file=sys.stderr, force_terminal=True)
    title = _t(lang, "Smart Search 配置", "Smart Search Setup")
    console.print(Panel(text.strip(), title=title, expand=False, safe_box=True))


def _exit_code(data: dict[str, Any]) -> int:
    if data.get("ok", False):
        return EXIT_OK
    error_type = data.get("error_type")
    if error_type == "config_error":
        return EXIT_CONFIG_ERROR
    if error_type == "parameter_error":
        return EXIT_PARAMETER_ERROR
    if error_type == "network_error":
        return EXIT_NETWORK_ERROR
    if error_type == "evidence_error":
        return EXIT_NETWORK_ERROR
    return EXIT_RUNTIME_ERROR


def _print_result(command: str, data: dict[str, Any], fmt: str, output: str = "") -> int:
    rendered = _render(command, data, fmt)
    if output:
        service.write_output(output, rendered)
    if fmt == "json":
        rendered = _json_stdout_safe(data)
    _write_stdout(rendered)
    if rendered and not rendered.endswith("\n"):
        _write_stdout("\n")
    return _exit_code(data)


def _add_format_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "markdown", "content"], default="json")
    parser.add_argument("--output", default="", help="Write rendered output to a file.")


def _is_secret_key(key: str) -> bool:
    upper_key = key.upper()
    return "KEY" in upper_key or "TOKEN" in upper_key or "SECRET" in upper_key


def _is_private_display_key(key: str) -> bool:
    return key.upper().endswith("_URL") or key.upper().endswith("_BASE_URL")


def _t(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


def _display_provider(provider: str, lang: str) -> str:
    names = {
        "xai-responses": "xAI Responses",
        "openai-compatible": "OpenAI-compatible",
        "zhipu": _t(lang, "智谱", "Zhipu"),
        "zhipu-mcp": _t(lang, "智谱 Coding Plan MCP", "Zhipu Coding Plan MCP"),
        "zhipu-mcp-reader": _t(lang, "智谱 MCP Reader", "Zhipu MCP Reader"),
        "exa": "Exa",
        "context7": "Context7",
        "jina": "Jina Reader",
        "tavily": "Tavily",
        "firecrawl": "Firecrawl",
        "anysearch": "AnySearch",
    }
    return names.get(provider, provider)


def _with_scheme(url: str) -> str:
    value = url.strip()
    if not value:
        return ""
    if "://" not in value:
        return f"https://{value}"
    return value


def _normalize_custom_base_url(url: str) -> str:
    value = _with_scheme(url).strip()
    return value.rstrip("/") if value else ""


def _normalize_tavily_api_url(url: str, *, hikari: bool = True) -> str:
    value = _normalize_custom_base_url(url)
    if not value:
        return ""
    parsed = urlsplit(value)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if host == "api.tavily.com":
        return urlunsplit((parsed.scheme, parsed.netloc, path or "", "", ""))
    if hikari and path in {"", "/mcp"}:
        return urlunsplit((parsed.scheme, parsed.netloc, "/api/tavily", "", ""))
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _normalize_tavily_flag_api_url(url: str, api_key: str = "") -> str:
    value = _normalize_custom_base_url(url)
    if not value:
        return ""
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    if path == "/mcp" or _is_tavily_hikari_key(api_key):
        return _normalize_tavily_api_url(value)
    return _normalize_tavily_api_url(value, hikari=False)


def _normalize_firecrawl_api_url(url: str) -> str:
    return _normalize_custom_base_url(url)


def _normalize_zhipu_api_url(url: str) -> str:
    return _normalize_custom_base_url(url)


def _normalize_jina_reader_api_url(url: str) -> str:
    return _normalize_custom_base_url(url)


def _is_tavily_hikari_key(api_key: str) -> bool:
    return api_key.strip().lower().startswith("th-")


def _is_interactive_setup_stream() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)() and getattr(sys.stderr, "isatty", lambda: False)())


def _setup_status_from_values(values: dict[str, str]) -> dict[str, Any]:
    def has(key: str) -> bool:
        return bool(values.get(key))

    main_configured: set[str] = set()
    if has("XAI_API_KEY"):
        main_configured.add("xai-responses")
    if has("OPENAI_COMPATIBLE_API_URL") and has("OPENAI_COMPATIBLE_API_KEY"):
        main_configured.add("openai-compatible")

    status = {
        "main_search": {
            "configured": [provider for provider in ("xai-responses", "openai-compatible") if provider in main_configured],
            "fallback_chain": ["xai-responses", "openai-compatible"],
        },
        "web_search": {
            "configured": [
                provider
                for provider, configured in [
                    ("zhipu", has("ZHIPU_API_KEY")),
                    ("zhipu-mcp", has("ZHIPU_MCP_API_KEY")),
                    ("tavily", has("TAVILY_API_KEY")),
                    ("firecrawl", has("FIRECRAWL_API_KEY")),
                ]
                if configured
            ],
            "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"],
        },
        "docs_search": {
            "configured": [
                provider
                for provider, configured in [
                    ("context7", has("CONTEXT7_API_KEY")),
                    ("exa", has("EXA_API_KEY")),
                ]
                if configured
            ],
            "fallback_chain": ["context7", "exa"],
        },
        "web_fetch": {
            "configured": [
                provider
                for provider, configured in [
                    ("tavily", has("TAVILY_API_KEY")),
                    ("jina", has("JINA_API_KEY")),
                    ("zhipu-mcp-reader", has("ZHIPU_MCP_API_KEY")),
                    ("firecrawl", has("FIRECRAWL_API_KEY")),
                ]
                if configured
            ],
            "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"],
        },
        "vertical_search": {
            "configured": ["anysearch"] if has("ANYSEARCH_API_KEY") else [],
            "fallback_chain": ["anysearch"],
            "experimental": True,
        },
    }
    for item in status.values():
        item["ok"] = bool(item["configured"])
    return status


def _merge_setup_values(current: dict[str, str], values: dict[str, str]) -> dict[str, str]:
    merged = dict(current)
    merged.update({key: value for key, value in values.items() if value})
    return merged


def _write_setup_status(status: dict[str, Any], lang: str, *, final: bool = False) -> None:
    title = _t(lang, "最低配置检查", "Minimum profile check") if final else _t(lang, "当前状态", "Current status")
    _write_stderr(f"\n{title}:\n")
    required = {"main_search", "docs_search", "web_fetch"}
    labels = {
        "main_search": _t(lang, "main_search 主搜索", "main_search primary search"),
        "docs_search": _t(lang, "docs_search 文档搜索", "docs_search documentation search"),
        "web_fetch": _t(lang, "web_fetch 网页抓取", "web_fetch page fetch"),
        "web_search": _t(lang, "web_search 网页补强", "web_search web reinforcement"),
        "vertical_search": _t(lang, "vertical_search 垂直搜索", "vertical_search vertical search"),
    }
    for capability in ("main_search", "docs_search", "web_fetch", "web_search", "vertical_search"):
        item = status.get(capability, {})
        configured = item.get("configured") or []
        configured_text = ", ".join(_display_provider(provider, lang) for provider in configured)
        if item.get("ok"):
            marker = "OK"
            value = configured_text
        elif capability in required:
            marker = "MISSING"
            value = _t(lang, "需要至少配置一个 provider", "at least one provider is required")
        else:
            marker = "OPTIONAL"
            value = _t(lang, "未配置", "not configured")
        _write_stderr(f"  [{marker}] {labels[capability]}: {value}\n")


def _prompt_choice(prompt: str, default: str = "") -> str:
    _write_stderr(prompt)
    value = input("").strip()
    return value or default


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    default_text = "Y/n" if default else "y/N"
    answer = _prompt_choice(f"{prompt} [{default_text}]: ", "y" if default else "n").strip().lower()
    return answer in {"y", "yes", "是", "好", "1", "true"}


def _prompt_value(key: str, label: str, current: str = "", optional: bool = False, lang: str = "en") -> str:
    suffix = _t(lang, " 可选", " optional") if optional else _t(lang, " 必填", " required")
    current_display = (
        _t(lang, "已配置，回车保留", "configured, press Enter to keep")
        if current and (_is_secret_key(key) or _is_private_display_key(key))
        else current
    )
    if current:
        prompt = f"{label}{suffix} [{current_display}]: "
    else:
        prompt = f"{label}{suffix}: "
    if _is_secret_key(key):
        value = getpass.getpass(_stream_safe(sys.stderr, prompt)).strip()
    else:
        _write_stderr(prompt)
        value = input("").strip()
    return value or current


def _ascii_choice_values(choices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**choice, "name": _stream_safe(sys.stderr, str(choice.get("name", "")))}
        for choice in choices
    ]


def _select_with_tui(message: str, choices: list[dict[str, Any]], default: Any = None) -> Any:
    if not _is_interactive_setup_stream():
        return None
    try:
        from InquirerPy import inquirer
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            return inquirer.select(
                message=_stream_safe(sys.stderr, message),
                choices=_ascii_choice_values(choices),
                default=default,
                qmark="",
                pointer=">",
                marker=">",
            ).execute()
    except (KeyboardInterrupt, EOFError):
        raise
    except Exception:
        return None


def _checkbox_with_tui(message: str, choices: list[dict[str, Any]]) -> list[str] | None:
    if not _is_interactive_setup_stream():
        return None
    try:
        from InquirerPy import inquirer
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = inquirer.checkbox(
                message=_stream_safe(sys.stderr, message),
                choices=_ascii_choice_values(choices),
                instruction="(Up/Down move, Space select, Enter confirm)",
                qmark="",
                pointer=">",
                enabled_symbol="[x]",
                disabled_symbol="[ ]",
            ).execute()
        return [str(item) for item in result]
    except (KeyboardInterrupt, EOFError):
        raise
    except Exception:
        return None


def _provider_choices(providers: list[str], selected: list[str], lang: str) -> list[dict[str, Any]]:
    selected_set = set(selected)
    return [
        {"name": _display_provider(provider, lang), "value": provider, "enabled": provider in selected_set}
        for provider in providers
    ]


def _prompt_provider_multi_select(
    message: str,
    providers: list[str],
    default_selected: list[str],
    lang: str,
) -> list[str]:
    tui_value = _checkbox_with_tui(message, _provider_choices(providers, default_selected, lang))
    if tui_value is not None:
        return [provider for provider in providers if provider in set(tui_value)]

    default_text = ",".join(default_selected) if default_selected else "skip"
    _write_stderr(f"{message} [{'/'.join(providers)}/skip] ({default_text}): ")
    raw = input("").strip().lower()
    if not raw:
        return [provider for provider in providers if provider in set(default_selected)]
    aliases = {
        "跳过": "skip",
        "无": "skip",
        "n": "skip",
        "no": "skip",
        "否": "skip",
        "都配": "all",
        "全部": "all",
        "两个": "all",
        "both": "all",
        "all": "all",
        "xai": "xai-responses",
        "openai": "openai-compatible",
        "ctx7": "context7",
        "context": "context7",
    }
    tokens = [aliases.get(part.strip(), part.strip()) for part in raw.replace("+", ",").replace(";", ",").split(",")]
    if len(tokens) == 1 and " " in tokens[0]:
        tokens = [aliases.get(part.strip(), part.strip()) for part in tokens[0].split()]
    if "skip" in tokens or "none" in tokens:
        return []
    if "all" in tokens:
        return providers
    selected = [provider for provider in providers if provider in tokens]
    return selected if selected else [provider for provider in providers if provider in set(default_selected)]


def _prompt_select(message: str, choices: list[dict[str, Any]], default: str) -> str:
    tui_value = _select_with_tui(message, choices, default)
    if tui_value is not None:
        return str(tui_value)
    choice_values = [str(choice["value"]) for choice in choices]
    _write_stderr(f"{message} [{'/'.join(choice_values)}] ({default}): ")
    value = input("").strip().lower()
    return value if value in set(choice_values) else default


def _select_setup_language(lang: str = "") -> str:
    if lang in {"zh", "en"}:
        return lang
    choices = [
        {"name": "中文", "value": "zh"},
        {"name": "English", "value": "en"},
    ]
    answer = _prompt_select("Language / 语言", choices, "zh").strip().lower()
    if answer in {"en", "english"}:
        return "en"
    return "zh"


def _skill_target_choices(selected: list[str], lang: str) -> list[dict[str, Any]]:
    selected_set = set(selected)
    choices: list[dict[str, Any]] = []
    for target in SKILL_TARGETS:
        label = target.label
        name = f"{label} (~/{target.relative_root})"
        choices.append({"name": name, "value": target.target_id, "enabled": target.target_id in selected_set})
    return choices


def _prompt_skill_targets(lang: str) -> list[str]:
    _write_stderr(
        _t(
            lang,
            "\n[可选] 安装 smart-search-cli skill\n用途: 让本机全局 AI 工具知道优先调用 smart-search CLI。\n提示: 只安装 Smart Search skill；不会初始化 Trellis，也不会生成 hooks、agents 或 commands。\n",
            "\n[Optional] Install the smart-search-cli skill\nPurpose: teach user-level AI tools on this machine to call the smart-search CLI first.\nNote: this only installs the Smart Search skill; it does not initialize Trellis or generate hooks, agents, or commands.\n",
        )
    )
    tui_value = _checkbox_with_tui(
        _t(lang, "安装给哪些 AI 工具使用?", "Install for which AI tools?"),
        _skill_target_choices(DEFAULT_SKILL_TARGET_IDS, lang),
    )
    if tui_value is not None:
        return [target.target_id for target in SKILL_TARGETS if target.target_id in set(tui_value)]

    default_text = ",".join(DEFAULT_SKILL_TARGET_IDS)
    _write_stderr(
        _t(
            lang,
            f"安装 skill 目标 [codex,claude,cursor,.../all/skip] ({default_text}): ",
            f"Skill install targets [codex,claude,cursor,.../all/skip] ({default_text}): ",
        )
    )
    raw = input("").strip()
    if not raw:
        return list(DEFAULT_SKILL_TARGET_IDS)
    try:
        return parse_skill_targets(raw)
    except SkillInstallError as e:
        _write_stderr(f"{e}\n")
        return list(DEFAULT_SKILL_TARGET_IDS)


def _setup_choice(prompt: str, choices: set[str], default: str) -> str:
    value = _prompt_choice(prompt, default).strip().lower()
    aliases = {
        "保持": "keep",
        "跳过": "skip",
        "都配": "both",
        "两个": "both",
        "是": "yes",
        "否": "no",
    }
    value = aliases.get(value, value)
    return value if value in choices else default


def _prompt_main_search(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    status = _setup_status_from_values(_merge_setup_values(current, values))
    configured = status["main_search"]["configured"]
    default_selected = configured or ["xai-responses"]
    _write_stderr(
        _t(
            lang,
            "\n[1/3 必选] main_search 主搜索\n用途: 负责综合搜索回答和最终合成。\n推荐: 有 xAI key 选 xai；有中转服务选 openai；两者都配可以同能力兜底。\n",
            "\n[1/3 Required] main_search primary search\nPurpose: broad search answers and final synthesis.\nRecommended: choose xai for an xAI key, openai for a relay, or both for same-capability fallback.\n",
        )
    )
    selected = _prompt_provider_multi_select(
        _t(
            lang,
            "选择 main_search provider",
            "Choose main_search providers",
        ),
        ["xai-responses", "openai-compatible"],
        default_selected,
        lang,
    )
    if "xai-responses" in selected:
        values["XAI_API_KEY"] = _prompt_value("XAI_API_KEY", "xAI API key", current.get("XAI_API_KEY", ""), lang=lang)
        values["XAI_MODEL"] = _prompt_value(
            "XAI_MODEL",
            _t(lang, "xAI Responses 模型", "xAI Responses model"),
            current.get("XAI_MODEL", ""),
            optional=True,
            lang=lang,
        )
    if "openai-compatible" in selected:
        values["OPENAI_COMPATIBLE_API_URL"] = _prompt_value(
            "OPENAI_COMPATIBLE_API_URL",
            _t(
                lang,
                "OpenAI-compatible API 地址（示例: https://api.openai.com/v1）",
                "OpenAI-compatible API URL (example: https://api.openai.com/v1)",
            ),
            current.get("OPENAI_COMPATIBLE_API_URL", ""),
            lang=lang,
        )
        values["OPENAI_COMPATIBLE_API_KEY"] = _prompt_value(
            "OPENAI_COMPATIBLE_API_KEY",
            "OpenAI-compatible API key",
            current.get("OPENAI_COMPATIBLE_API_KEY", ""),
            lang=lang,
        )
        values["OPENAI_COMPATIBLE_MODEL"] = _prompt_value(
            "OPENAI_COMPATIBLE_MODEL",
            _t(lang, "OpenAI-compatible 模型", "OpenAI-compatible model"),
            current.get("OPENAI_COMPATIBLE_MODEL", ""),
            optional=True,
            lang=lang,
        )
        stream_default = current.get("OPENAI_COMPATIBLE_STREAM", "")
        if _prompt_yes_no(
            _t(
                lang,
                f"是否启用 OpenAI-compatible stream=true？用于部分中转长请求兼容 [{stream_default or 'false'}]: ",
                f"Enable OpenAI-compatible stream=true for relay long-request compatibility [{stream_default or 'false'}]: ",
            ),
            default=(str(stream_default).lower() in {"true", "1", "yes"}),
        ):
            values["OPENAI_COMPATIBLE_STREAM"] = "true"
        elif stream_default:
            values["OPENAI_COMPATIBLE_STREAM"] = "false"


def _prompt_docs_search(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    status = _setup_status_from_values(_merge_setup_values(current, values))
    default_selected = status["docs_search"]["configured"] or ["context7"]
    _write_stderr(
        _t(
            lang,
            "\n[2/3 必选] docs_search 文档搜索\n用途: 查官方文档、SDK、API、框架和库说明。\n推荐: 文档/API/库优先 Context7；官方域名、论文和低噪声发现再配 Exa。\n",
            "\n[2/3 Required] docs_search documentation search\nPurpose: official docs, SDKs, APIs, frameworks, and library references.\nRecommended: Context7 for docs/API/library intent; Exa for official domains, papers, and low-noise discovery.\n",
        )
    )
    selected = _prompt_provider_multi_select(
        _t(
            lang,
            "选择 docs_search provider",
            "Choose docs_search providers",
        ),
        ["exa", "context7"],
        default_selected,
        lang,
    )
    if "exa" in selected:
        values["EXA_API_KEY"] = _prompt_value("EXA_API_KEY", "Exa API key", current.get("EXA_API_KEY", ""), lang=lang)
    if "context7" in selected:
        values["CONTEXT7_API_KEY"] = _prompt_value(
            "CONTEXT7_API_KEY",
            "Context7 API key",
            current.get("CONTEXT7_API_KEY", ""),
            lang=lang,
        )


def _prompt_tavily_api_url(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    current_url = current.get("TAVILY_API_URL", "")
    tavily_key = values.get("TAVILY_API_KEY") or current.get("TAVILY_API_KEY", "")
    if current_url:
        default_choice = "current"
    elif _is_tavily_hikari_key(tavily_key):
        default_choice = "hikari"
    else:
        default_choice = "official"
    choices = []
    if current_url:
        choices.append({"name": _t(lang, "保留当前地址（已配置）", "Keep current URL (configured)"), "value": "current"})
    choices.extend([
        {"name": _t(lang, "官方 Tavily (https://api.tavily.com)", "Official Tavily (https://api.tavily.com)"), "value": "official"},
        {"name": _t(lang, "Tavily Hikari / 号池", "Tavily Hikari / pooled endpoint"), "value": "hikari"},
        {"name": _t(lang, "自定义 Tavily REST base", "Custom Tavily REST base"), "value": "custom"},
    ])
    choice = _prompt_select(_t(lang, "选择 Tavily endpoint", "Choose Tavily endpoint"), choices, default_choice)
    if choice == "current":
        return
    if choice == "official":
        values["TAVILY_API_URL"] = TAVILY_DEFAULT_API_URL
        return
    if choice == "hikari":
        _write_stderr(
            _t(
                lang,
                "号池地址填服务商给你的域名或 URL，例如 https://pool.example.com 或 https://pool.example.com/mcp；setup 会保存为 https://pool.example.com/api/tavily。\n",
                "For pooled endpoints, paste the provider domain or URL, for example https://pool.example.com or https://pool.example.com/mcp; setup saves it as https://pool.example.com/api/tavily.\n",
            )
        )
    label = _t(
        lang,
        "Tavily REST 地址",
        "Tavily REST URL",
    )
    raw = _prompt_value("TAVILY_API_URL", label, current_url, optional=False, lang=lang)
    normalized = _normalize_tavily_api_url(raw) if choice == "hikari" else _normalize_tavily_api_url(raw, hikari=False)
    if normalized:
        values["TAVILY_API_URL"] = normalized
        if normalized != raw.rstrip("/"):
            _write_stderr(_t(lang, f"已规范化 Tavily REST base: {normalized}\n", f"Normalized Tavily REST base: {normalized}\n"))


def _prompt_firecrawl_api_url(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    current_url = current.get("FIRECRAWL_API_URL", "")
    choices = []
    if current_url:
        choices.append({"name": _t(lang, "保留当前地址（已配置）", "Keep current URL (configured)"), "value": "current"})
    choices.extend([
        {
            "name": _t(
                lang,
                "官方 Firecrawl (https://api.firecrawl.dev/v2)",
                "Official Firecrawl (https://api.firecrawl.dev/v2)",
            ),
            "value": "official",
        },
        {"name": _t(lang, "自定义 Firecrawl REST base", "Custom Firecrawl REST base"), "value": "custom"},
    ])
    default_choice = "current" if current_url else "official"
    choice = _prompt_select(_t(lang, "选择 Firecrawl endpoint", "Choose Firecrawl endpoint"), choices, default_choice)
    if choice == "current":
        return
    if choice == "official":
        values["FIRECRAWL_API_URL"] = FIRECRAWL_DEFAULT_API_URL
        return
    raw = _prompt_value(
        "FIRECRAWL_API_URL",
        _t(lang, "Firecrawl 自定义 REST base", "Firecrawl custom REST base"),
        current_url,
        optional=False,
        lang=lang,
    )
    normalized = _normalize_firecrawl_api_url(raw)
    if normalized:
        values["FIRECRAWL_API_URL"] = normalized


def _prompt_zhipu_api_url(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    current_url = current.get("ZHIPU_API_URL", "")
    choices = []
    if current_url:
        choices.append({"name": _t(lang, "保留当前地址（已配置）", "Keep current URL (configured)"), "value": "current"})
    choices.extend([
        {
            "name": _t(
                lang,
                "官方智谱 Web Search API (https://open.bigmodel.cn/api)",
                "Official Zhipu Web Search API (https://open.bigmodel.cn/api)",
            ),
            "value": "official",
        },
        {
            "name": _t(
                lang,
                "自定义智谱 API 地址",
                "Custom Zhipu API URL",
            ),
            "value": "custom",
        },
    ])
    default_choice = "current" if current_url else "official"
    choice = _prompt_select(_t(lang, "选择智谱 API 地址", "Choose Zhipu API URL"), choices, default_choice)
    if choice == "current":
        return
    if choice == "official":
        values["ZHIPU_API_URL"] = ZHIPU_DEFAULT_API_URL
        return
    raw = _prompt_value(
        "ZHIPU_API_URL",
        _t(lang, "智谱 API 地址", "Zhipu API URL"),
        current_url,
        optional=False,
        lang=lang,
    )
    normalized = _normalize_zhipu_api_url(raw)
    if normalized:
        values["ZHIPU_API_URL"] = normalized


def _prompt_zhipu_search_engine(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    current_engine = current.get("ZHIPU_SEARCH_ENGINE", "")
    choices = []
    if current_engine:
        choices.append(
            {
                "name": _t(
                    lang,
                    f"保留当前搜索服务（{current_engine}）",
                    f"Keep current search service ({current_engine})",
                ),
                "value": "current",
            }
        )
    choices.extend(
        {"name": engine, "value": engine}
        for engine in ZHIPU_SEARCH_ENGINE_CHOICES
    )
    choices.append({"name": _t(lang, "自定义搜索服务", "Custom search service"), "value": "custom"})
    default_choice = "current" if current_engine else "search_std"
    choice = _prompt_select(_t(lang, "选择智谱搜索服务", "Choose Zhipu search service"), choices, default_choice)
    if choice == "current":
        return
    if choice == "custom":
        raw = _prompt_value(
            "ZHIPU_SEARCH_ENGINE",
            _t(lang, "智谱搜索服务", "Zhipu search service"),
            current_engine,
            optional=False,
            lang=lang,
        )
        if raw:
            values["ZHIPU_SEARCH_ENGINE"] = raw.strip()
        return
    values["ZHIPU_SEARCH_ENGINE"] = choice


def _prompt_web_fetch(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    status = _setup_status_from_values(_merge_setup_values(current, values))
    default_selected = status["web_fetch"]["configured"] or ["tavily"]
    _write_stderr(
        _t(
            lang,
            "\n[3/3 必选] web_fetch 网页抓取\n用途: 已知 URL 抓正文；高风险事实核验必须用。\n推荐: Tavily 优先；Jina 需要 key 才算标准配置；Firecrawl 可作为抓取兜底。\n",
            "\n[3/3 Required] web_fetch page fetch\nPurpose: extract known URLs; required for high-risk fact checks.\nRecommended: Tavily first; Jina requires a key to satisfy standard config; Firecrawl as fetch fallback.\n",
        )
    )
    selected = _prompt_provider_multi_select(
        _t(
            lang,
            "选择 web_fetch provider",
            "Choose web_fetch providers",
        ),
        ["tavily", "jina", "firecrawl"],
        default_selected,
        lang,
    )
    if "tavily" in selected:
        values["TAVILY_API_KEY"] = _prompt_value("TAVILY_API_KEY", "Tavily API key", current.get("TAVILY_API_KEY", ""), lang=lang)
        _prompt_tavily_api_url(values, current, lang)
    if "jina" in selected:
        values["JINA_API_KEY"] = _prompt_value("JINA_API_KEY", "Jina API key", current.get("JINA_API_KEY", ""), lang=lang)
        raw_url = _prompt_value(
            "JINA_READER_API_URL",
            "Jina Reader API URL",
            current.get("JINA_READER_API_URL", "https://r.jina.ai"),
            optional=True,
            lang=lang,
        )
        values["JINA_READER_API_URL"] = _normalize_jina_reader_api_url(raw_url)
    if "firecrawl" in selected:
        values["FIRECRAWL_API_KEY"] = _prompt_value(
            "FIRECRAWL_API_KEY",
            "Firecrawl API key",
            current.get("FIRECRAWL_API_KEY", ""),
            lang=lang,
        )
        _prompt_firecrawl_api_url(values, current, lang)


def _prompt_optional_enhancements(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    _write_stderr(
        _t(
            lang,
            "\n[可选增强] web_search 网页补强\n用途: 中文、国内、时效、域名过滤类来源检索。\n推荐: 中文场景建议配置 Zhipu。\n",
            "\n[Optional] web_search web reinforcement\nPurpose: Chinese, domestic, current, or domain-filtered source discovery.\nRecommended: configure Zhipu for Chinese/current scenarios.\n",
        )
    )
    default_selected = ["zhipu"] if current.get("ZHIPU_API_KEY") else []
    selected = _prompt_provider_multi_select(
        _t(lang, "选择可选 web_search 增强", "Choose optional web_search reinforcement"),
        ["zhipu"],
        default_selected,
        lang,
    )
    if "zhipu" in selected:
        values["ZHIPU_API_KEY"] = _prompt_value("ZHIPU_API_KEY", "Zhipu API key", current.get("ZHIPU_API_KEY", ""), lang=lang)
        _prompt_zhipu_api_url(values, current, lang)
        _prompt_zhipu_search_engine(values, current, lang)
    if _prompt_yes_no(_t(lang, "是否调整验证/兜底默认值?", "Adjust validation/fallback defaults?"), default=False):
        values["SMART_SEARCH_VALIDATION_LEVEL"] = _prompt_value(
            "SMART_SEARCH_VALIDATION_LEVEL",
            _t(lang, "验证强度 (fast/balanced/strict)", "Validation level (fast/balanced/strict)"),
            current.get("SMART_SEARCH_VALIDATION_LEVEL", ""),
            optional=True,
            lang=lang,
        )
        values["SMART_SEARCH_FALLBACK_MODE"] = _prompt_value(
            "SMART_SEARCH_FALLBACK_MODE",
            _t(lang, "兜底模式 (auto/off)", "Fallback mode (auto/off)"),
            current.get("SMART_SEARCH_FALLBACK_MODE", ""),
            optional=True,
            lang=lang,
        )
        values["SMART_SEARCH_MINIMUM_PROFILE"] = _prompt_value(
            "SMART_SEARCH_MINIMUM_PROFILE",
            _t(lang, "最低配置门槛 (standard/off)", "Minimum profile (standard/off)"),
            current.get("SMART_SEARCH_MINIMUM_PROFILE", ""),
            optional=True,
            lang=lang,
        )


def _write_setup_keep_note(lang: str) -> None:
    _write_stderr(
        _t(
            lang,
            "\n提示: setup 不会删除旧配置；删除请运行 `smart-search config unset KEY`。\n",
            "\nNote: setup does not delete saved values; use `smart-search config unset KEY` to remove one.\n",
        )
    )


def _write_setup_examples(lang: str) -> None:
    _write_stderr(
        _t(
            lang,
            "\n不知道怎么填: 先配齐 main_search + docs_search + web_fetch。\n"
            "  main_search: xAI Responses，或 OpenAI-compatible（示例: https://api.openai.com/v1）\n"
            "  docs_search: 文档/API 优先 Context7；官方域名、论文和低噪声发现再配 Exa。\n"
            "  web_fetch: Tavily 官方地址是 https://api.tavily.com；号池填 https://<host>/api/tavily。\n"
            "  key 都填你自己控制台里的；Zhipu / Firecrawl 可以之后再补。\n",
            "\nIf unsure: first configure main_search + docs_search + web_fetch.\n"
            "  main_search: xAI Responses, or OpenAI-compatible (example: https://api.openai.com/v1)\n"
            "  docs_search: Context7 for docs/API first; add Exa for official domains, papers, and low-noise discovery.\n"
            "  web_fetch: official Tavily endpoint is https://api.tavily.com; pooled endpoints use https://<host>/api/tavily.\n"
            "  Use keys from your own provider consoles. Zhipu / Firecrawl can be added later.\n",
        )
    )


def _run_guided_setup_prompts(
    values: dict[str, str],
    current: dict[str, str],
    lang: str,
    *,
    skill_targets: list[str] | None = None,
    show_banner: bool = True,
) -> None:
    config_file = service.config_path()["config_file"]
    if show_banner:
        _write_setup_banner(lang)
    _write_panel(
        _t(
            lang,
            f"\nSmart Search 配置向导\n配置文件: {config_file}\n\n目标: standard 最低可用配置\n操作: 方向键移动，空格勾选，回车确认；API key 输入不显示。\n最低要求: main_search + docs_search + web_fetch 各至少一个 provider。\n",
            f"\nSmart Search setup wizard\nConfig file: {config_file}\n\nGoal: standard minimum profile\nKeys: move with arrow keys, select with Space, confirm with Enter; API key input is hidden.\nMinimum: at least one provider in each of main_search + docs_search + web_fetch.\n",
        ),
        lang,
    )
    _write_setup_keep_note(lang)
    _write_setup_examples(lang)
    _write_setup_status(_setup_status_from_values(_merge_setup_values(current, values)), lang)
    if skill_targets is not None:
        skill_targets[:] = _prompt_skill_targets(lang)
    _prompt_main_search(values, current, lang)
    _prompt_docs_search(values, current, lang)
    _prompt_web_fetch(values, current, lang)
    _prompt_optional_enhancements(values, current, lang)


def _write_skill_install_summary(result: dict[str, Any], lang: str) -> None:
    if not result.get("selected"):
        _write_stderr(_t(lang, "\nSkill 安装: 已跳过。\n", "\nSkill install: skipped.\n"))
        return
    _write_stderr(
        _t(
            lang,
            f"\nSkill 安装结果: installed {result.get('installed_count', 0)}, skipped {result.get('skipped_count', 0)}, failed {result.get('failed_count', 0)}\n",
            f"\nSkill install result: installed {result.get('installed_count', 0)}, skipped {result.get('skipped_count', 0)}, failed {result.get('failed_count', 0)}\n",
        )
    )
    for item in result.get("installed", []):
        _write_stderr(f"  [OK] {item.get('label')} -> {item.get('path')}\n")
    for item in result.get("failed", []):
        _write_stderr(f"  [FAILED] {item.get('label')} -> {item.get('path')}: {item.get('error')}\n")


def _run_advanced_setup_prompts(values: dict[str, str], current: dict[str, str], lang: str) -> None:
    _write_stderr(
        _t(
            lang,
            "\n高级模式: 逐项配置底层键。一般用户建议直接使用默认分组向导。\n",
            "\nAdvanced mode: configure low-level keys one by one. Most users should use the grouped wizard.\n",
        )
    )
    prompts = [
        ("XAI_API_URL", "xAI Responses API URL", True),
        ("XAI_API_KEY", "xAI API key", True),
        ("XAI_MODEL", "xAI Responses model", True),
        ("XAI_TOOLS", "xAI Responses tools (web_search,x_search)", True),
        ("OPENAI_COMPATIBLE_API_URL", "OpenAI-compatible API URL", True),
        ("OPENAI_COMPATIBLE_API_KEY", "OpenAI-compatible API key", True),
        ("OPENAI_COMPATIBLE_MODEL", "OpenAI-compatible model", True),
        ("OPENAI_COMPATIBLE_STREAM", "OpenAI-compatible stream mode (true/false)", True),
        ("SMART_SEARCH_VALIDATION_LEVEL", "Validation level (fast/balanced/strict)", True),
        ("SMART_SEARCH_FALLBACK_MODE", "Fallback mode (auto/off)", True),
        ("SMART_SEARCH_MINIMUM_PROFILE", "Minimum profile (standard/off)", True),
        ("EXA_API_KEY", "Exa API key", True),
        ("CONTEXT7_API_KEY", "Context7 API key", True),
        ("ZHIPU_API_KEY", "Zhipu API key", True),
        ("ZHIPU_API_URL", "Zhipu Web Search API URL", True),
        ("ZHIPU_SEARCH_ENGINE", "Zhipu search service (search_std/search_pro/search_pro_sogou/search_pro_quark/custom)", True),
        ("ZHIPU_MCP_API_KEY", "Zhipu Coding Plan MCP API key", True),
        ("ZHIPU_MCP_SEARCH_API_URL", "Zhipu Coding Plan search MCP URL", True),
        ("ZHIPU_MCP_READER_API_URL", "Zhipu Coding Plan reader MCP URL", True),
        ("ZHIPU_MCP_ZREAD_API_URL", "Zhipu Coding Plan zread MCP URL", True),
        ("ZHIPU_MCP_TIMEOUT_SECONDS", "Zhipu Coding Plan MCP timeout seconds", True),
        ("JINA_API_KEY", "Jina API key", True),
        ("JINA_READER_API_URL", "Jina Reader API URL", True),
        ("JINA_RESPOND_WITH", "Jina respond-with mode (optional, e.g. readerlm-v2)", True),
        ("JINA_TIMEOUT_SECONDS", "Jina timeout seconds", True),
        ("TAVILY_API_URL", "Tavily API URL", True),
        ("TAVILY_API_KEY", "Tavily API key", True),
        ("FIRECRAWL_API_URL", "Firecrawl API URL", True),
        ("FIRECRAWL_API_KEY", "Firecrawl API key", True),
        ("ANYSEARCH_API_URL", "AnySearch MCP API URL", True),
        ("ANYSEARCH_API_KEY", "AnySearch API key", True),
        ("ANYSEARCH_TIMEOUT_SECONDS", "AnySearch timeout seconds", True),
    ]
    for key, label, optional in prompts:
        if values[key]:
            continue
        value = _prompt_value(key, label, current.get(key, ""), optional=optional, lang=lang)
        if key == "TAVILY_API_URL":
            value = _normalize_tavily_api_url(value)
        elif key == "FIRECRAWL_API_URL":
            value = _normalize_firecrawl_api_url(value)
        elif key == "ZHIPU_API_URL":
            value = _normalize_zhipu_api_url(value)
        elif key == "JINA_READER_API_URL":
            value = _normalize_jina_reader_api_url(value)
        elif key in {"ZHIPU_MCP_SEARCH_API_URL", "ZHIPU_MCP_READER_API_URL", "ZHIPU_MCP_ZREAD_API_URL"}:
            value = _normalize_custom_base_url(value)
        values[key] = value


async def _run_async(args: argparse.Namespace) -> int:
    if args.command == "search":
        search_kwargs = {
            "platform": args.platform,
            "model": args.model,
            "extra_sources": args.extra_sources,
            "validation": args.validation,
            "fallback": args.fallback,
            "providers": args.providers,
        }
        if args.stream is not None:
            search_kwargs["stream"] = args.stream
        try:
            data = await asyncio.wait_for(
                service.search(args.query, **search_kwargs),
                timeout=args.timeout,
            )
        except asyncio.TimeoutError:
            data = _search_timeout_result(args.query, args.timeout, search_kwargs)
            return _print_result("search", data, args.format, args.output)
        return _print_result("search", data, args.format, args.output)
    if args.command == "fetch":
        data = await service.fetch(args.url)
        return _print_result("fetch", data, args.format, args.output)
    if args.command == "map":
        data = await service.map_site(
            args.url,
            instructions=args.instructions,
            max_depth=args.max_depth,
            max_breadth=args.max_breadth,
            limit=args.limit,
            timeout=args.timeout,
        )
        return _print_result("map", data, args.format, args.output)
    if args.command == "exa-search":
        data = await service.exa_search(
            args.query,
            num_results=args.num_results,
            search_type=args.search_type,
            include_text=args.include_text,
            include_highlights=args.include_highlights,
            start_published_date=args.start_published_date,
            include_domains=args.include_domains,
            exclude_domains=args.exclude_domains,
            category=args.category,
        )
        return _print_result("exa-search", data, args.format, args.output)
    if args.command == "exa-similar":
        data = await service.exa_find_similar(args.url, num_results=args.num_results)
        return _print_result("exa-similar", data, args.format, args.output)
    if args.command == "zhipu-search":
        data = await service.zhipu_search(
            args.query,
            count=args.count,
            search_engine=args.search_engine,
            search_recency_filter=args.search_recency_filter,
            search_domain_filter=args.search_domain_filter,
            content_size=args.content_size,
        )
        return _print_result("zhipu-search", data, args.format, args.output)
    if args.command == "zhipu-mcp-search":
        data = await service.zhipu_mcp_search(args.query, count=args.count)
        return _print_result("zhipu-mcp-search", data, args.format, args.output)
    if args.command == "zhipu-mcp-reader":
        data = await service.zhipu_mcp_reader(args.url)
        return _print_result("zhipu-mcp-reader", data, args.format, args.output)
    if args.command == "zhipu-mcp-search-doc":
        data = await service.zhipu_mcp_search_doc(args.repo, args.query, max_results=args.max_results)
        return _print_result("zhipu-mcp-search-doc", data, args.format, args.output)
    if args.command == "zhipu-mcp-repo-structure":
        data = await service.zhipu_mcp_repo_structure(args.repo, ref=args.ref)
        return _print_result("zhipu-mcp-repo-structure", data, args.format, args.output)
    if args.command == "zhipu-mcp-read-file":
        data = await service.zhipu_mcp_read_file(args.repo, args.path, ref=args.ref)
        return _print_result("zhipu-mcp-read-file", data, args.format, args.output)
    if args.command == "anysearch-domains":
        data = await service.anysearch_domains(args.domain)
        return _print_result("anysearch-domains", data, args.format, args.output)
    if args.command == "anysearch-search":
        data = await service.anysearch_search(
            args.query,
            domain=args.domain,
            sub_domain=args.sub_domain,
            max_results=args.max_results,
        )
        return _print_result("anysearch-search", data, args.format, args.output)
    if args.command == "anysearch-extract":
        data = await service.anysearch_extract(args.url, max_length=args.max_length)
        return _print_result("anysearch-extract", data, args.format, args.output)
    if args.command == "anysearch-batch":
        data = await service.anysearch_batch(args.queries, max_results=args.max_results)
        return _print_result("anysearch-batch", data, args.format, args.output)
    if args.command == "context7-library":
        data = await service.context7_library(args.name, args.query)
        return _print_result("context7-library", data, args.format, args.output)
    if args.command == "context7-docs":
        data = await service.context7_docs(args.library_id, args.query)
        return _print_result("context7-docs", data, args.format, args.output)
    if args.command == "deep":
        data = service.build_deep_research_plan(
            args.query,
            budget=args.budget,
            evidence_dir=args.evidence_dir,
        )
        return _print_result("deep", data, args.format, args.output)
    if args.command == "research":
        data = await service.research(
            args.query,
            budget=args.budget,
            evidence_dir=args.evidence_dir,
            fallback=args.fallback,
        )
        return _print_result("research", data, args.format, args.output)
    if args.command == "smoke":
        data = await service.smoke(args.mode)
        return _print_result("smoke", data, args.format, args.output)
    if args.command == "doctor":
        data = await service.doctor()
        return _print_result("doctor", data, args.format, args.output)
    if args.command == "diagnose":
        if args.diagnose_target == "openai-compatible":
            data = await service.diagnose_openai_compatible(timeout_seconds=args.timeout)
            return _print_result("diagnose", data, args.format, args.output)
        return _print_result(
            "diagnose",
            {"ok": False, "error_type": "parameter_error", "error": f"Unknown diagnose target: {args.diagnose_target}"},
            args.format,
            args.output,
        )
    return EXIT_PARAMETER_ERROR


def _run_model(args: argparse.Namespace) -> int:
    if args.model_command == "set":
        data = service.set_model(args.model)
    elif args.model_command == "current":
        data = service.current_model()
    else:
        data = {"ok": False, "error_type": "parameter_error", "error": "Unknown model command"}
    return _print_result("model", data, args.format, args.output)


def _run_config(args: argparse.Namespace) -> int:
    if args.config_command == "path":
        data = service.config_path()
    elif args.config_command == "list":
        data = service.config_list(show_secrets=False)
    elif args.config_command == "set":
        data = service.config_set(args.key, args.value)
    elif args.config_command == "unset":
        data = service.config_unset(args.key)
    else:
        data = {"ok": False, "error_type": "parameter_error", "error": "Unknown config command"}
    return _print_result("config", data, args.format, args.output)


def _skill_targets_from_args(args: argparse.Namespace) -> list[str]:
    if getattr(args, "all", False):
        return [target.target_id for target in SKILL_TARGETS]
    raw = getattr(args, "targets", "") or ""
    if raw:
        return parse_skill_targets(raw)
    return list(DEFAULT_SKILL_TARGET_IDS)


def _run_skills(args: argparse.Namespace) -> int:
    try:
        target_ids = _skill_targets_from_args(args)
    except SkillInstallError as e:
        data = {"ok": False, "error_type": "parameter_error", "error": str(e), "selected": []}
        return _print_result("skills", data, args.format, args.output)

    if args.skills_command == "status":
        try:
            data = status_skill_targets(target_ids, project_root=args.skills_root)
        except SkillInstallError as e:
            data = {"ok": False, "error_type": "runtime_error", "error": str(e), "selected": target_ids}
        return _print_result("skills", data, args.format, args.output)

    if args.skills_command == "update":
        try:
            data = install_skill_targets(target_ids, project_root=args.skills_root)
        except SkillInstallError as e:
            data = {"ok": False, "error_type": "runtime_error", "error": str(e), "selected": target_ids}
        return _print_result("skills", data, args.format, args.output)

    data = {"ok": False, "error_type": "parameter_error", "error": "Unknown skills command", "selected": target_ids}
    return _print_result("skills", data, args.format, args.output)


def _run_setup(args: argparse.Namespace) -> int:
    try:
        explicit_skill_targets = parse_skill_targets(args.install_skills) if args.install_skills else []
    except SkillInstallError as e:
        data = {"ok": False, "error_type": "parameter_error", "error": str(e), "config_file": service.config_path()["config_file"]}
        return _print_result("setup", data, args.format, args.output)

    values = {
        "XAI_API_URL": args.xai_api_url,
        "XAI_API_KEY": args.xai_api_key,
        "XAI_MODEL": args.xai_model,
        "XAI_TOOLS": args.xai_tools_explicit,
        "OPENAI_COMPATIBLE_API_URL": args.openai_compatible_api_url,
        "OPENAI_COMPATIBLE_API_KEY": args.openai_compatible_api_key,
        "OPENAI_COMPATIBLE_MODEL": args.openai_compatible_model,
        "OPENAI_COMPATIBLE_STREAM": args.openai_compatible_stream,
        "SMART_SEARCH_VALIDATION_LEVEL": args.validation_level,
        "SMART_SEARCH_FALLBACK_MODE": args.fallback_mode,
        "SMART_SEARCH_MINIMUM_PROFILE": args.minimum_profile,
        "EXA_API_KEY": args.exa_key,
        "CONTEXT7_API_KEY": args.context7_key,
        "ZHIPU_API_KEY": args.zhipu_key,
        "ZHIPU_API_URL": _normalize_zhipu_api_url(args.zhipu_api_url),
        "ZHIPU_SEARCH_ENGINE": args.zhipu_search_engine,
        "ZHIPU_MCP_API_KEY": args.zhipu_mcp_key,
        "ZHIPU_MCP_SEARCH_API_URL": _normalize_custom_base_url(args.zhipu_mcp_search_api_url),
        "ZHIPU_MCP_READER_API_URL": _normalize_custom_base_url(args.zhipu_mcp_reader_api_url),
        "ZHIPU_MCP_ZREAD_API_URL": _normalize_custom_base_url(args.zhipu_mcp_zread_api_url),
        "ZHIPU_MCP_TIMEOUT_SECONDS": args.zhipu_mcp_timeout,
        "JINA_API_KEY": args.jina_key,
        "JINA_READER_API_URL": _normalize_jina_reader_api_url(args.jina_reader_api_url),
        "JINA_RESPOND_WITH": args.jina_respond_with,
        "JINA_TIMEOUT_SECONDS": args.jina_timeout,
        "TAVILY_API_URL": _normalize_tavily_flag_api_url(args.tavily_api_url, args.tavily_key),
        "TAVILY_API_KEY": args.tavily_key,
        "FIRECRAWL_API_URL": _normalize_firecrawl_api_url(args.firecrawl_api_url),
        "FIRECRAWL_API_KEY": args.firecrawl_key,
        "ANYSEARCH_API_URL": _normalize_custom_base_url(args.anysearch_api_url),
        "ANYSEARCH_API_KEY": args.anysearch_key,
        "ANYSEARCH_TIMEOUT_SECONDS": args.anysearch_timeout,
    }

    lang = args.lang if args.lang in {"zh", "en"} else "zh"
    selected_skill_targets: list[str] = list(explicit_skill_targets)

    if not args.non_interactive:
        current = service.config_list(show_secrets=True)["values"]
        _write_setup_banner(args.lang if args.lang in {"zh", "en"} else "zh")
        lang = _select_setup_language(args.lang)
        if args.advanced:
            _run_advanced_setup_prompts(values, current, lang)
        else:
            skill_targets_for_prompt = selected_skill_targets if not args.skip_skills and not selected_skill_targets else None
            _run_guided_setup_prompts(values, current, lang, skill_targets=skill_targets_for_prompt, show_banner=False)

    saved: dict[str, str] = {}
    for key, value in values.items():
        if value:
            result = service.config_set(key, value)
            saved[key] = result.get("value", "")

    skill_result = None
    if not args.skip_skills and selected_skill_targets:
        skill_result = install_skill_targets(selected_skill_targets, project_root=args.skills_root)

    ok = True if skill_result is None else bool(skill_result.get("ok", False))
    data = {"ok": ok, "config_file": service.config_path()["config_file"], "saved": saved}
    if skill_result is not None:
        data["skills"] = skill_result
        if not skill_result.get("ok", False):
            data["error_type"] = "runtime_error"
            data["error"] = "One or more skill targets failed to install."
    if not args.non_interactive:
        current_after = service.config_list(show_secrets=True)["values"]
        final_values = _merge_setup_values(current_after, values)
        final_status = _setup_status_from_values(final_values)
        _write_stderr(_t(lang, "\n保存完成。\n", "\nSaved.\n"))
        if skill_result is not None:
            _write_skill_install_summary(skill_result, lang)
        _write_setup_status(final_status, lang, final=True)
        missing = [capability for capability in ("main_search", "docs_search", "web_fetch") if not final_status[capability]["ok"]]
        if missing:
            _write_stderr(
                _t(
                    lang,
                    "\n当前配置尚未满足 standard 最低配置。\nsearch / doctor 会 fail closed，不会假装可用。\n",
                    "\nThe current config does not satisfy the standard minimum profile.\nsearch / doctor will fail closed instead of pretending to work.\n",
                )
            )
        else:
            _write_stderr(
                _t(
                    lang,
                    "\n下一步建议:\n  smart-search doctor --format json\n  smart-search smoke --mock --format json\n",
                    "\nNext steps:\n  smart-search doctor --format json\n  smart-search smoke --mock --format json\n",
                )
            )
        data["minimum_profile_ok"] = not missing
        data["minimum_profile_missing"] = missing
        data["capability_status"] = final_status
    return _print_result("setup", data, args.format, args.output)


def _run_regression() -> int:
    root = Path(__file__).resolve().parents[2]
    patterns = [
        "tests/test_cli.py",
        "tests/test_service.py",
        "tests/test_providers_new.py",
        "tests/test_jina_provider.py",
        "tests/test_zhipu_mcp_provider.py",
        "tests/test_smoke.py",
        "tests/test_regression.py",
        "tests/test_release_workflow.py",
    ]
    if not all((root / pattern).exists() for pattern in patterns):
        print("Packaged install has no test files; running mock smoke regression instead.", file=sys.stderr)
        return asyncio.run(_run_regression_smoke_fallback())
    cmd = [sys.executable, "-m", "pytest", *patterns]
    return subprocess.call(cmd, cwd=str(root))


async def _run_regression_smoke_fallback() -> int:
    data = await service.smoke("mock")
    return _print_result("smoke", data, "json")


def build_parser() -> argparse.ArgumentParser:
    parser = SmartSearchArgumentParser(
        prog="smart-search",
        description="Smart Search CLI for AI-agent web research.",
    )
    parser.add_argument("-v", "--v", "--version", action="version", version=f"%(prog)s {_get_version()}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=SmartSearchArgumentParser)

    search_parser = sub.add_parser(
        "search", aliases=COMMAND_ALIASES["search"], help="Run OpenAI-compatible web search."
    )
    search_parser.set_defaults(command="search")
    search_parser.add_argument("query")
    search_parser.add_argument("--platform", default="")
    search_parser.add_argument("--model", default="")
    search_parser.add_argument("--extra-sources", type=int, default=0)
    search_parser.add_argument("--validation", choices=["fast", "balanced", "strict"], default="")
    search_parser.add_argument("--fallback", choices=["auto", "off"], default="")
    search_parser.add_argument("--providers", default="auto")
    stream_group = search_parser.add_mutually_exclusive_group()
    stream_group.add_argument("--stream", dest="stream", action="store_true", default=None, help="Use stream=true for OpenAI-compatible main search.")
    stream_group.add_argument("--no-stream", dest="stream", action="store_false", help="Force stream=false for OpenAI-compatible main search.")
    search_parser.add_argument("--timeout", type=float, default=90, metavar="SECONDS", help="Hard timeout in seconds.")
    _add_format_args(search_parser)

    fetch_parser = sub.add_parser("fetch", aliases=COMMAND_ALIASES["fetch"], help="Fetch a URL as markdown.")
    fetch_parser.set_defaults(command="fetch")
    fetch_parser.add_argument("url")
    _add_format_args(fetch_parser)

    map_parser = sub.add_parser("map", aliases=COMMAND_ALIASES["map"], help="Map a website structure.")
    map_parser.set_defaults(command="map")
    map_parser.add_argument("url")
    map_parser.add_argument("--instructions", default="")
    map_parser.add_argument("--max-depth", type=int, default=1)
    map_parser.add_argument("--max-breadth", type=int, default=20)
    map_parser.add_argument("--limit", type=int, default=50)
    map_parser.add_argument("--timeout", type=int, default=150)
    _add_format_args(map_parser)

    exa_parser = sub.add_parser(
        "exa-search", aliases=COMMAND_ALIASES["exa-search"], help="Run Exa source-first search."
    )
    exa_parser.set_defaults(command="exa-search")
    exa_parser.add_argument("query")
    exa_parser.add_argument("--num-results", type=int, default=5)
    exa_parser.add_argument("--search-type", choices=["neural", "keyword", "auto"], default="neural")
    exa_parser.add_argument("--include-text", action="store_true")
    exa_parser.add_argument("--include-highlights", action="store_true")
    exa_parser.add_argument("--start-published-date", default="")
    exa_parser.add_argument("--include-domains", nargs="+", default="")
    exa_parser.add_argument("--exclude-domains", nargs="+", default="")
    exa_parser.add_argument("--category", default="")
    _add_format_args(exa_parser)

    similar_parser = sub.add_parser(
        "exa-similar", aliases=COMMAND_ALIASES["exa-similar"], help="Find pages similar to a URL with Exa."
    )
    similar_parser.set_defaults(command="exa-similar")
    similar_parser.add_argument("url")
    similar_parser.add_argument("--num-results", type=int, default=5)
    _add_format_args(similar_parser)

    zhipu_parser = sub.add_parser(
        "zhipu-search", aliases=COMMAND_ALIASES["zhipu-search"], help="Run Zhipu Web Search source-first search."
    )
    zhipu_parser.set_defaults(command="zhipu-search")
    zhipu_parser.add_argument("query")
    zhipu_parser.add_argument("--count", type=int, default=10)
    zhipu_parser.add_argument("--search-engine", default="")
    zhipu_parser.add_argument("--search-recency-filter", default="noLimit")
    zhipu_parser.add_argument("--search-domain-filter", default="")
    zhipu_parser.add_argument("--content-size", choices=["medium", "high"], default="medium")
    _add_format_args(zhipu_parser)

    zhipu_mcp_search_parser = sub.add_parser(
        "zhipu-mcp-search",
        aliases=COMMAND_ALIASES["zhipu-mcp-search"],
        help="Run Zhipu Coding Plan Remote MCP web_search_prime.",
    )
    zhipu_mcp_search_parser.set_defaults(command="zhipu-mcp-search")
    zhipu_mcp_search_parser.add_argument("query")
    zhipu_mcp_search_parser.add_argument("--count", type=int, default=5)
    _add_format_args(zhipu_mcp_search_parser)

    zhipu_mcp_reader_parser = sub.add_parser(
        "zhipu-mcp-reader",
        aliases=COMMAND_ALIASES["zhipu-mcp-reader"],
        help="Run Zhipu Coding Plan Remote MCP webReader.",
    )
    zhipu_mcp_reader_parser.set_defaults(command="zhipu-mcp-reader")
    zhipu_mcp_reader_parser.add_argument("url")
    _add_format_args(zhipu_mcp_reader_parser)

    zhipu_mcp_search_doc_parser = sub.add_parser(
        "zhipu-mcp-search-doc",
        aliases=COMMAND_ALIASES["zhipu-mcp-search-doc"],
        help="Search repository docs through Zhipu Coding Plan zread MCP.",
    )
    zhipu_mcp_search_doc_parser.set_defaults(command="zhipu-mcp-search-doc")
    zhipu_mcp_search_doc_parser.add_argument("repo")
    zhipu_mcp_search_doc_parser.add_argument("query")
    zhipu_mcp_search_doc_parser.add_argument("--max-results", type=int, default=5)
    _add_format_args(zhipu_mcp_search_doc_parser)

    zhipu_mcp_repo_structure_parser = sub.add_parser(
        "zhipu-mcp-repo-structure",
        aliases=COMMAND_ALIASES["zhipu-mcp-repo-structure"],
        help="Read repository structure through Zhipu Coding Plan zread MCP.",
    )
    zhipu_mcp_repo_structure_parser.set_defaults(command="zhipu-mcp-repo-structure")
    zhipu_mcp_repo_structure_parser.add_argument("repo")
    zhipu_mcp_repo_structure_parser.add_argument("--ref", default="")
    _add_format_args(zhipu_mcp_repo_structure_parser)

    zhipu_mcp_read_file_parser = sub.add_parser(
        "zhipu-mcp-read-file",
        aliases=COMMAND_ALIASES["zhipu-mcp-read-file"],
        help="Read a repository file through Zhipu Coding Plan zread MCP.",
    )
    zhipu_mcp_read_file_parser.set_defaults(command="zhipu-mcp-read-file")
    zhipu_mcp_read_file_parser.add_argument("repo")
    zhipu_mcp_read_file_parser.add_argument("path")
    zhipu_mcp_read_file_parser.add_argument("--ref", default="")
    _add_format_args(zhipu_mcp_read_file_parser)

    anysearch_domains_parser = sub.add_parser(
        "anysearch-domains",
        aliases=COMMAND_ALIASES["anysearch-domains"],
        help="List AnySearch vertical search domains.",
    )
    anysearch_domains_parser.set_defaults(command="anysearch-domains")
    anysearch_domains_parser.add_argument("domain", nargs="?", default="")
    _add_format_args(anysearch_domains_parser)

    anysearch_search_parser = sub.add_parser(
        "anysearch-search",
        aliases=COMMAND_ALIASES["anysearch-search"],
        help="Run experimental AnySearch vertical/general search.",
    )
    anysearch_search_parser.set_defaults(command="anysearch-search")
    anysearch_search_parser.add_argument("query")
    anysearch_search_parser.add_argument("--domain", default="")
    anysearch_search_parser.add_argument("--sub-domain", default="")
    anysearch_search_parser.add_argument("--max-results", type=int, default=5)
    _add_format_args(anysearch_search_parser)

    anysearch_extract_parser = sub.add_parser(
        "anysearch-extract",
        aliases=COMMAND_ALIASES["anysearch-extract"],
        help="Extract a URL through AnySearch experimental extract.",
    )
    anysearch_extract_parser.set_defaults(command="anysearch-extract")
    anysearch_extract_parser.add_argument("url")
    anysearch_extract_parser.add_argument("--max-length", type=int, default=20000)
    _add_format_args(anysearch_extract_parser)

    anysearch_batch_parser = sub.add_parser(
        "anysearch-batch",
        aliases=COMMAND_ALIASES["anysearch-batch"],
        help="Run up to 5 AnySearch queries in parallel.",
    )
    anysearch_batch_parser.set_defaults(command="anysearch-batch")
    anysearch_batch_parser.add_argument("queries", nargs="+")
    anysearch_batch_parser.add_argument("--max-results", type=int, default=3)
    _add_format_args(anysearch_batch_parser)

    context7_library_parser = sub.add_parser(
        "context7-library",
        aliases=COMMAND_ALIASES["context7-library"],
        help="Resolve Context7 library candidates.",
    )
    context7_library_parser.set_defaults(command="context7-library")
    context7_library_parser.add_argument("name")
    context7_library_parser.add_argument("query", nargs="?", default="")
    _add_format_args(context7_library_parser)

    context7_docs_parser = sub.add_parser(
        "context7-docs",
        aliases=COMMAND_ALIASES["context7-docs"],
        help="Fetch Context7 docs for a library.",
    )
    context7_docs_parser.set_defaults(command="context7-docs")
    context7_docs_parser.add_argument("library_id")
    context7_docs_parser.add_argument("query")
    _add_format_args(context7_docs_parser)

    deep_parser = sub.add_parser(
        "deep",
        aliases=COMMAND_ALIASES["deep"],
        help="Create an offline Deep Research plan without calling providers.",
    )
    deep_parser.set_defaults(command="deep")
    deep_parser.add_argument("query")
    deep_parser.add_argument("--budget", choices=["quick", "standard", "deep"], default="standard")
    deep_parser.add_argument("--evidence-dir", default="")
    _add_format_args(deep_parser)

    research_parser = sub.add_parser(
        "research",
        aliases=COMMAND_ALIASES["research"],
        help="Run live Deep Research with provider-advantage routing and evidence-only synthesis.",
    )
    research_parser.set_defaults(command="research")
    research_parser.add_argument("query")
    research_parser.add_argument("--budget", choices=["quick", "standard", "deep"], default="deep")
    research_parser.add_argument("--evidence-dir", default="")
    research_parser.add_argument("--fallback", choices=["auto", "off"], default="auto")
    _add_format_args(research_parser)

    smoke_parser = sub.add_parser(
        "smoke", aliases=COMMAND_ALIASES["smoke"], help="Run provider routing and fallback smoke checks."
    )
    smoke_parser.set_defaults(command="smoke")
    smoke_mode = smoke_parser.add_mutually_exclusive_group()
    smoke_mode.add_argument("--mode", choices=["mock", "live"], default=None)
    smoke_mode.add_argument("--mock", dest="mode", action="store_const", const="mock", help="Run offline mock smoke checks.")
    smoke_mode.add_argument("--live", dest="mode", action="store_const", const="live", help="Run live provider smoke checks.")
    smoke_parser.set_defaults(mode="mock")
    _add_format_args(smoke_parser)

    doctor_parser = sub.add_parser(
        "doctor", aliases=COMMAND_ALIASES["doctor"], help="Show masked configuration and connection checks."
    )
    doctor_parser.set_defaults(command="doctor")
    _add_format_args(doctor_parser)

    diagnose_parser = sub.add_parser(
        "diagnose",
        aliases=COMMAND_ALIASES["diagnose"],
        help="Run focused troubleshooting checks for a provider.",
    )
    diagnose_parser.set_defaults(command="diagnose")
    diagnose_parser.add_argument("diagnose_target", choices=["openai-compatible"])
    diagnose_parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS", help="Per search-shape probe timeout in seconds.")
    diagnose_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    diagnose_parser.add_argument("--output", default="", help="Write rendered output to a file.")

    model_parser = sub.add_parser(
        "model",
        aliases=COMMAND_ALIASES["model"],
        help="Inspect explicit provider models; use config set XAI_MODEL or OPENAI_COMPATIBLE_MODEL to change them.",
    )
    model_parser.set_defaults(command="model")
    model_sub = model_parser.add_subparsers(dest="model_command", required=True, parser_class=SmartSearchArgumentParser)
    model_set = model_sub.add_parser("set", aliases=MODEL_COMMAND_ALIASES["set"])
    model_set.set_defaults(model_command="set")
    model_set.add_argument("model")
    _add_format_args(model_set)
    model_current = model_sub.add_parser("current", aliases=MODEL_COMMAND_ALIASES["current"])
    model_current.set_defaults(model_command="current")
    _add_format_args(model_current)

    skills_parser = sub.add_parser(
        "skills",
        aliases=COMMAND_ALIASES["skills"],
        help="Inspect or update installed smart-search-cli skills.",
    )
    skills_parser.set_defaults(command="skills")
    skills_sub = skills_parser.add_subparsers(dest="skills_command", required=True, parser_class=SmartSearchArgumentParser)
    skills_status = skills_sub.add_parser("status", aliases=SKILLS_COMMAND_ALIASES["status"], help="Compare bundled and installed skill files.")
    skills_status.set_defaults(skills_command="status")
    skills_status.add_argument(
        "--targets",
        default=",".join(DEFAULT_SKILL_TARGET_IDS),
        help="Comma-separated AI tool targets, e.g. codex,claude,cursor,hermes.",
    )
    skills_status.add_argument("--all", action="store_true", help="Check every known skill target.")
    skills_status.add_argument(
        "--skills-root",
        default="",
        help="Advanced override for the user-level skill root; defaults to the current user's home directory.",
    )
    _add_format_args(skills_status)
    skills_update = skills_sub.add_parser("update", aliases=SKILLS_COMMAND_ALIASES["update"], help="Overwrite selected installed skill files with bundled assets.")
    skills_update.set_defaults(skills_command="update")
    skills_update.add_argument(
        "--targets",
        default=",".join(DEFAULT_SKILL_TARGET_IDS),
        help="Comma-separated AI tool targets, e.g. codex,claude,cursor,hermes.",
    )
    skills_update.add_argument("--all", action="store_true", help="Update every known skill target.")
    skills_update.add_argument(
        "--skills-root",
        default="",
        help="Advanced override for the user-level skill root; defaults to the current user's home directory.",
    )
    _add_format_args(skills_update)

    setup_parser = sub.add_parser(
        "setup", aliases=COMMAND_ALIASES["setup"], help="Interactively save local provider configuration."
    )
    setup_parser.set_defaults(command="setup")
    setup_parser.add_argument("--non-interactive", action="store_true", help="Only save values passed as flags.")
    setup_parser.add_argument("--lang", choices=["zh", "en"], default="", help="Interactive setup language.")
    setup_parser.add_argument("--advanced", action="store_true", help="Show every low-level config key in interactive setup.")
    setup_parser.add_argument("--skip-skills", action="store_true", help="Skip user-level smart-search-cli skill installation.")
    setup_parser.add_argument(
        "--install-skills",
        default="",
        help="Comma-separated AI tool targets for smart-search-cli skill installation, e.g. codex,claude,cursor,hermes.",
    )
    setup_parser.add_argument(
        "--skills-root",
        default="",
        help="Advanced override for the user-level skill root; defaults to the current user's home directory.",
    )
    setup_parser.add_argument("--xai-api-url", default="", help="Save XAI_API_URL.")
    setup_parser.add_argument("--xai-api-key", default="", help="Save XAI_API_KEY.")
    setup_parser.add_argument("--xai-model", default="", help="Save XAI_MODEL.")
    setup_parser.add_argument("--xai-tools-explicit", default="", help="Save XAI_TOOLS.")
    setup_parser.add_argument("--openai-compatible-api-url", default="", help="Save OPENAI_COMPATIBLE_API_URL.")
    setup_parser.add_argument("--openai-compatible-api-key", default="", help="Save OPENAI_COMPATIBLE_API_KEY.")
    setup_parser.add_argument("--openai-compatible-model", default="", help="Save OPENAI_COMPATIBLE_MODEL.")
    setup_parser.add_argument("--openai-compatible-stream", default="", help="Save OPENAI_COMPATIBLE_STREAM.")
    setup_parser.add_argument("--validation-level", default="", help="Save SMART_SEARCH_VALIDATION_LEVEL.")
    setup_parser.add_argument("--fallback-mode", default="", help="Save SMART_SEARCH_FALLBACK_MODE.")
    setup_parser.add_argument("--minimum-profile", default="", help="Save SMART_SEARCH_MINIMUM_PROFILE.")
    setup_parser.add_argument("--exa-key", default="", help="Save EXA_API_KEY.")
    setup_parser.add_argument("--context7-key", default="", help="Save CONTEXT7_API_KEY.")
    setup_parser.add_argument("--zhipu-key", default="", help="Save ZHIPU_API_KEY.")
    setup_parser.add_argument("--zhipu-api-url", default="", help="Save ZHIPU_API_URL.")
    setup_parser.add_argument("--zhipu-search-engine", default="", help="Save ZHIPU_SEARCH_ENGINE.")
    setup_parser.add_argument("--zhipu-mcp-key", default="", help="Save ZHIPU_MCP_API_KEY.")
    setup_parser.add_argument("--zhipu-mcp-search-api-url", default="", help="Save ZHIPU_MCP_SEARCH_API_URL.")
    setup_parser.add_argument("--zhipu-mcp-reader-api-url", default="", help="Save ZHIPU_MCP_READER_API_URL.")
    setup_parser.add_argument("--zhipu-mcp-zread-api-url", default="", help="Save ZHIPU_MCP_ZREAD_API_URL.")
    setup_parser.add_argument("--zhipu-mcp-timeout", default="", help="Save ZHIPU_MCP_TIMEOUT_SECONDS.")
    setup_parser.add_argument("--jina-key", default="", help="Save JINA_API_KEY.")
    setup_parser.add_argument("--jina-reader-api-url", default="", help="Save JINA_READER_API_URL.")
    setup_parser.add_argument("--jina-respond-with", default="", help="Save JINA_RESPOND_WITH, e.g. readerlm-v2.")
    setup_parser.add_argument("--jina-timeout", default="", help="Save JINA_TIMEOUT_SECONDS.")
    setup_parser.add_argument("--tavily-api-url", default="", help="Save TAVILY_API_URL.")
    setup_parser.add_argument("--tavily-key", default="", help="Save TAVILY_API_KEY.")
    setup_parser.add_argument("--firecrawl-api-url", default="", help="Save FIRECRAWL_API_URL.")
    setup_parser.add_argument("--firecrawl-key", default="", help="Save FIRECRAWL_API_KEY.")
    setup_parser.add_argument("--anysearch-api-url", default="", help="Save ANYSEARCH_API_URL.")
    setup_parser.add_argument("--anysearch-key", default="", help="Save ANYSEARCH_API_KEY.")
    setup_parser.add_argument("--anysearch-timeout", default="", help="Save ANYSEARCH_TIMEOUT_SECONDS.")
    _add_format_args(setup_parser)

    config_parser = sub.add_parser(
        "config", aliases=COMMAND_ALIASES["config"], help="Read or edit the local Smart Search config file."
    )
    config_parser.set_defaults(command="config")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True, parser_class=SmartSearchArgumentParser)
    config_path = config_sub.add_parser("path", aliases=CONFIG_COMMAND_ALIASES["path"])
    config_path.set_defaults(config_command="path")
    _add_format_args(config_path)
    config_list = config_sub.add_parser("list", aliases=CONFIG_COMMAND_ALIASES["list"])
    config_list.set_defaults(config_command="list")
    _add_format_args(config_list)
    config_set = config_sub.add_parser("set", aliases=CONFIG_COMMAND_ALIASES["set"])
    config_set.set_defaults(config_command="set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    _add_format_args(config_set)
    config_unset = config_sub.add_parser("unset", aliases=CONFIG_COMMAND_ALIASES["unset"])
    config_unset.set_defaults(config_command="unset")
    config_unset.add_argument("key")
    _add_format_args(config_unset)

    regression_parser = sub.add_parser(
        "regression", aliases=COMMAND_ALIASES["regression"], help="Run offline CLI regression tests."
    )
    regression_parser.set_defaults(command="regression")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "regression":
            return _run_regression()
        if args.command == "setup":
            return _run_setup(args)
        if args.command == "skills":
            return _run_skills(args)
        if args.command == "config":
            return _run_config(args)
        if args.command == "model":
            return _run_model(args)
        return asyncio.run(_run_async(args))
    except KeyboardInterrupt:
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
