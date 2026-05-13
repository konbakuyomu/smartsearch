# Directory Structure

> Frontend applicability for this repository.

---

## Overview

This repository currently has no browser frontend, no React/Vue/Svelte app, no page routing, and no UI component tree. Do not create frontend directories or component abstractions unless a future task explicitly adds a user-facing web application.

The only JavaScript code today is npm distribution glue:
- `npm/bin/smart-search.js` is the executable wrapper for the Python CLI.
- `npm/scripts/` contains package install, version sync, packaging, and test helpers.
- `package.json` exposes the `smart-search` binary and includes packaged Python and skill files.

---

## Directory Layout

```text
npm/
  bin/smart-search.js            # Node wrapper that launches Python CLI
  scripts/postinstall.js         # npm install-time runtime setup
  scripts/test.js                # package-level test command
  scripts/sync-python-version.js # version sync helper
  scripts/set-package-version.js # version helper

skills/smart-search-cli/         # source skill assets shipped in npm package
src/smart_search/assets/skills/  # packaged Python resource copy of skill assets
```

There is no `src/components`, `src/pages`, `app/`, `public/`, or frontend build output.

---

## Module Organization

Treat JavaScript files as packaging/backend support, not frontend code. Keep npm wrapper changes minimal and compatible with Node 18+.

If a task adds a real frontend later, update this spec first with the chosen framework, route structure, component conventions, styling system, and test approach before implementing pages.

---

## Naming Conventions

Existing npm files use kebab-case names in `npm/scripts/` and CommonJS in `npm/bin/smart-search.js`. Preserve this style for npm packaging helpers unless the package is deliberately migrated to ESM.

The npm wrapper must keep the binary name `smart-search` from `package.json`.

---

## Examples

The wrapper boundary is:

```javascript
spawn(pythonPath, ["-m", "smart_search.cli", ...process.argv.slice(2)], {
  cwd: callerCwd,
  stdio: "inherit",
  env: {
    ...process.env,
    SMART_SEARCH_PACKAGE_ROOT: packageRoot
  },
  windowsHide: true
});
```

Do not add UI concerns here. The wrapper should locate the packaged Python runtime, delegate arguments, preserve stdio, and propagate exit status.
