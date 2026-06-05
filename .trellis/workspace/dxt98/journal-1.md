# Journal - dxt98 (Part 1)

> AI development session journal
> Started: 2026-05-12

---



## Session 1: Search provider capability fallback

**Date**: 2026-05-12
**Task**: Search provider capability fallback
**Branch**: `main`

### Summary

Implemented capability registry, provider fallback, Zhipu and Context7 adapters, xAI/OpenAI-compatible peer main-search providers, smoke/regression validation, and provider guardrails.

### Main Changes

- Added a provider capability model for `main_search`, `web_search`, `docs_search`, `web_fetch`, and synthesis.
- Added Zhipu and Context7 provider adapters and source-first service/CLI paths.
- Modeled xAI Responses and OpenAI-compatible as explicit peer main-search providers instead of implicit key reuse.
- Added same-capability fallback, minimum-profile validation, and provider observability fields.
- Added smoke/regression coverage and provider capability guardrails.

### Git Commits

| Hash | Message |
|------|---------|
| `55369d3` | (see git log) |

### Testing

- [OK] See commit `55369d3` and the archived task context for the original verification details.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: Capability setup wizard

**Date**: 2026-05-12
**Task**: Capability setup wizard
**Branch**: `main`

### Summary

Implemented bilingual capability-grouped setup wizard and recorded provider setup UX contracts.

### Main Changes

﻿- Implemented a bilingual grouped setup wizard for `smart-search setup`.
- Preserved `--non-interactive` script behavior and added `--advanced` for low-level key prompts.
- Added setup result observability fields for minimum profile status and capability status.
- Added tests for Chinese/English setup paths, missing minimum profile, OpenAI-compatible-only main search, both peer main providers, advanced prompts, and secret masking.
- Captured setup UX contract in the distributable CLI contract and local Trellis provider capability spec.
- No active Trellis current task existed; `00-bootstrap-guidelines` remains in progress and was not archived.
- Release route confirmed: push to `main` triggers npm `next` build as `${package.version}-dev.${GITHUB_RUN_NUMBER}`; no `v*` tag was created, so this is beta/next rather than latest.


### Git Commits

| Hash | Message |
|------|---------|
| `f9330df` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: Setup TUI provider URLs

**Date**: 2026-05-13
**Task**: Setup TUI provider URLs
**Branch**: `main`

### Summary

Implemented grouped setup TUI, Tavily/Firecrawl URL configuration, Hikari normalization, concise beginner guidance, URL masking, tests, docs, and smoke/regression validation.

### Main Changes

- Added `smart-search skills status/update` for routine global skill drift checks and refreshes without rerunning setup.
- Implemented bundled-vs-installed skill comparison with `missing`, `up_to_date`, `stale`, `extra_files`, and `error` status output.
- Rebalanced docs/API/library routing toward Context7 first, with Exa reserved for official domains, papers, product pages, trusted sites, and low-noise discovery.
- Updated Deep Research planning so Chinese/current prompts select Zhipu, docs/API prompts select Context7, URL-first prompts still start with `fetch`, and generic claim verification no longer adds Exa unconditionally.
- Synced public skill files and packaged runtime assets, then updated the live Codex and `.cc-switch` `smart-search-cli` skill copies.
- Updated the three Obsidian Trellis guidance notes with `skills status/update`, first-time setup vs daily sync guidance, and search-engine selection rules.
- Archived `.trellis/tasks/archive/2026-05/05-24-anysearch-acceptance-openai-streaming` after validation.

### Git Commits

| Hash | Message |
|------|---------|
| `97b54c2` | (see git log) |

### Testing

- [OK] `.\.venv\Scripts\python.exe -m pytest tests -q` -> 225 passed
- [OK] `.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json` -> ok
- [OK] `.\.venv\Scripts\python.exe -m compileall -q src tests`
- [OK] `git diff --check`
- [OK] `smart-search skills status/update --targets codex --format json`
- [OK] unknown skill target returns `parameter_error` and exit code 2
- [OK] `.cc-switch` skill copy SHA256 matches the repo-local skill files

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: Setup visual skill injection

**Date**: 2026-05-13
**Task**: Setup visual skill injection
**Branch**: `main`

### Summary

Added Trellis-style setup banner and project-local smart-search-cli skill injection with bundled package assets, npm cwd preservation, docs, tests, regression, mock smoke, and npm pack validation.

### Main Changes

