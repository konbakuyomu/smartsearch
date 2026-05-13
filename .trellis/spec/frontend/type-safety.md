# Type Safety

> Type-safety conventions for frontend code.

---

## Overview

There is no TypeScript frontend in this repository. Existing JavaScript is CommonJS npm packaging code and is not typed with TypeScript.

The active type-safety conventions are in Python:
- use Python 3.10+ type hints such as `dict[str, Any]`, `list[dict]`, and `str | None`
- keep public result dictionary fields stable and covered by tests
- use dataclasses for simple immutable structured records when useful, as in `SkillTarget`

---

## Type Organization

Not applicable for frontend. Do not add shared frontend type directories unless a frontend exists.

For Python code, colocate small types with their owning module. Examples:
- `SearchResult` and `BaseSearchProvider` live in `src/smart_search/providers/base.py`
- `SkillTarget` lives in `src/smart_search/skill_installer.py`

---

## Validation

There is no frontend runtime validation library. Python config validation is centralized in `Config` and service-level parameter checks.

Examples:
- `Config.parse_xai_tools()` validates allowed xAI tools.
- `service.search()` validates `validation_level` and `fallback_mode`.
- `skill_installer.parse_skill_targets()` validates known installation targets and raises `SkillInstallError`.

---

## Common Patterns

Use explicit dictionaries for public CLI/service payloads and assert their fields in tests. Prefer small normalization helpers over passing raw provider payloads through the system.

---

## Forbidden Patterns

Do not add `any`-style frontend guidance or TypeScript rules without a TypeScript codebase.

Do not weaken Python contracts by returning raw provider JSON directly from public service functions unless the command already has that behavior and tests cover it.
