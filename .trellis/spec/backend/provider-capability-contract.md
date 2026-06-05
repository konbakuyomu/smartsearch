# Provider Capability Contract

This contract applies when changing Smart Search provider registration, routing,
fallback, configuration, doctor output, smoke checks, or CLI provider controls.

## 1. Scope / Trigger

Use this spec for any change that touches:

- provider capability membership or fallback order;
- environment/config keys for search, docs, or fetch providers;
- `search`, `doctor`, `setup`, `smoke`, or provider-specific CLI signatures;
- output fields such as `routing_decision`, `providers_used`,
  `provider_attempts`, `fallback_used`, or capability status;
- smoke/regression behavior for provider routing.

This is an infra and cross-layer contract. The implementation must remain
distributable: behavior cannot depend on a developer's local shell, local
installed wrappers, or uncommitted config files.

## 2. Signatures

CLI signatures:

```text
smart-search search QUERY
  [--validation fast|balanced|strict]
  [--fallback auto|off]
  [--providers auto|CSV]
  [--stream | --no-stream]
  [--format json|markdown|content]
smart-search research QUERY
  [--budget quick|standard|deep]
  [--evidence-dir PATH]
  [--fallback auto|off]
  [--format json|markdown|content]
  [--output PATH]

smart-search doctor --format json|markdown|content
smart-search diagnose openai-compatible
  [--timeout SECONDS]
  [--format json|markdown]
smart-search setup
  [--lang zh|en]
  [--advanced]
  [--non-interactive]
  [--skip-skills]
  [--install-skills CSV]
  [--skills-root PATH]
  [provider/config flags...]
smart-search skills status
  [--targets CSV]
  [--all]
  [--skills-root PATH]
  [--format json|markdown|content]
smart-search skills update
  [--targets CSV]
  [--all]
  [--skills-root PATH]
  [--format json|markdown|content]
smart-search smoke (--mock|--live|--mode mock|--mode live) --format json|markdown|content
smart-search exa-search QUERY
  [--num-results N]
  [--search-type neural|keyword|auto]
  [--include-domains DOMAIN...]
  [--exclude-domains DOMAIN...]
  [--format json|markdown|content]
smart-search zhipu-search QUERY --format json|markdown|content
smart-search anysearch-domains [DOMAIN] --format json|markdown|content
smart-search anysearch-search QUERY
  [--domain DOMAIN]
  [--sub-domain SUBDOMAIN]
  [--max-results N]
  [--format json|markdown|content]
smart-search anysearch-extract URL [--max-length N] --format json|markdown|content
smart-search anysearch-batch QUERY...
  [--max-results N]
  [--format json|markdown|content]
smart-search context7-library NAME [--query QUERY] --format json|markdown|content
smart-search context7-docs LIBRARY_ID [--query QUERY] --format json|markdown|content
```

Service-level contracts:

```python
get_capability_status() -> dict[str, Any]
validate_minimum_profile() -> dict[str, Any]
search(query, platform="", model="", extra_sources=0,
       validation="", fallback="", providers="auto") -> dict[str, Any]
research(query, budget="deep", evidence_dir="", fallback="auto") -> dict[str, Any]
doctor() -> dict[str, Any]
diagnose_openai_compatible(timeout_seconds=30.0) -> dict[str, Any]
smoke(mode="mock") -> dict[str, Any]
```

Main-search providers are peers, not nested fallbacks:

```text
main_search fallback chain: xai-responses -> openai-compatible
```

## 3. Contracts

Capabilities:

| Capability | Provider order | Purpose |
| --- | --- | --- |
| `main_search` | `xai-responses`, `openai-compatible` | Broad answer generation and synthesis |
| `web_search` | `zhipu`, `zhipu-mcp`, `tavily`, `firecrawl` | General web-source reinforcement |
| `docs_search` | `context7`, `exa` by intent | Documentation, SDK, API, library, and framework lookup |
| `web_fetch` | `tavily`, `jina`, `zhipu-mcp-reader`, `firecrawl` | Known URL content extraction |
| `vertical_search` | `anysearch` | Experimental structured/vertical search evidence |
| `synthesis` | currently successful `main_search` provider | Final answer synthesis |

Deep Research planner orchestration:

- Deep Research has a public offline planner command:
  `smart-search deep QUERY [--budget quick|standard|deep] [--evidence-dir PATH]`.
  Alias: `dr`.
- `smart-search deep` is a planner, not an executor. It must not call live
  providers, run `doctor`, fetch pages, or change configuration by default.
  Live research happens only when the AI agent or user executes the planned
  `steps[].command` values, or when the user calls `smart-search research`.
- `smart-search research QUERY [--budget quick|standard|deep] [--evidence-dir
  PATH] [--fallback auto|off]` is the live Deep Research executor. It performs
  plan -> source discovery -> fetch/read -> gap check -> evidence-only
  synthesis.
- `research --fallback auto` is the default and permits same-capability
  fallback inside selected routes. `research --fallback off` tries only the
  first selected provider for each capability and is intended for debugging and
  deterministic provider checks.
- `smart-search search` remains the fast live-search entrypoint and must not be
  silently upgraded into Deep Research.
- Deep Research planning is capability-based. Do not require fixed topic recipe
  ids such as `current_market_research`, `technical_docs_research`, or
  `url_first_research`; topic phrases are prompt examples only.
- The planner emits a `research_plan`-shaped JSON object. Required fields are
  `mode`, `query_mode`, `question`, `trigger_source`, `difficulty`,
  `intent_signals`, `decomposition`, `capability_plan`, `evidence_policy`,
  `preflight`, `steps`, `gap_check`, `final_answer_policy`, and
  `usage_boundary`.
- Complex plans should include 2-6 `decomposition` subquestions, each with
  `id`, `question`, `reason`, and `required_capabilities`. Each step must bind
  to a subquestion using `subquestion_id`.
- `intent_signals` should be dimensional signals such as recency, docs/API
  intent, locale/domain scope, known URL, source-authority need, claim risk,
  cross-validation need, and breadth/depth budget.
- `steps[].tool` may only use existing CLI blocks: `search`, `exa-search`,
  `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`,
  and `map`. `doctor` is preflight, not a research step.
- `fetch_before_claim` remains the default evidence policy. `primary_sources`
  and `extra_sources` are discovery candidates until the relevant URL has been
  fetched.