- Added `smart-search diagnose openai-compatible`, with Markdown as the default human-facing report and JSON for scripts/agents.
- The diagnosis path reports masked OpenAI-compatible config, config path/source, base URL, model, configured stream mode, and timeout.
- The service checks three stages: lightweight chat completion, real Smart Search search-shape `stream=false`, and real Smart Search search-shape `stream=true`.
- Search CLI timeout output now includes provider/model/stream context and recommends `smart-search diagnose openai-compatible --format markdown`.
- README, provider capability spec, public `smart-search-cli` skill, packaged skill asset, and CLI contract docs were kept in sync.
- `00-bootstrap-guidelines` remains active because its PRD checklist is not complete; no task archive was performed for this unrelated bootstrap task.

### Git Commits

| Hash | Message |
|------|---------|
| `adf3213` | (see git log) |

### Testing

- [OK] `.\.venv\Scripts\python.exe -m compileall -q src tests`
- [OK] `.\.venv\Scripts\python.exe -m pytest tests -q` -> 234 passed
- [OK] `.\.venv\Scripts\python.exe -m smart_search.cli regression` -> 172 passed
- [OK] `.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json` -> `ok: true`
- [OK] `git diff --check`
- [OK] Smoke: `diagnose openai-compatible --format json`, `diagnose openai-compatible --format markdown`, and timeout markdown search output.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: Ship v0.1.8 content output and realtime routing fixes

**Date**: 2026-05-13
**Task**: Ship v0.1.8 content output and realtime routing fixes
**Branch**: `main`

### Summary

Added direct content output, balanced realtime sports web reinforcement, packaged regression fallback, skill contract synchronization, release verification, and local task archive.

### Main Changes

- Implemented Jina Reader as controlled `web_fetch` only: key-required for the standard minimum profile, ReaderLM-v2 fail-closed without key, challenge/empty/error filtering, and same-capability fallback.
- Implemented separate Zhipu Coding Plan Remote MCP provider paths for `webSearchPrime`, `webReader`, and zread repo/docs discovery tools without mixing them into the existing Zhipu REST Web Search provider.
- Updated setup/config, doctor/status, public and packaged skill docs, README files, provider-capability spec, and unit/regression tests.
- Captured the async wrapper gotcha where provider JSON decoders must be awaited before returning from service-level wrappers.

### Git Commits

| Hash | Message |
|------|---------|
| `c5f38fe` | (see git log) |
| `e164174` | (see git log) |

### Testing

- [OK] `.venv\Scripts\python.exe -m pytest tests -q` -> 257 passed.
- [OK] `.venv\Scripts\python.exe -m smart_search.cli regression` -> 195 passed.
- [OK] `.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json` -> `ok: true`.
- [OK] `python -m compileall -q src tests`.
- [OK] `git diff --check` with line-ending warnings only.
- [OK] `npm pack --dry-run` included Jina/Zhipu MCP provider files and bundled skill assets.
- [OK] Secret scan found no real Jina key in the repository.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: Ship Deep Research and Exa domain filters

**Date**: 2026-05-13
**Task**: Ship Deep Research and Exa domain filters
**Branch**: `main`

### Summary

Shipped optional skill-driven Deep Research workflow, fixed Exa PowerShell domain-filter parsing and Exa parameter error classification, bumped package metadata to 0.1.10, and completed source checkout validation before release.

### Main Changes

﻿- Added Deep Research Mode to README, public smart-search-cli skill, packaged skill assets, and CLI contract.
- Defined research_plan, fetch_before_claim, allowed tool blocks, evidence paths, and mock-full/live-limited smoke expectations.
- Fixed exa-search --include-domains / --exclude-domains to accept comma-separated and whitespace-separated domains, including PowerShell split argv flows.
- Classified Exa HTTP 400/422 as parameter_error and 429 as rate_limited.
- Added tests for Deep Research contract sync, Exa CLI parsing, service normalization, provider error classification, and packaged asset parity.
- Bumped package metadata to 0.1.10 for GitHub Actions npm release.
- Validation: compileall passed; pytest tests -> 151 passed; smart_search.cli smoke --mock -> ok true; smart_search.cli regression -> 109 passed; npm pack dry-run included public and packaged skills; diff checks clean except CRLF notices.


### Git Commits

| Hash | Message |
|------|---------|
| `efd95ca` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: Deep Research capability orchestration

**Date**: 2026-05-13
**Task**: Deep Research capability orchestration
**Branch**: `main`

### Summary

Implemented capability-based Deep Research skill orchestration, synchronized public and packaged skill contracts, added mock smoke/regression coverage, captured local spec lessons, and prepared npm next-lane publish via main push.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `68e15bb3d5096068762eeb6b7bc779c9e3e74f4a` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: Zhipu search service setup

**Date**: 2026-05-14
**Task**: Zhipu search service setup
**Branch**: `main`

### Summary

