# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains the active coding contracts for the Python CLI, service, provider, config, and npm-wrapper portions of this repository.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Python package, provider, CLI, test, and npm wrapper organization | Filled |
| [Database Guidelines](./database-guidelines.md) | Current no-database stance, file config, and in-memory cache conventions | Filled |
| [Error Handling](./error-handling.md) | Result dictionaries, error types, CLI exit codes, and fallback diagnostics | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Contract testing, provider/config review rules, and forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Quiet-by-default logging, debug logs, stderr/stdout boundaries | Filled |

---

## Pre-Development Checklist

Before editing backend, CLI, provider, config, source parsing, npm wrapper, or tests:

1. Read the guideline file matching the touched area.
2. Identify the public contract being changed: CLI flags, result dictionary fields, provider ids, config keys, exit codes, or package assets.
3. Add or update focused tests for that contract before reporting completion.
4. Keep stdout machine-readable and keep secrets masked.

## Quality Check

At minimum, run focused pytest coverage for the touched module. For broad backend or CLI changes, run `python -m pytest`. For packaging or npm-wrapper changes, run `npm test` when the local npm-managed Python runtime is available.

---

**Language**: All documentation should be written in **English**.
