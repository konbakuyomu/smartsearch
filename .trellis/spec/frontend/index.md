# Frontend Development Guidelines

> Best practices for frontend development in this project.

---

## Overview

This repository currently has no browser frontend. These guidelines document that boundary so future agents do not invent component, hook, state, or TypeScript conventions that are not present. JavaScript in this repo is npm packaging glue for the Python CLI.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | No frontend app; npm wrapper and package helper layout | Filled |
| [Component Guidelines](./component-guidelines.md) | No components today; future frontend requirements | Filled |
| [Hook Guidelines](./hook-guidelines.md) | No hooks today; backend/provider data-fetching boundary | Filled |
| [State Management](./state-management.md) | No frontend state layer; CLI/config/cache state boundary | Filled |
| [Quality Guidelines](./quality-guidelines.md) | npm wrapper/package quality rules | Filled |
| [Type Safety](./type-safety.md) | No TypeScript frontend; Python typing boundary | Filled |

---

## Pre-Development Checklist

Before editing anything that looks frontend-related:

1. Confirm whether the task is really adding a browser frontend or only changing npm packaging.
2. For npm packaging, follow the wrapper/package guidance here and backend CLI contracts.
3. For a new browser UI, update these specs with the actual framework and conventions before implementation.

## Quality Check

For npm wrapper/package changes, run `npm test` when the local npm-managed Python runtime is available. For backend-only CLI changes, use the backend quality guide.

---

**Language**: All documentation should be written in **English**.