Exposed Zhipu Web Search API URL and search service in setup/config docs, synchronized public and packaged skills, and verified CLI/service/provider behavior.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `8e24a75` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 9: Deep Research explicit planner

**Date**: 2026-05-14
**Task**: Deep Research explicit planner
**Branch**: `main`

### Summary

Added public offline smart-search deep/dr planner, synchronized docs and packaged skill contracts, preserved fetch evidence under quick budget, and validated source checkout gates.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `fbf6f86` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 10: Deep Research beta.3 wrapper fix

**Date**: 2026-05-14
**Task**: Deep Research beta.3 wrapper fix
**Branch**: `main`

### Summary

修复 Windows npm/mise packaged CLI 在管道捕获中文 JSON 时的编码问题；发布 0.1.11-beta.3 到 npm next，并完成本机 mise 安装和 packaged smoke 验证。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `13dc1e6` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 11: Hard remove legacy main search config and release 0.1.12

**Date**: 2026-05-14
**Task**: Hard remove legacy main search config and release 0.1.12
**Branch**: `main`

### Summary

Removed legacy SMART_SEARCH_API_* main-search config support, documented the explicit XAI_* /responses and OPENAI_COMPATIBLE_* /chat/completions split, published v0.1.12 to npm latest and GitHub Releases, and updated local mise smart-search to 0.1.12.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `a15c679` | (see git log) |
| `07ecb71` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 12: CLI human-readable output formats

**Date**: 2026-05-15
**Task**: CLI human-readable output formats
**Branch**: `main`

### Summary

Implemented human-readable markdown/content rendering for doctor, smoke, config, model, setup, and provider result commands; updated README and smart-search-cli skill contracts; verified source tests, regression, smoke, npm test, and diff checks before beta push.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `3ce62fb` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 13: Config path diagnostics and output formats

**Date**: 2026-05-15
**Task**: Config path diagnostics and output formats
**Branch**: `main`

### Summary

Implemented Windows config path diagnostics, detailed doctor markdown, content error summaries, and format-respecting timeout handling.

### Main Changes

﻿## 本轮沉淀

- Windows 配置路径排障不能只看 `config_file`，必须同时看 `config_dir_source`、`config_dir_override_value`、`config_dir_override_matches_default`、`default_config_file` 和旧 home 路径是否存在。
- 如果 `config_dir_source=environment` 且 `config_dir_override_matches_default=true`，说明用户级 `SMART_SEARCH_CONFIG_DIR` 只是把路径固定到了新版默认值；功能上不再是第二套配置，但删除前必须先验证升级后的 `config path`、`doctor`、smoke/regression。
- `doctor --format markdown` 应定位为给人排障的详细报告，长错误/长消息不能只塞进表格后被截断，必须在 provider detail 或代码块里完整呈现。
- `json` 继续作为最完整机器接口，`content` 只做短摘要；但错误路径即使是 `content` 也要包含 `error_type` 或错误消息，避免看起来像“无输出”。
- `search` timeout 不能绕过用户请求的 `--format`，否则 shell/agent 调用会因为错误路径突然变 JSON 而破坏兼容性。
- public skill 与 packaged skill 的 `cli-contract.md` 必须同步，发布包里也要带上相同的故障诊断契约。

## 验证

- `..venv\Scripts\python.exe -m pytest tests/test_config_dir_override.py tests/test_cli.py -q` -> 81 passed
- `npm test` -> 190 passed，并执行 npm pack dry-run
- `..venv\Scripts\python.exe -m smart_search.cli regression` -> 143 passed
- `..venv\Scripts\python.exe -m compileall -q src tests` -> passed
- `git diff --staged --check` -> passed

## 归档说明

- `get_context.py --mode record` 显示 current task 为 none。
- 仍在 in_progress 的 `00-bootstrap-guidelines` 与本轮配置路径/输出格式工作无关，因此本轮不归档该任务。


### Git Commits

| Hash | Message |
|------|---------|
| `7ad6fbb` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 14: Global smart-search skill setup and Tavily doctor timeout

**Date**: 2026-05-15
**Task**: Global smart-search skill setup and Tavily doctor timeout
**Branch**: `main`

### Summary

Moved setup skill installation to user-level tool roots, made Tavily doctor timeout configurable, synced docs/assets/tests, and verified beta-ready release gates.

### Main Changes

