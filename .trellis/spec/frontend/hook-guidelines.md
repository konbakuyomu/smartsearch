# Hook Guidelines

> Hook conventions for this project.

---

## Overview

There are no frontend hooks in this repository. There is no React app, no custom `use*` hooks, and no browser data-fetching layer.

---

## Custom Hook Patterns

Not applicable today.

If a future frontend is added, document actual hook boundaries here. Include naming, state ownership, data fetching, cancellation behavior, and test expectations.

---

## Data Fetching

Current data fetching is backend/provider code using async Python and `httpx`, not frontend hooks. See backend specs for provider and service rules.

---

## Naming Conventions

Not applicable today.

---

## Common Mistakes

Do not introduce frontend hook abstractions for CLI setup, config, provider fallback, or npm packaging scripts. Those belong in Python service/config/provider modules or npm packaging helpers.
