# State Management

> State management conventions for this project.

---

## Overview

There is no frontend state-management layer. No Redux, Zustand, React Query, SWR, browser storage, or client-side cache exists in this repository.

Current state is backend/CLI state:
- config file and environment variables in `src/smart_search/config.py`
- in-memory source cache in `src/smart_search/sources.py`
- local npm-installed Python runtime under `.smart-search-python`

Backend state rules are documented in backend database and quality specs.

---

## State Categories

Frontend local/global/server/URL state categories are not applicable.

For CLI/service work, treat state categories as:
- environment values
- JSON config-file values
- process-local in-memory caches
- command output payloads

---

## When to Use Global State

Do not add frontend global state. For Python code, avoid new module-level mutable state unless it has a bounded purpose like `_AVAILABLE_MODELS_CACHE` or `SourcesCache` and is protected appropriately for async use.

---

## Server State

There is no frontend server-state cache. Provider responses are normalized into returned dictionaries and optional process-local caches.

---

## Common Mistakes

Do not use browser storage or frontend cache concepts for CLI configuration. Use `Config` and `SMART_SEARCH_CONFIG_DIR` instead.

Do not persist source cache entries unless a task explicitly introduces durable history and updates backend specs.