- `gap_check` must fetch missing evidence for key claims or downgrade the claim
  or source to an unverified candidate.
- Deep Research should inspect existing `search` observability fields
  (`routing_decision`, `provider_attempts`, `fallback_used`, `source_warning`)
  rather than introducing an opaque planner path.
- Deep Research must not add `exa-search` as an unconditional second hop for
  high claim risk, cross-validation, or comparison prompts. Choose the
  supplemental tool by intent: `zhipu-search` for Chinese/domestic/current
  evidence, `context7-library` plus `context7-docs` for docs/API/library
  questions, `fetch` plus `exa-similar` for known URLs, and `exa-search` only
  for official domains, papers, product pages, trusted sites, or explicit
  low-noise discovery needs.
- Research provider selection is capability-first and provider-advantage
  second. Future providers must register a profile before joining `research`.
  Profiles declare supported capability, strengths, exclusions, fallback group,
  minimum-profile role, quality filters, route reasons, and experimental status.
- Safe research overrides are
  `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and
  `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`. They may reorder or disable
  providers only inside capabilities the provider already supports. Unknown
  providers are reported in routing metadata and ignored; overrides must never
  move a provider across capability boundaries.
- Baseline `research` provider advantages:
  Context7 for library/API/framework docs; Exa for official domains, papers,
  product/company pages, date/domain-filtered low-noise discovery, and adjacent
  sources; Zhipu REST for Chinese/domestic/current/policy/announcement
  searches; Zhipu MCP only as the separate Coding Plan quota route; Tavily for
  broad discovery and site maps; Jina for known public URL/PDF/arXiv clean
  extraction; Firecrawl for JS-heavy/dynamic/browser-like/OCR/PDF/structured
  extraction fallback; AnySearch only when vertical intent is clear.
- Research final synthesis receives only fetched/read evidence and structured
  source metadata. It must not call web providers again and must not cite
  unfetched discovery candidates as proof. If evidence cannot close, return a
  degraded result with explicit gaps instead of unsupported claims.

Minimum profile:

- Default `SMART_SEARCH_MINIMUM_PROFILE=standard`.
- Standard requires at least one configured provider in `main_search`,
  `docs_search`, and `web_fetch`.
- `vertical_search` is optional and experimental. It must not satisfy or alter
  the `standard` minimum profile until a separate routing task accepts it.
- Jina Reader satisfies `web_fetch` only when `JINA_API_KEY` is configured.
  Anonymous `r.jina.ai` behavior is allowed only as explicit/experimental
  degraded fetch behavior and must not make `standard` pass.
- Missing required capability must fail closed before search execution.
- `SMART_SEARCH_MINIMUM_PROFILE=off` is only for local experiments and tests.

Provider configuration:

- `XAI_API_KEY` registers `xai-responses`.
- `XAI_API_URL` defaults to `https://api.x.ai/v1`.
- `XAI_MODEL` and `XAI_TOOLS` configure the xAI Responses route.
- `OPENAI_COMPATIBLE_API_URL` plus `OPENAI_COMPATIBLE_API_KEY` registers
  `openai-compatible`.
- `OPENAI_COMPATIBLE_MODEL` configures the compatible route.
- `OPENAI_COMPATIBLE_STREAM` is an opt-in relay compatibility switch. It
  defaults to `false`, accepts `true`, `1`, or `yes`, and may be overridden for
  one `search` call with `--stream` or `--no-stream`.
- Official xAI calls use the Responses API `/responses` route through `XAI_*`.
- Compatible relays/gateways use Chat Completions `/chat/completions` through
  `OPENAI_COMPATIBLE_*`.
- `ANYSEARCH_API_URL` configures the experimental AnySearch JSON-RPC endpoint
  and defaults to `https://api.anysearch.com/mcp`.
- `ANYSEARCH_API_KEY` is optional. When present, AnySearch requests send
  `Authorization: Bearer <key>`; when absent, requests are anonymous.
- `ANYSEARCH_TIMEOUT_SECONDS` configures the AnySearch HTTP timeout and
  defaults to `30`.
- `ZHIPU_API_KEY` registers the `zhipu` web-search provider.
- `ZHIPU_API_URL` configures the Zhipu Web Search API base URL. It defaults to
  `https://open.bigmodel.cn/api` and is independent of `TAVILY_API_URL`.
- `ZHIPU_SEARCH_ENGINE` configures the Zhipu Web Search API service/engine. It
  defaults to `search_std`; setup should offer `search_std`, `search_pro`,
  `search_pro_sogou`, and `search_pro_quark`, while `config set
  ZHIPU_SEARCH_ENGINE VALUE` remains free-form for future official services.
- Zhipu support in this project currently means `/paas/v4/web_search` Web
  Search API. Do not describe or implement it as a GLM chat model choice,
  Chat Completions `tools=[web_search]`, Search Agent, or MCP Server unless a
  separate provider design task explicitly adds that route.
- `ZHIPU_MCP_API_KEY` registers separate Zhipu Coding Plan Remote MCP
  providers. It is not part of the `/paas/v4/web_search` REST provider.
- `ZHIPU_MCP_SEARCH_API_URL` defaults to
  `https://open.bigmodel.cn/api/mcp/web_search_prime/mcp` and calls
  `web_search_prime` for `web_search`.
- `ZHIPU_MCP_READER_API_URL` defaults to
  `https://open.bigmodel.cn/api/mcp/web_reader/mcp` and calls `webReader` for
  `web_fetch`.
- `ZHIPU_MCP_ZREAD_API_URL` defaults to
  `https://open.bigmodel.cn/api/mcp/zread/mcp` and exposes explicit repo/docs
  discovery commands for `search_doc`, `get_repo_structure`, and `read_file`.
- A normal Zhipu Web Search API key is not sufficient evidence of Coding Plan
  entitlement. Do not assume `ZHIPU_API_KEY` authorizes `web_search_prime`,
  `webReader`, or zread. If `ZHIPU_MCP_API_KEY` is missing or returns
  auth/provider errors, MCP providers must be skipped or fall through within
  the same capability; zread remains explicit and does not affect the
  `standard` minimum profile.
- Zhipu Coding Plan MCP must be implemented first as a narrow tested
  MCP-over-HTTP provider layer. Avoid broad MCP abstractions until the
  first search, reader, and zread tools are stable.
