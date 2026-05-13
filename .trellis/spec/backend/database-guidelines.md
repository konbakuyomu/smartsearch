# Database Guidelines

> Database conventions for this project.

---

## Overview

This project currently has no database, ORM, migration system, queue storage, or persistent application schema. Do not introduce database abstractions for configuration or cache behavior unless the feature explicitly requires durable multi-record state.

Current persistence is file-based configuration:
- `src/smart_search/config.py` stores user config in JSON at `~/.config/smart-search/config.json` by default.
- `SMART_SEARCH_CONFIG_DIR` can pin config and log state to a test or sandbox-friendly directory.
- Tests isolate config by monkeypatching `Config._config_file` and environment variables in `tests/conftest.py`.

Runtime source caching is in-memory only:
- `src/smart_search/sources.py` uses `SourcesCache` with an `asyncio.Lock` and an `OrderedDict`.
- Cache ids are short session ids from `new_session_id()`.
- The cache is process-local and intentionally not persisted.

---

## Query Patterns

There are no database queries. For external API requests, use provider classes and `httpx.AsyncClient` rather than inventing repository or DAO layers.

If a future feature needs persisted records, document the new storage contract here before implementing it. Include:
- storage backend and migration mechanism
- file or database location
- record schema
- read/write locking behavior
- cleanup and compatibility strategy

---

## Migrations

There are no migrations today. Config file changes are handled by tolerant reads and explicit key normalization:
- `Config._LEGACY_CONFIG_KEYS` maps legacy names to current environment-style keys.
- `Config.get_saved_config()` filters loaded JSON to supported keys from `_CONFIG_KEYS`.
- `Config.unset_config_value()` removes both current and legacy keys when applicable.

For config migrations, prefer backward-compatible reads plus tests over one-time destructive rewrites.

---

## Naming Conventions

Config keys use uppercase environment-style names. Add new keys to `Config._CONFIG_KEYS` and expose them consistently through:
- `Config` property accessors
- `smart-search config set/list/unset`
- setup flow when user input is needed
- tests that prove environment values override config-file values

JSON config values are stored as strings. Secret and URL-like values must be masked in display paths using the CLI/service masking helpers rather than printed raw.

---

## Common Mistakes

Do not store test or runtime state in the repository root by default. `tests/test_regression.py` asserts that regression behavior does not create repo log files.

Do not make config-file location implicit in tests. Use monkeypatching or `SMART_SEARCH_CONFIG_DIR` so tests do not touch a developer's real `~/.config/smart-search/config.json`.

Do not persist source cache data unless a task explicitly introduces durable history. Current source lookup is process-local and should remain easy to reset between CLI runs.
