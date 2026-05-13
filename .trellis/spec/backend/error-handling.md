# Error Handling

> Error and result contracts for CLI, service, and provider code.

---

## Overview

User-facing service functions return dictionaries with an `ok` boolean and, on failure, `error_type` plus `error`. The CLI maps `error_type` to process exit codes in `src/smart_search/cli.py`.

Canonical exit codes:

```python
EXIT_OK = 0
EXIT_PARAMETER_ERROR = 2
EXIT_CONFIG_ERROR = 3
EXIT_NETWORK_ERROR = 4
EXIT_RUNTIME_ERROR = 5
```

Keep this mapping stable. Tests in `tests/test_cli.py` assert config and network failures.

---

## Error Types

Use these public `error_type` values for service results:

| Error type | Meaning | CLI exit |
|---|---|---|
| `parameter_error` | Invalid argument, invalid config value, unsupported option | 2 |
| `config_error` | Required provider key or endpoint is missing | 3 |
| `network_error` | Timeout, HTTP error, provider unavailable, empty external result | 4 |
| `evidence_error` | Strict validation could not produce sources | 4 |
| `runtime_error` | Unexpected local failure | 5 |
| `parse_error` | External response could not be parsed when no narrower type exists | 5 unless mapped |

When adding a new error type, update `_exit_code()` in `src/smart_search/cli.py` and add CLI tests.

---

## Error Handling Patterns

Service functions should catch expected provider/config failures and return result dictionaries. They should not let expected user-facing failures bubble to `main()`.

Example from `search()` behavior:

```python
if validation_level not in config._ALLOWED_VALIDATION_LEVELS:
    return _empty_search_result(start, session_id, query, "parameter_error", str(e))

if not minimum.get("ok"):
    return _empty_search_result(start, session_id, query, "config_error", ...)
```

Provider-level HTTP failures can raise inside provider classes when service code needs fallback tracking. `service.search()` catches provider exceptions, converts them to attempt records, and tries the next configured main provider unless fallback is off.

For simple direct provider commands such as Exa or map, return a dictionary with `ok: False`, `error_type`, and `error` instead of raising for missing API keys.

---

## API Error Responses

Search results must preserve this public shape on both success and failure:

```python
{
    "ok": bool,
    "error_type": str,
    "error": str,
    "session_id": str,
    "query": str,
    "primary_api_mode": str,
    "content": str,
    "sources": list[dict],
    "sources_count": int,
    "primary_sources": list[dict],
    "primary_sources_count": int,
    "extra_sources": list[dict],
    "extra_sources_count": int,
    "source_warning": str,
    "routing_decision": dict,
    "providers_used": list[str],
    "provider_attempts": list[dict],
    "fallback_used": bool,
    "validation_level": str,
    "elapsed_ms": float,
}
```

Provider attempts use:

```python
{
    "capability": "main_search" | "web_search" | "docs_search" | "web_fetch",
    "provider": str,
    "status": "ok" | "empty" | "error",
    "error_type": str,
    "error": str,
    "elapsed_ms": float,
    "result_count": int,
}
```

`fetch()` success returns `ok`, `url`, `provider`, `content`, `provider_attempts`, `fallback_used`, and `elapsed_ms`. Missing both Tavily and Firecrawl keys is a `config_error`; configured providers that cannot fetch content produce `network_error`.

---

## Common Mistakes

Do not print secrets in error messages, setup prompts, config listings, logs, or test snapshots. Use masking paths from `cli.py` and `config.py`.

Do not collapse all external failures into `runtime_error`. Timeouts, HTTP status failures, empty provider results, and missing keys have distinct user-facing behavior and tests.

Do not return partial search failures without the standard empty fields. Timeout handling in `cli._search_timeout_result()` includes the full search result shape so downstream callers can parse it consistently.

Do not swallow fallback attempt details. When fallback occurs, `provider_attempts`, `providers_used`, and `fallback_used` are part of the contract and are asserted in `tests/test_service.py`.