- `JINA_API_KEY` registers Jina Reader as `web_fetch`.
- `JINA_READER_API_URL` defaults to `https://r.jina.ai`.
- `JINA_RESPOND_WITH` is optional. `JINA_RESPOND_WITH=readerlm-v2` requires
  `JINA_API_KEY` and must fail before network when the key is absent.
- Jina Reader is not a general `web_search` provider and must not be shown as
  one in docs, setup, doctor, or capability status.
- Legacy main-search keys are unsupported: `SMART_SEARCH_API_URL`,
  `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and
  `SMART_SEARCH_XAI_TOOLS`. `config set` / `config unset` must reject them with
  parameter errors, `config list` must omit saved legacy values, and provider
  construction must not infer a main-search provider from them.

Main-search peer rule:

- Never create an `openai-compatible` fallback by reusing the same xAI
  Responses URL/key.
- If only `XAI_API_KEY` is configured, the `main_search` chain contains only
  `xai-responses`.
- If only `OPENAI_COMPATIBLE_API_URL` and `OPENAI_COMPATIBLE_API_KEY` are
  configured, the `main_search` chain contains only `openai-compatible`.
- If both explicit provider families are configured, fallback order is
  `xai-responses -> openai-compatible`.
- The OpenAI-compatible stream switch changes only the request transport for
  OpenAI-compatible `search()` and provider-side `fetch()`. It must not affect
  xAI Responses, URL description, source ranking, or capability routing.

AnySearch boundary:

- AnySearch is an experimental `vertical_search` provider exposed only through
  explicit `anysearch-*` CLI commands and capability diagnostics.
- Do not insert AnySearch into `web_search`, `docs_search`, `web_fetch`, or
  `main_search` fallback chains without a separate acceptance/routing task.
- AnySearch uses JSON-RPC 2.0 `tools/call` with tool names `list_domains`,
  `search`, `extract`, and `batch_search`.
- AnySearch search/extract results must preserve raw markdown/text content.
  URL/title/snippet candidates should be extracted when present, but
  structured evidence without URLs must remain in the result instead of being
  discarded.
- `anysearch-batch` accepts at most five queries. Reject larger batches before
  sending a network request.

Interactive setup contract:

- Setup may install the bundled `smart-search-cli` skill into user-level/global
  AI tool directories under the current user's home directory. This is a setup
  convenience, not Trellis initialization. It must
  not create Trellis workflow files, hooks, agents, commands, or edit unrelated
  skills.
- Skill target ids are `codex`, `claude`, `cursor`, `opencode`, `copilot`,
  `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`,
  `antigravity`, `windsurf`, and `hermes`.
- Skill install targets are relative to the user's home directory by default:
  Codex `~/.codex/skills/`, Claude Code `~/.claude/skills/`, Cursor
  `~/.cursor/skills/`, GitHub Copilot `~/.copilot/skills/`, Hermes Agent
  `~/.hermes/skills/`, and the remaining targets under their listed user-level
  dot-directories. The npm wrapper must preserve the caller cwd for CLI
  execution; package assets are passed separately via package-root metadata and
  must not become the default skill installation root.
- Pi Agent installs to `~/.pi/agent/skills/smart-search-cli`, not the older
  `~/.pi/skills/smart-search-cli` path.
- Runtime skill injection must load bundled package assets, not a developer's
  global `~/.codex/skills`, `~/.cc-switch/skills`, or the local checkout only.
- Skill contract changes must update both public repo-local skill files under
  `skills/smart-search-cli/**` and packaged runtime assets under
  `src/smart_search/assets/skills/smart-search-cli/**`. A source-only skill
  update leaves installed npm users with stale setup/install guidance.
- `--skip-skills` disables skill install. `--install-skills CSV` explicitly
  chooses targets. `--skills-root PATH` is an advanced override for the
  user-level install root used in portable installs or tests. Normal users
  should omit it.
- `smart-search skills status` is the routine stale-skill check. It compares
  bundled assets with installed user-level `smart-search-cli` directories and
  reports per-target `missing`, `up_to_date`, `stale`, `extra_files`, or
  `error` without writing or deleting files.
- `smart-search skills update` is the routine skill sync path after CLI
  upgrades. It reuses the same bundled-file overwrite behavior as setup skill
  installation, supports `--targets CSV`, `--all`, and `--skills-root PATH`,
  and must not change provider keys, run setup prompts, create Trellis files,
  create hooks, create agents, create commands, or delete extra leftover
  files.
- `smart-search setup --non-interactive --install-skills codex` remains the
  first-time configuration compatibility path. Documentation should recommend
  `skills status` and `skills update` for daily/global skill synchronization.
- Default `smart-search setup` must ask for language first. Default language is
  Chinese (`zh`); `--lang en` or `--lang zh` skips the language question.
- The default setup wizard is capability-first, not key-first. It must guide
  required groups in this order: `main_search`, `docs_search`, `web_fetch`,
  then optional `web_search` reinforcement.
- The wizard must make the minimum profile visible before and after prompts,
  including `minimum_profile_ok`, missing required capabilities, and configured
  providers per capability.
- Interactive guidance belongs on stderr so stdout remains parseable
  JSON/Markdown/content output for scripts and AI callers.
- Beginner guidance in setup must be concise and action-first. It should tell
  users to first satisfy `main_search + docs_search + web_fetch`; it must not
  become a long tutorial that pushes the real prompts off screen.
- Setup examples must use official endpoints or neutral placeholders only, such
  as `https://api.openai.com/v1`, `https://api.tavily.com`, or
  `https://<host>/api/tavily`. Do not use a developer's personal relay,
  private pool, temporary key, or local runtime value as an example.
- Existing configured URLs are private display values. Prompt them as
  `configured, press Enter to keep` / `已配置，回车保留`, not as raw URLs.
- Tavily Hikari / pooled endpoint prompts must include a concrete placeholder
  example, for example `https://pool.example.com` or
  `https://pool.example.com/mcp`, and must state that setup saves it as
  `https://pool.example.com/api/tavily`.
- `--advanced` is the compatibility path for low-level key-by-key prompts.
  Most users should stay on the grouped wizard.
- `--non-interactive` must remain script-stable: it only saves flags passed on
  the command line and must not prompt, inspect local developer-only state, or
  call providers.
- When optional `web_search` reinforcement selects Zhipu, grouped setup must
  ask for `ZHIPU_API_KEY`, `ZHIPU_API_URL`, and `ZHIPU_SEARCH_ENGINE`. The URL
  prompt may offer official/current/custom choices; the service prompt should
  offer the official values above plus custom input.
- Non-interactive setup must expose Zhipu endpoint/service flags as
  `--zhipu-api-url` and `--zhipu-search-engine`. Saving these flags must not
  change web-search provider order or enable any cross-capability fallback.
- Advanced setup must include `ZHIPU_API_URL` and `ZHIPU_SEARCH_ENGINE` next to
  `ZHIPU_API_KEY`, preserving URL/secret masking rules.

Output contracts:

- Keep legacy search fields stable: `content`, `sources`, `primary_sources`,
  and `extra_sources`.
- `--format json` is the stable machine-readable contract and must stay
  parseable with readable non-ASCII text when the terminal encoding supports
  it.
- `--format markdown` is the human-readable report/list format. `doctor
  --format markdown` must render a detailed diagnostic report with overall
  status, active/default/legacy config paths, log path resolution, file-logging
  status, masked config values with sources, minimum profile, capability
  status, main-search provider checks, provider connectivity checks, model
  metadata, and full long error/message detail instead of falling back to raw
  JSON.
- `--format content` prints only the `content` field for content-bearing
  commands (`search`, `fetch`, `context7-docs`, `research`). Commands without a
  `content` field, including `doctor`, `smoke`, `config`, and `model`, must
  print a compact non-empty text summary rather than empty stdout.
- Include observability fields: `routing_decision`, `providers_used`,
  `provider_attempts`, `fallback_used`, `validation_level`,
  `minimum_profile_ok`, and `capability_status`.
- `research` JSON must include `final_answer`, `content`, `citations`,
  `evidence_items`, `gap_check`, `provider_attempts`, `fallback_used`,
  `degraded`, `route_policy_version`, and `evidence_dir`.
- `search` must expose the effective OpenAI-compatible stream decision in
  `routing_decision.openai_compatible_stream` when that provider is attempted.
- AnySearch command output must include `provider="anysearch"`, `tool`,
  `content`/`raw_content` when available, `results`, and `elapsed_ms` on
  success. Failures must include stable `ok=false`, `error_type`, `error`,
  `provider`, `tool`, and `elapsed_ms` fields.
- Current/realtime web routing must expose `web_current_intent` while keeping
  `zh_current_intent` as a backward-compatible alias, and should list
  supplemental capability paths under `routing_decision.supplemental_paths`.
- Realtime sports/current queries belong to `web_search` reinforcement under
  `balanced` and `strict`; generic language requests must not become current
  web queries only because they mention Chinese or another language.
- `doctor()` must expose `main_search_connection_tests` keyed by configured
  main provider id.
- `doctor().primary_connection_test` is a backward-compatible alias for the
  first configured main provider only.
- `diagnose openai-compatible` is the beginner-facing focused report for
  OpenAI-compatible Chat Completions search hangs/timeouts. It must default to
  Markdown, support JSON, mask API keys, report base URL/model/stream/config
  path, run a lightweight chat check, then probe real Smart Search search-shape
  requests with `stream=false` and `stream=true`.
- Each `diagnose openai-compatible` check must report status, elapsed time,
  HTTP status when available, content type when available, and whether response
  content was observed. The summary must be plain language: missing config,
  quick chat ok but real search timeout, stream-only works, no-stream-only
  works, both fail, or both real search shapes work.
- On Windows, the default config file is `%LOCALAPPDATA%\smart-search\config.json`.
  Linux/macOS default to `~/.config/smart-search/config.json`.
  `SMART_SEARCH_CONFIG_DIR` remains an advanced override. Earlier Windows
  source defaults used `~\.config\smart-search\config.json`, while some installs
  were already pinned to `%LOCALAPPDATA%\smart-search` through that override. If
  the new default file is missing but the old file exists, the active config
  source is `legacy_windows_home` so upgrades do not silently lose
  configuration. Diagnostics must report the override value and whether it
  matches the current default path.
- OpenAI-compatible doctor checks must use `/chat/completions` as the health
  gate. `/models` may be probed for supplementary model metadata, but a
  `/models` failure must not mark `openai-compatible` unhealthy when
  `/chat/completions` succeeds.
- Exa domain filters accept both comma-separated and whitespace-separated
  domains. The service must normalize strings and list/tuple argv values with
  commas or whitespace into the same list before calling Exa. This protects
  Windows PowerShell and `.ps1` wrapper flows where an unquoted comma expression
  can be forwarded as multiple argv values rather than one CSV string.
- Exa HTTP `400` or `422` failures are parameter errors, not generic network
  errors. The provider should expose `error_type="parameter_error"` so the CLI
  and docs-search fallback path can report bad user arguments accurately.
- Secrets must be masked or omitted in command output, smoke output, docs, task
  artifacts, and error strings.

Regression and release contracts:

- `smart-search regression` has two valid modes. In a source checkout, it runs
  pytest-backed regression over repository tests. In npm or mise packaged
  installs, repository tests are not bundled; it must fall back to built-in mock
  smoke regression and clearly print that packaged fallback is being used.
- Packaged-install regression is an install-health check only. Release
  validation must still run from a source checkout with full pytest-backed
  regression before publishing or tagging a release.
- Published npm versions are immutable. Retagging a GitHub release after npm
  publish can update repository history and rerun CI, but it cannot replace the
  already published tarball. If packaged assets must change for installed users,
  publish a new patch version instead of relying on a retag.
- The npm publish workflow has two automatic release lanes. A push to `main`
  publishes the next test package as `<package.json version>-beta.N` with npm
  dist-tag `next`; `N` resets per base version and legacy `-dev.*` versions
  reserve the earlier beta slots. A pushed stable `vX.Y.Z` tag publishes
  `X.Y.Z` with npm dist-tag `latest`.
- Prerelease `vX.Y.Z-beta.N` tags or manual dispatch versions are never allowed
  to publish npm `latest`; they must use `next` or a backfill/non-latest tag.
- Historical test builds may be backfilled with GitHub Actions
  `workflow_dispatch` using an explicit `target_ref`, exact version, and
  non-latest npm tag such as `backfill`.

### Scenario: Global npm/mise Upgrade and Skill Sync

#### 1. Scope / Trigger

- Trigger: upgrading the globally installed npm package through mise, validating
  a `next` build, or syncing user-level skills after a packaged CLI upgrade.

#### 2. Signatures

- `npm view @konbakuyomu/smart-search dist-tags --json`
- `npm view @konbakuyomu/smart-search@next version`
- `mise use -g "npm:@konbakuyomu/smart-search@next" -y --pin`
- `mise reshim npm:@konbakuyomu/smart-search`
- `where.exe smart-search`
- `smart-search --version`
- `smart-search skills status --all --format json`
- `smart-search skills update --all --format json`
- `smart-search regression`
- `smart-search smoke --mock --format json`
- `smart-search doctor --format json`

#### 3. Contracts

- Do not treat `mise use` success as completion. Final truth is the bare
  `smart-search --version` plus command resolution via `where.exe smart-search`
  or `Get-Command smart-search`.
- For beta/latest distinction, npm `latest` may remain stable while `next`
  carries the newest merged main build. If validating main or a just-merged PR
  output, install and verify `@next`.
- After a fresh packaged install, run the first runtime-creating command
  sequentially before parallel validation. The npm wrapper may create or repair
  `.smart-search-python`; concurrent first-use invocations can race and produce
  one transient missing-runtime failure even though the final runtime is
  healthy.
- Validate `python -m pip --version` inside `.smart-search-python` when runtime
  creation or repair output looked suspicious.
- `skills update --all` may overwrite only managed bundled skill files under
  user-level target directories. It must not alter provider config, run setup
  prompts, create Trellis files, create hooks, create agents, create commands,
  or delete extra files.
- Pi Agent's target path is `~/.pi/agent/skills/smart-search-cli`.

#### 4. Validation & Error Matrix

- `mise use` succeeds but `where.exe smart-search` still resolves an old
  version -> run `mise reshim`, then reopen the shell if the shim remains
  stale.
- `smart-search --version` does not print the target version -> the upgrade is
  not complete.
- First parallel validation reports a missing Python runtime but later
  sequential validation succeeds -> classify as an install-time race and rerun
  the checks sequentially.
- `doctor` returns an upstream 502 while regression/smoke pass and retry
  succeeds -> classify as an external provider transient, not an install
  failure.
- `skills status --all` reports stale or missing targets after upgrade -> run
  `skills update --all`, then require all managed targets to report
  `up_to_date`.

#### 5. Good/Base/Bad Cases

- Good: npm `next=0.1.13-beta.3`, mise current shows `next`, `where.exe`
  points to `...\npm-konbakuyomu-smart-search\next\smart-search.cmd`,
  `smart-search --version` prints `0.1.13b3`, and every managed skill target is
  `up_to_date`.
- Base: packaged `smart-search regression` prints the packaged fallback message
  and passes.
- Bad: declaring success immediately after `mise use -g`, or running parallel
  validation before the runtime exists and treating a transient missing-runtime
  error as final.

#### 6. Tests Required

- Packaged/manual validation must include command resolution, version, runtime
  and pip health when the runtime was created or repaired, `skills status
  --all`, packaged regression, mock smoke, doctor retry on transient upstream
  errors, and at least one minimal live search when provider health is part of
  the upgrade request.
- Code changes touching target paths must include Windows-safe path assertions,
  such as `Path(...).as_posix()` suffix checks or direct `Path` comparisons.

#### 7. Wrong vs Correct

Wrong:

```powershell
mise use -g "npm:@konbakuyomu/smart-search@next" -y --pin
# Report done here.
```

Correct:

```powershell
mise use -g "npm:@konbakuyomu/smart-search@next" -y --pin
mise reshim npm:@konbakuyomu/smart-search
where.exe smart-search
smart-search --version
smart-search skills update --all --format json
smart-search skills status --all --format json
smart-search regression
smart-search smoke --mock --format json
smart-search doctor --format json
```

## 4. Validation & Error Matrix

| Condition | Behavior |
| --- | --- |
| Missing required capability under `standard` | Return `ok: false`, `error_type: "config_error"`, and missing capability ids |
| Invalid validation/fallback/minimum enum | Return `error_type: "parameter_error"` |
| Provider filter excludes all configured main providers | Return config error; do not silently choose another capability |
| `OPENAI_COMPATIBLE_STREAM` is missing | Treat as `false`; do not send `stream: true` |
| `OPENAI_COMPATIBLE_STREAM` or `--stream` is true | Send `stream: true` only to OpenAI-compatible `search()` / `fetch()` and parse SSE deltas, ignoring `[DONE]` |
| `--no-stream` is set | Force non-streaming OpenAI-compatible `search()` for that invocation even when config is true |
| AnySearch `result.isError=true` | Return `ok=false`, `error_type: "provider_error"`, and do not treat the response as a successful source |
| AnySearch HTTP 401/403 | Return `error_type: "auth_error"` with a masked/non-secret message |
| AnySearch timeout | Return `error_type: "timeout"` |
| AnySearch JSON-RPC `error` object | Return `error_type: "provider_error"` with the provider message |
| `anysearch-batch` receives more than five queries | Return `error_type: "parameter_error"` without a network request |
| Exa `--include-domains` / `--exclude-domains` receives comma-separated, whitespace-separated, or PowerShell-split values | Normalize to a flat domain list before sending `includeDomains` / `excludeDomains` to Exa |
| Exa returns HTTP 400 or 422 | Return `error_type: "parameter_error"` and preserve the Exa response body excerpt for diagnosis |
| Provider HTTP/network/timeout/schema error | Record `provider_attempts[].status="error"` and try next same-capability provider when fallback is `auto` |
| Provider returns empty normalized result | Record `status="empty"` and try next same-capability provider when fallback is `auto` |
| `--fallback off` | Try only the first matching provider in the capability chain |
| `research --fallback off` | Try only the first selected provider inside each capability route and report gaps rather than continuing through same-capability fallback |
| Docs intent is false | Do not invoke Context7 or Exa as generic web-search fallback |
| Fetch intent or known URL flow | Use the shared `web_fetch` chain only: Tavily, Jina with key, Zhipu MCP Reader, then Firecrawl |
| Jina Reader has no `JINA_API_KEY` | Do not register it as configured `web_fetch`; standard minimum profile remains missing unless another fetch provider is configured |
| `JINA_RESPOND_WITH=readerlm-v2` without `JINA_API_KEY` | Return config error before network and do not count Jina toward `standard` |
| Jina returns 401/403, 422, 429, timeout, network error, or challenge page such as `Title: Just a moment...` | Record a failed `web_fetch` provider attempt and continue same-capability fallback |
| Zhipu Coding Plan MCP returns auth/rate/provider/timeout/network error | Record the error in `provider_attempts` when used through fallback and keep fallback same-capability |
| Zhipu MCP auth is configured | Send `Authorization: Bearer <key>` and never log the token unmasked |
| Strict validation has no sources | Return `error_type: "evidence_error"` instead of pretending success |
| One live enhancement provider fails but same capability has fallback | Live smoke may mark the case `degraded`; critical paths still fail non-zero |
| Interactive setup has guidance text | Write guidance to stderr and final rendered data to stdout |
| Unknown `--install-skills` target | Return `error_type: "parameter_error"`; do not install any skill |
| `--skip-skills` is set | Do not prompt for or install skills, even if `--install-skills` is also set |
| Skill install target filesystem error | Report target path and error under setup `skills.failed[]`; do not hide provider config writes |
| Interactive setup has an existing URL value | Display only `configured, press Enter to keep`; do not print the raw URL |
| Interactive setup shows example endpoints | Use official endpoints or neutral placeholders; never user/private provider domains |
| Zhipu setup selects official endpoint | Save `ZHIPU_API_URL=https://open.bigmodel.cn/api` |
| Zhipu setup selects an official service | Save the selected `ZHIPU_SEARCH_ENGINE` value without changing provider order |
| Zhipu setup selects custom service | Save the custom `ZHIPU_SEARCH_ENGINE` value; do not reject it just because it is not in today's official list |
| User sets `TAVILY_API_URL` | Affect Tavily REST calls only; do not route, proxy, or document this as a Zhipu endpoint |
| User asks for a Zhipu "model" in setup | Use "Zhipu search service/search engine" wording and keep GLM chat models out of this Web Search API provider |
| Tavily Hikari / pooled endpoint is selected | Tell the user to paste the provider domain/root URL or `/mcp`; normalize to `/api/tavily` |
| Interactive setup skips all required providers | Save nothing new, report `minimum_profile_ok=false`, and list `main_search`, `docs_search`, `web_fetch` |
| `--advanced` is used | Prompt low-level config keys one by one while preserving secret masking |
| `--non-interactive` is used | Do not prompt; save only explicit flags and keep existing script output compatible |
| Source checkout runs `smart-search regression` | Run pytest over CLI, service, provider, smoke, and skill-contract tests |
| Packaged npm/mise install runs `smart-search regression` without `tests/` | Run built-in mock smoke fallback and report that repository tests are absent |
| Skill contract changes | Keep `skills/smart-search-cli/**` and `src/smart_search/assets/skills/smart-search-cli/**` synchronized |
| Deep Research skill contract changes | Assert `intent_signals`, `capability_plan`, `gap_check`, expanded tool allowlist, non-recipe schema, and README coverage |
| Research executor has discovery snippets but no fetched evidence | Return degraded or failed gap report and do not cite discovery candidates |
| Research provider advantage route changes | Add mock routing tests for docs/API, Chinese/current/policy, known URL/PDF/arXiv, JS-heavy/dynamic fetch, and vertical AnySearch intent |
| Research fallback route changes | Assert fallback never crosses capability, provider failures and quality errors are recorded, and `--fallback off` disables same-capability fallback |
| Already published npm version needs changed packaged assets | Do not assume retagging updates npm; cut a new patch version for installable artifacts |
| Need a test npm publish without moving `latest` | Push a commit to `main` and verify the Actions run publishes `<base>-beta.N` with dist-tag `next` |

## 5. Good/Base/Bad Cases

Good:

- Query: `React useEffect API docs`.
- Route: `main_search` answer plus `docs_search` fallback chain.
- Expected: Context7 first for docs/API/library intent; Exa only after
  Context7 error/empty result or when official-domain, paper, product-page,
  trusted-site, or low-noise discovery is explicitly needed.
- Command: `smart-search exa-search "FreeRTOS Kernel latest release" --include-domains github.com,freertos.org --format json`.
- Expected: CLI normalizes the domain filter to `["github.com", "freertos.org"]`.
- Command: `smart-search exa-search "FreeRTOS Kernel latest release" --include-domains github.com freertos.org --format json`.
- Expected: Same normalized domain filter as the comma-separated command.

Base:

- Query: `今天国内 AI 新闻有什么变化`.
- Route: `main_search` answer plus `web_search` reinforcement.
- Expected: Zhipu is eligible because the query is Chinese/current; Context7 is
  not eligible because this is not a docs intent.

Sports/current:

- Query: `nba report`, `NBA score`, or `today schedule`.
- Route: `main_search` answer plus `web_search` reinforcement under
  `balanced`.
- Expected: `routing_decision.web_current_intent=true`,
  `routing_decision.supplemental_paths` contains `web_search`, and
  `provider_attempts` contains a `web_search` attempt.

Language-only:

- Query: `Chinese explanation of a Python function`.
- Route: docs intent may be true, but current web intent is false.
- Expected: the presence of a language word does not trigger `web_search` by
  itself.

Bad:

- Query: `what happened in markets today`.
- Wrong route: Exa fails, then Context7 is forced as a generic news source.
- Expected: Context7 is skipped; web reinforcement uses `web_search` providers.

Setup good:

- Command: `smart-search setup --lang en`.
- Route: grouped wizard asks `main_search`, `docs_search`, `web_fetch`, then
  optional `web_search`.
- Expected: prompt text appears on stderr; stdout remains JSON; secrets are not
  printed; existing URLs are shown only as configured values.

Setup bad:

- Command: `smart-search setup`.
- Wrong route: prompt every low-level key by default and leave users guessing
  which keys satisfy the minimum profile.
- Expected: use grouped capability prompts by default; keep low-level prompts
  behind `--advanced`.

Release good:

- Command: source checkout runs full `smart-search regression`; packaged npm
  install runs `smart-search regression` as mock smoke fallback.
- Expected: source checkout is the release gate; packaged install verifies that
  the installed CLI can execute without bundled test files.
- Test npm publish: push the work commit to `main` only. The workflow derives
  the next `0.1.10-beta.N` style version from npm's published versions and
  publishes it under `next`.

Release bad:

- Command: retag `vX.Y.Z` after npm publish and expect the npm tarball to change.
- Expected: GitHub history may update, but npm keeps the original tarball; ship
  changed packaged assets with a new patch version.
- Command: creating or pushing a `v*` tag when the user asked for a test npm
  package.
- Risk: the workflow publishes to npm dist-tag `latest`, moving the default
  install target for all users.
- Command: publishing a historical backfill with npm dist-tag `next`.
- Risk: npm `next` can move backward to an older beta; use a non-latest tag
  such as `backfill` for historical replacements, then keep `next` on the
  newest beta.

## 6. Tests Required

When this contract changes, add or update tests that assert:

- minimum profile fails closed when any required capability is missing;
- capability fallback order is fixed and same-capability only;
- provider error and empty result both trigger fallback;
- `--fallback off` stops after the first provider;
- provider profiles route `research` by capability first and provider advantage
  second;
- `research` executes staged plan, discovery, fetch/read, gap check, and
  evidence-only synthesis with mocked providers;
- `research` does not cite unfetched discovery candidates and returns degraded
  gaps when evidence cannot close;
- `research --fallback off` disables same-capability fallback;
- provider filters apply to main-search ids and aliases;
- xAI Responses and OpenAI-compatible use separate explicit config families;
- `XAI_API_KEY` alone does not fabricate an OpenAI-compatible fallback;
- OpenAI-compatible alone satisfies `main_search`;
- OpenAI-compatible stream defaults to false, accepts `true`/`1`/`yes`, applies
  only to `search()` and provider-side `fetch()`, and CLI `--stream` /
  `--no-stream` overrides config for one search invocation;
- streaming response parsing concatenates SSE delta content, ignores `[DONE]`,
  and returns an empty string for an empty stream;
- `diagnose openai-compatible` reports missing config clearly, masks API keys,
  distinguishes quick-chat success plus real-search timeout from total
  provider failure, recommends `OPENAI_COMPATIBLE_STREAM=true` when only stream
  works, recommends `OPENAI_COMPATIBLE_STREAM=false` when only no-stream works,
  and marks both real search shapes working as a normal Smart Search main
  path;
- `search` CLI timeout results include provider/model/stream context when
  available plus the next diagnostic command
  `smart-search diagnose openai-compatible --format markdown`;
- AnySearch config keys are listed, settable, masked where secret, and optional
  for the `standard` minimum profile;
- AnySearch capability status is `vertical_search`, `experimental=true`, and
  does not change required minimum capabilities;
- AnySearch JSON-RPC success, `result.isError=true`, JSON-RPC error, HTTP
  error, timeout, anonymous request, authenticated header, raw markdown parsing,
  structured evidence without URL, and batch limit are covered;
- `doctor()` tests configured main providers independently;
- general queries do not call docs providers;
- docs queries use Exa before Context7;
- Exa domain filters accept comma-separated strings, whitespace-separated
  strings, and list/tuple argv values produced by PowerShell wrapper flows;
- Exa HTTP 400/422 responses surface as `parameter_error`, and docs-search
  fallback records them as provider errors rather than empty results;
- Tavily fetch failure falls back through Jina/Zhipu MCP Reader/Firecrawl as
  configured;
- Jina no-key does not satisfy `web_fetch`, Jina key does, and ReaderLM-v2
  without key reports configuration error;
- Jina and Remote MCP service wrappers await `_decode_provider_json(...)` and
  return a decoded dict, never a coroutine object;
- Jina empty/error/challenge output falls through to the next same-capability
  fetch provider;
- `fetch URL` and known-URL `search "https://..."` use the same fetch chain;
- Zhipu Coding Plan Remote MCP mock calls cover `web_search_prime`,
  `webReader`, `search_doc`, `get_repo_structure`, and `read_file`;
- Zhipu MCP auth header is sent, masked, and provider errors are recorded in
  `provider_attempts` without cross-capability fallback;
- strict validation returns insufficient evidence when sources are absent;
- mock smoke covers minimum gate, fallback, routing, and secret masking.
- `--format content` prints only `content` for `search`, `fetch`, and
  `context7-docs`, while commands without `content` print a non-empty summary,
  and `--format json` remains parseable with readable non-ASCII output where
  supported.
- `doctor --format markdown` renders a human-readable health report rather than
  raw JSON, and provider list commands render Markdown result lists or a clear
  no-results message.
- sports/current queries assert `web_current_intent=true`,
  `supplemental_paths` contains `web_search`, and a `web_search` provider
  attempt is recorded under `balanced`.
- language-only queries assert `web_current_intent=false` when no current or
  realtime signal is present.
- interactive setup groups minimum capabilities in Chinese and English;
- setup output keeps prompts on stderr and parseable result data on stdout;
- OpenAI-compatible alone can satisfy `main_search` in the setup wizard;
- selecting both main providers saves distinct xAI and OpenAI-compatible
  credentials and reports the fixed peer fallback chain;
- `--advanced` retains low-level prompts and secret masking;
- `setup --non-interactive --zhipu-api-url URL --zhipu-search-engine ENGINE`
  saves `ZHIPU_API_URL` and `ZHIPU_SEARCH_ENGINE`;
- grouped setup selecting Zhipu prompts for key, API URL, and search service;
- Zhipu setup accepts both official service values and a custom
  `ZHIPU_SEARCH_ENGINE` string;
- service-level `zhipu_search()` uses `config.zhipu_search_engine` by default
  and command-level `--search-engine` as the one-call override;
- provider-level Zhipu payload sends `search_engine` from constructor default
  or per-call override;
- README, public skill, packaged asset skill, and contract docs all state that
  `TAVILY_API_URL` does not proxy Zhipu and that the route is Web Search API,
  not Chat Completions/Search Agent/MCP;
- `--non-interactive` remains prompt-free and backward compatible.
- `--install-skills codex,claude,cursor,hermes --skills-root <tmp>` writes the
  bundled skill into `<tmp>/.codex/skills`, `<tmp>/.claude/skills`,
  `<tmp>/.cursor/skills`, and `<tmp>/.hermes/skills`.
- `--skip-skills` writes no skill files even if skill targets are supplied.
- npm dry-run includes both the public `skills/smart-search-cli/**` tree and
  the runtime package-data assets under `src/smart_search/assets/skills/**`.
- skill contract docs in `skills/smart-search-cli/**` and
  `src/smart_search/assets/skills/smart-search-cli/**` remain byte-for-byte or
  content-equivalent for shared contract files.
- Deep Research mock smoke covers simple current prompts such as
  `深度搜索一下最近的比特币行情`, docs/API prompts, claim verification,
  URL-first fetch, normal search non-trigger, missing-provider guidance, and
  fixed topic recipe ids as examples rather than schema modes.
- packaged regression fallback is covered by simulating a runtime without
  bundled repository tests; release validation still runs source checkout
  regression.
- existing configured URL defaults are not printed in setup stderr;
- beginner setup examples appear on stderr, stay concise, and do not appear in
  stdout;
- Tavily Hikari prompts show a neutral example domain and explain `/mcp` to
  `/api/tavily` normalization;
- scans for real temporary key substrings and private provider domains return
  no hits before commit.

Required closeout commands for provider architecture work:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m smart_search.cli regression
.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json
git diff --check
```

If real temporary keys were used, also run a targeted secret scan for the exact
key substrings before committing.

## 7. Wrong vs Correct

### Wrong

Calling the Zhipu Web Search API service a "model" and wiring it through the
main-search model/provider settings:

```text
smart-search setup --model search_pro_sogou
```

This confuses a Web Search API service selector with GLM chat model selection
and makes users think Tavily/OpenAI-compatible settings can affect Zhipu.

### Correct

Keep the Web Search API service on Zhipu-specific config and expose it through
setup/config/provider payload tests:

```text
smart-search setup --zhipu-api-url https://open.bigmodel.cn/api --zhipu-search-engine search_pro_sogou
smart-search config set ZHIPU_SEARCH_ENGINE search_pro_sogou
smart-search zhipu-search "today China AI news" --search-engine search_pro_quark
```

`ZHIPU_API_URL` and `ZHIPU_SEARCH_ENGINE` affect only the Zhipu
`/paas/v4/web_search` route. `TAVILY_API_URL` remains Tavily-only.

### Wrong

Treating xAI Responses failure as permission to call the same xAI URL through
the OpenAI-compatible adapter:

```python
providers = [
    XAIResponsesSearchProvider(api_url, api_key, model, tools),
    OpenAICompatibleSearchProvider(api_url, api_key, model),
]
```

This creates a fake fallback and hides whether the user actually configured a
compatible relay.

### Correct

Build main-search providers from separate provider config families and only
include providers that are truly configured:

```python
providers = []
if config.xai_api_key:
    providers.append("xai-responses")
if config.openai_compatible_api_url and config.openai_compatible_api_key:
    providers.append("openai-compatible")
```

Legacy `SMART_SEARCH_API_*` must not register any main provider. Users must
migrate to `XAI_*` for official xAI Responses or `OPENAI_COMPATIBLE_*` for a
Chat Completions relay/gateway.

### Wrong

Using the default setup path as a flat list of provider keys:

```text
Primary API URL:
Primary API key:
Exa API key:
Tavily API key:
Firecrawl API key:
```

This hides the minimum profile and makes distributable installs fail later.

### Correct

Guide by capability, then show the final minimum-profile result:

```text
[1/3 Required] main_search: xAI Responses or OpenAI-compatible
[2/3 Required] docs_search: Context7 for docs/API; Exa for official domains, papers, and low-noise discovery
[3/3 Required] web_fetch: Tavily, Jina with key, Zhipu MCP Reader, or Firecrawl
[Optional] web_search reinforcement: Zhipu / Tavily / Firecrawl
```

This makes setup self-validating without relying on one developer's local
environment.

### Wrong

Returning a provider JSON decoder coroutine from a public service wrapper:

```python
async def call_jina_reader(url: str) -> dict[str, Any]:
    raw = await JinaReaderProvider(...).fetch_url(url)
    return _decode_provider_json(raw, provider="jina")
```

This can pass type review while failing at runtime because CLI callers receive
a coroutine instead of the normalized result dict.

### Correct

Await every async normalization boundary before returning from service wrappers:

```python
async def call_jina_reader(url: str) -> dict[str, Any]:
    raw = await JinaReaderProvider(...).fetch_url(url)
    return await _decode_provider_json(raw, provider="jina")
```

Add wrapper-level tests for each provider family (`Jina`, `AnySearch`, and
`Zhipu MCP`) so future async helper changes cannot silently break the public
CLI/service contract.

### Wrong

Showing a configured endpoint or private relay as the default value:

```text
OpenAI-compatible API URL required [https://private-relay.example.com/v1]:
```

This leaks local runtime configuration into a distributable setup flow.

### Correct

Mask URL defaults the same way as secrets, but still let Enter keep them:

```text
OpenAI-compatible API URL required [configured, press Enter to keep]:
```

### Wrong

Run the npm-installed Python CLI from the npm package directory and let setup
default skill installation there:

```javascript
spawn(pythonPath, ["-m", "smart_search.cli", ...args], { cwd: packageRoot })
```

### Correct

Run from the caller cwd while passing packageRoot separately for bundled runtime
assets; skill installation itself defaults to the user's home directory, not the
package directory or the caller project:

```javascript
spawn(pythonPath, ["-m", "smart_search.cli", ...args], {
  cwd: process.cwd(),
  env: { ...process.env, SMART_SEARCH_PACKAGE_ROOT: packageRoot }
})
```

Use official endpoints or neutral placeholders only when teaching new users
what to type.

### Wrong

Updating only the public skill copy after a CLI contract change:

```text
skills/smart-search-cli/references/cli-contract.md
```

The npm installer reads packaged assets, so installed users may still receive
old command signatures or regression guidance.

### Correct

Update the public skill and the package asset copy together:

```text
skills/smart-search-cli/references/cli-contract.md
src/smart_search/assets/skills/smart-search-cli/references/cli-contract.md
```

Then assert both copies match, and run source checkout regression before
release.

### Wrong

Treating packaged `smart-search regression` as the full release gate:

```powershell
smart-search regression
```

When run from an npm/mise install, repository tests are not present and the CLI
can only run the built-in mock smoke fallback.

### Correct

Use source checkout regression as the release gate and packaged regression as
an install-health check:

```powershell
.\.venv\Scripts\python.exe -m smart_search.cli regression
smart-search regression
```
