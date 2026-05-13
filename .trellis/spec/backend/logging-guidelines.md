# Logging Guidelines

> Logging conventions for the Python CLI package.

---

## Overview

Logging is intentionally quiet by default. `src/smart_search/logger.py` configures a `smart_search` logger with a `NullHandler`, and file logging is enabled only when either debug mode or explicit file logging is enabled.

Use `await log_info(ctx, message, config.debug_enabled)` for optional debug messages in async service/provider flows. The helper logs to the Python logger only in debug mode and forwards to an MCP-style `ctx.info()` when a context object is supplied.

---

## Log Levels

Current project code primarily uses info-level debug logging through `log_info()`. Provider SSL warnings use module loggers and `warning` because disabling TLS verification is a security-relevant event.

Use:
- info: optional debug traces, provider lifecycle messages, non-sensitive request routing notes
- warning: insecure configuration such as `SSL_VERIFY=false`
- error: only for failures that cannot be represented in the returned result contract

Do not add noisy default logs to normal CLI commands. Standard command output must remain machine-readable JSON or Markdown.

---

## Structured Logging

File logs use this format:

```text
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

Daily log files are named `smart_search_YYYYMMDD.log` under `config.log_dir`. Do not create repository-root logs during normal test or CLI execution. Tests isolate config/log state through `SMART_SEARCH_CONFIG_DIR` or monkeypatching.

Service return values, not logs, are the structured observability interface. For search/fetch flows, add details to `provider_attempts`, `routing_decision`, `elapsed_ms`, and `capability_status` rather than relying on logs.

---

## What to Log

Acceptable debug logs:
- selected platform or provider prompt metadata without secrets
- provider operation start/end messages
- empty provider response retry notes
- parsed content only when debug mode is explicitly enabled

Examples in the codebase:
- `OpenAICompatibleSearchProvider.search()` logs the platform prompt through `log_info()`.
- `ExaSearchProvider.search()` logs operation start and finish.
- `call_firecrawl_scrape()` logs empty markdown retries in debug mode.

---

## What NOT to Log

Never log raw API keys, tokens, secrets, full config files, or unmasked private URLs. `cli._is_secret_key()` and `cli._is_private_display_key()` identify values that should not be shown directly in setup prompts.

Do not log to stdout. stdout is reserved for command output consumed by tools. Human-facing setup and warnings go to stderr.

Do not add always-on request/response body logging for provider calls. If a test needs to inspect a payload, monkeypatch the HTTP client or provider method as in provider tests.
