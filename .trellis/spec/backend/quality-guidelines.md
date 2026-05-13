# Quality Guidelines

> Code quality, testing, and review standards for backend and CLI work.

---

## Overview

This project is contract-heavy. Public CLI output, exit codes, provider routing, config precedence, fallback behavior, and source parsing are all treated as executable contracts. When changing behavior, update or add regression tests in the same change.

The package targets Python 3.10+. It uses stdlib typing syntax such as `dict[str, Any]`, async service functions, `httpx`, and `pytest` plus `pytest-asyncio`.

---

## Forbidden Patterns

Do not bypass `service.py` from CLI commands for network behavior. CLI code should parse arguments and render service results; service/provider modules should perform work.

Do not introduce global mutable config outside `Config`. Configuration precedence is environment first, then config file, then defaults.

Do not create repository-root runtime files during tests. Config and log locations must be isolated through monkeypatching or `SMART_SEARCH_CONFIG_DIR`.

Do not print secrets. Config list and setup flows must mask API keys and private URL defaults.

Do not hand-roll source parsing at call sites. Use `split_answer_and_sources()`, `merge_sources()`, and helpers in `src/smart_search/sources.py`.

Do not remove command aliases or result fields without migration tests. `tests/test_cli.py` asserts aliases, help output, and command contracts.

---

## Required Patterns

Service result functions must include stable fields even on failure. Search failures should use `_empty_search_result()` or `_primary_search_error_result()` so callers always receive parseable output.

Network code should use `httpx.AsyncClient` with explicit timeouts. Retryable provider calls should use tenacity with retry predicates limited to timeout/network errors and retryable HTTP statuses.

Provider results should be normalized before merging into CLI/service output. Source dictionaries should include at minimum `url` and `provider` when provider provenance is known; optional fields include `title`, `description`, `published_date`, and `source`.

Fallback behavior must record attempts. Add or preserve `provider_attempts`, `providers_used`, `fallback_used`, and `routing_decision` fields when a command can call more than one provider.

Config changes must touch all relevant surfaces:
- `Config._CONFIG_KEYS`
- property or parser method on `Config`
- setup/config CLI path if user-facing
- service validation or provider construction
- tests for env override, config-file persistence, masking, and invalid values

---

## Testing Requirements

Run the Python suite for most backend changes:

```bash
python -m pytest
```

The npm wrapper's package-level test command runs Python install/test, wrapper help, and dry-run packaging:

```bash
npm test
```

Use focused tests during iteration, but run the full relevant suite before finishing a task that changes CLI contracts, provider contracts, config, packaging, or source parsing.

Expected test placement:
- CLI parser, aliases, rendering, setup, exit codes: `tests/test_cli.py`
- service orchestration, provider fallback, result contracts: `tests/test_service.py`
- source parsing and cleanup: `tests/test_sources.py`
- provider payloads, retries, response parsing: provider-specific test files
- config directory behavior: `tests/test_config_dir_override.py`
- packaging and skill contracts: `tests/test_regression.py`

Tests should monkeypatch network calls and config paths. Do not require live API keys for normal regression tests. Live smoke behavior should degrade safely when fallback providers exist.

---

## Code Review Checklist

Before accepting a backend/CLI change, verify:
- Public result dictionaries still include required fields on success and failure.
- CLI exit codes still match `error_type`.
- stdout remains machine-readable; human prompts and warnings use stderr.
- Secrets and private URLs are masked.
- Provider fallback attempts are visible in `provider_attempts`.
- Tests isolate config and do not touch the developer's real home config.
- Async provider calls have explicit timeouts and bounded retries.
- npm wrapper changes still delegate to `python -m smart_search.cli` and preserve exit status.

---

## Example Contract Test

When changing search fallback behavior, assert both user-visible output and diagnostics:

```python
result = await service.search("what is example")

assert result["ok"] is True
assert result["fallback_used"] is True
assert [a["provider"] for a in result["provider_attempts"][:2]] == [
    "xAI Responses",
    "OpenAI-compatible",
]
assert result["routing_decision"]["main_search_chain"] == [
    "xai-responses",
    "openai-compatible",
]
```