﻿- Implemented setup skill installation as a user-level/global workflow instead of project-local injection.
- Confirmed Codex should install to `~/.codex/skills`, not the previous `.agents/skills` target, and Copilot should use `~/.copilot/skills` rather than project `.github/skills`.
- Preserved `--skills-root` as an advanced root override for tests/portable installs, but no longer as project-root semantics.
- Added regression coverage for global install paths, guided TUI labels, skip behavior, aliases, Tavily timeout config, and doctor Tavily timeout propagation.
- Synced public skill docs and packaged runtime skill assets so npm users receive the same setup contract.
- Verification completed: pytest tests, regression, mock smoke, npm test, package asset parity, and diff checks all passed.
- Spec lesson captured locally: setup/install-skills contracts must be based on each tool's real user-level skill source of truth, and contract changes must update both public `skills/**` and packaged `src/smart_search/assets/skills/**` copies.


### Git Commits

| Hash | Message |
|------|---------|
| `015439b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 15: Skill sync command and search routing rebalance

**Date**: 2026-05-26
**Task**: Skill sync command and search routing rebalance
**Branch**: `main`

### Summary

Added standalone smart-search skills status/update commands, rebalanced planner/search routing away from unconditional Exa, synced public and packaged smart-search-cli skill docs, updated user-level Codex and cc-switch skill copies, refreshed Obsidian guidance, verified tests/smoke/CLI contracts, and archived the completed AnySearch acceptance task.

### Main Changes

- Added `smart-search skills status/update` for routine global skill drift checks and refreshes without rerunning setup.
- Implemented bundled-vs-installed skill comparison with `missing`, `up_to_date`, `stale`, `extra_files`, and `error` status output.
- Rebalanced docs/API/library routing toward Context7 first, with Exa reserved for official domains, papers, product pages, trusted sites, and low-noise discovery.
- Updated Deep Research planning so Chinese/current prompts select Zhipu, docs/API prompts select Context7, URL-first prompts still start with `fetch`, and generic claim verification no longer adds Exa unconditionally.
- Synced public skill files and packaged runtime assets, then updated the live Codex and `.cc-switch` `smart-search-cli` skill copies.
- Updated the three Obsidian Trellis guidance notes with `skills status/update`, first-time setup vs daily sync guidance, and search-engine selection rules.
- Archived `.trellis/tasks/archive/2026-05/05-24-anysearch-acceptance-openai-streaming` after validation.

### Git Commits

| Hash | Message |
|------|---------|
| `33be99b` | (see git log) |

### Testing

- [OK] `.\.venv\Scripts\python.exe -m pytest tests -q` -> 225 passed
- [OK] `.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json` -> ok
- [OK] `.\.venv\Scripts\python.exe -m compileall -q src tests`
- [OK] `git diff --check`
- [OK] `smart-search skills status/update --targets codex --format json`
- [OK] unknown skill target returns `parameter_error` and exit code 2
- [OK] `.cc-switch` skill copy SHA256 matches the repo-local skill files

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 16: OpenAI-compatible diagnose command

**Date**: 2026-05-30
**Task**: OpenAI-compatible diagnose command
**Branch**: `main`

### Summary

Added a beginner-facing diagnose openai-compatible command, enhanced search timeout guidance, synchronized README/skill/provider contracts, and validated with compileall, pytest, regression, mock smoke, and diff check.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `a62efcc` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 17: Jina and Zhipu MCP provider beta

**Date**: 2026-06-06
**Task**: Jina and Zhipu MCP provider beta
**Branch**: `codex/update-anysearch-readme-links`

### Summary

Added controlled Jina web_fetch support and separate Zhipu Coding Plan Remote MCP providers; updated setup/config/docs/skills/spec/tests; source validation passed with pytest, regression, mock smoke, compileall, diff check, secret scan, and npm dry-run.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `b19d00c` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 18: Research router and fallback

**Date**: 2026-06-06
**Task**: Research router and fallback
**Branch**: `codex/update-anysearch-readme-links`

### Summary

Added the live research executor with capability-first provider-advantage routing, same-capability fallback, safe research provider overrides, evidence-only synthesis, synchronized docs/skills/provider contract, and completed full unit, regression, mock smoke, live doctor, live research, and live smoke verification.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `6798283` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 19: Research router Jina and Zhipu MCP beta closeout

**Date**: 2026-06-06
**Task**: Research router Jina and Zhipu MCP beta closeout
**Branch**: `codex/update-anysearch-readme-links`

### Summary

Closed out the beta provider work: Jina fetch-only support, Zhipu Coding Plan MCP schema/error handling, live research router and same-capability fallback, provider-boundary documentation, Jina capability probe script, and release notes for 0.1.14-beta.2.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `b19d00c` | (see git log) |
| `539cb0e` | (see git log) |
| `6798283` | (see git log) |
| `205c7a6` | (see git log) |
| `d01814c` | (see git log) |
| `c775043` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
