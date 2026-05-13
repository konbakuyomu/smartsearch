# Directory Structure

> Backend and CLI code organization for this Python package.

---

## Overview

This repository is a Python CLI package distributed directly through Python packaging and through a thin npm wrapper. There is no web server layer. Treat `src/smart_search/` as the application package, `tests/` as the executable contract suite, and `npm/` as packaging glue for npm distribution.

Real examples:
- `src/smart_search/cli.py` owns argparse commands, aliases, rendering, exit codes, and interactive setup prompts.
- `src/smart_search/service.py` owns orchestration, provider fallback, routing decisions, response shaping, and config-facing service functions.
- `src/smart_search/providers/` owns provider-specific HTTP payloads, retries, response parsing, and result normalization.
- `src/smart_search/sources.py` owns source extraction, answer cleanup, source merging, and in-memory session source cache behavior.
- `src/smart_search/config.py` owns environment and config-file resolution.
- `npm/bin/smart-search.js` only locates the bundled Python runtime and delegates to `python -m smart_search.cli`.

---

## Directory Layout

```text
src/smart_search/
  cli.py                         # CLI parser, command aliases, rendering, setup flow
  service.py                     # async service orchestration and result contracts
  config.py                      # config singleton, env/config-file lookup, validation
  logger.py                      # optional file logging and MCP-style ctx logging
  sources.py                     # answer/source parsing, cache, deduplication
  skill_installer.py             # smart-search-cli skill installation targets
  providers/
    base.py                      # BaseSearchProvider and SearchResult
    openai_compatible.py         # Chat Completions provider
    xai_responses.py             # xAI Responses provider
    exa.py                       # Exa provider
    context7.py                  # Context7 provider
    zhipu.py                     # Zhipu provider
  assets/skills/smart-search-cli/ # packaged agent skill assets

npm/
  bin/smart-search.js            # npm executable wrapper
  scripts/                       # npm packaging, postinstall, and test helpers

tests/
  test_cli.py                    # command behavior, rendering, setup, aliases
  test_service.py                # service contracts, fallback, config, provider routing
  test_sources.py                # source parsing and cleanup contracts
  test_*provider*.py             # provider payload and parsing behavior
```

---

## Module Organization

New CLI commands start in `src/smart_search/cli.py` and delegate behavior into `src/smart_search/service.py`. Keep CLI code responsible for parsing, rendering, output files, stdout/stderr safety, and exit code mapping. Keep network and business behavior in service/provider modules.

Provider integrations should live under `src/smart_search/providers/` when they have their own API shape. Each provider should expose a small class or helper set that normalizes external responses before `service.py` merges them into public CLI output.

Reusable parsing or normalization helpers belong in focused modules:
- source text parsing and deduplication: `src/smart_search/sources.py`
- configuration lookup and validation: `src/smart_search/config.py`
- packaging or skill asset installation: `src/smart_search/skill_installer.py`

Do not put provider-specific HTTP details into `cli.py`. Do not put argparse or interactive prompt logic into provider classes.

---

## Naming Conventions

Python modules use lowercase snake_case filenames. Private helper functions use a leading underscore, as in `_empty_search_result`, `_parse_provider_filter`, and `_normalize_tavily_api_url`. Public service functions use command-like names such as `search`, `fetch`, `map_site`, `doctor`, `config_set`, and `set_model`.

Provider ids are stable lowercase strings because tests and CLI output assert them. Keep values such as `xai-responses`, `openai-compatible`, `tavily`, `firecrawl`, `exa`, `context7`, and `zhipu` unchanged unless you are doing a deliberate migration with regression tests.

Environment keys are uppercase and centralized in `Config._CONFIG_KEYS` in `src/smart_search/config.py`. Add new user-visible config keys there before exposing them through setup or service code.

---

## Examples

Good split for a new provider:

```python
# src/smart_search/providers/example.py
class ExampleProvider(BaseSearchProvider):
    async def search(self, query: str, count: int = 5) -> str:
        ...

# src/smart_search/service.py
async def example_search(query: str, count: int = 5) -> dict[str, Any]:
    if not config.example_api_key:
        return {"ok": False, "error_type": "config_error", "error": "..."}
    raw = await ExampleProvider(config.example_api_url, config.example_api_key).search(query, count)
    ...
```

Good CLI split:

```python
# src/smart_search/cli.py
async def _run_async(args: argparse.Namespace) -> int:
    if args.command == "search":
        data = await service.search(args.query, ...)
        return _print_result("search", data, args.format, args.output)
```

Tests should mirror the touched layer. CLI parsing and exit codes belong in `tests/test_cli.py`; service fallback/result contracts belong in `tests/test_service.py`; provider payload details belong in provider-specific tests.
