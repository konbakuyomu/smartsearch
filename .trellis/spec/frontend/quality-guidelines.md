# Quality Guidelines

> Quality standards for frontend-applicable work.

---

## Overview

There is currently no frontend application to lint, render, or test in a browser. Frontend quality work is therefore limited to npm packaging and wrapper behavior.

For Python CLI/service quality, use the backend specs.

---

## Forbidden Patterns

Do not add unused frontend scaffolding, placeholder component directories, or framework config files unless a task explicitly introduces a real frontend.

Do not change npm wrapper behavior in a way that diverges from the Python CLI contract. The wrapper should forward arguments, preserve stdio, set `SMART_SEARCH_PACKAGE_ROOT`, and propagate the Python process exit code.

Do not make npm scripts depend on developer-specific absolute paths.

---

## Required Patterns

Npm wrapper scripts must remain cross-platform:
- use Node built-ins such as `path`, `fs`, and `child_process`
- account for Windows virtualenv paths under `Scripts/python.exe`
- keep `windowsHide: true`
- avoid shell mode unless a script intentionally uses it for platform compatibility

Packaging changes must preserve package assets listed in `package.json`, especially:
- `src/smart_search/**/*.py`
- `src/smart_search/assets/skills/smart-search-cli/**`
- `skills/smart-search-cli/**`
- `pyproject.toml`, `README.md`, and `LICENSE`

---

## Testing Requirements

For npm wrapper or packaging changes, run:

```bash
npm test
```

This command verifies Python tests, wrapper help, and npm package dry-run behavior through `npm/scripts/test.js`.

If the local `.smart-search-python` runtime is missing, run the Python tests directly for backend-only changes and report that npm package validation could not run.

---

## Code Review Checklist

Review npm/frontend-applicable changes for:
- correct Python runtime path on macOS/Linux and Windows
- argument forwarding to `smart_search.cli`
- inherited stdio so CLI output remains unchanged
- exit status propagation
- package asset inclusion
- no accidental introduction of browser framework assumptions
