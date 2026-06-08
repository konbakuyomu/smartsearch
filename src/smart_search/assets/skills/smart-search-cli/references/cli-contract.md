# Smart Search CLI Contract

## Entrypoints

- `smart-search` is the primary CLI.
- `smart-search --version`, `smart-search --v`, and `smart-search -v` print the installed version and exit with code `0`.
- `smart-search` should resolve from the user's PATH.
- This bundled skill is maintained with the `smartsearch` repository.
- Private API keys should be saved with `smart-search setup` or `smart-search config set`.
- Environment variables remain supported for CI and advanced users, and override the local config file.
- Do not depend on MCP inline `env` values or committed API-key environment variables for CLI use.
- On Windows with mise, the managed package name is `npm:@konbakuyomu/smart-search`; the executable remains `smart-search`. Diagnose mise managed installs with `mise ls "npm:@konbakuyomu/smart-search"` and `mise which smart-search` (the bare name `smart-search` is the bin, not a mise tool identifier).
- On Windows, the default config file is `%LOCALAPPDATA%\smart-search\config.json`. Linux/macOS default to `~/.config/smart-search/config.json`.
- `SMART_SEARCH_CONFIG_DIR` is an advanced override for CI, containers, sandboxes, or portable installs. The CLI uses it for config and relative logs and skips default-directory selection.
- Earlier Windows source defaults used `~\.config\smart-search\config.json`, while some installs were already pinned to `%LOCALAPPDATA%\smart-search` through `SMART_SEARCH_CONFIG_DIR`. If the new Windows default file is missing but the old file exists, the active config source is `legacy_windows_home` so upgrades do not silently lose configuration. Diagnostics must expose the override value and whether it matches the current default.

## Commands

- `smart-search search QUERY [--platform NAME] [--model ID] [--extra-sources N] [--validation fast|balanced|strict] [--fallback auto|off] [--providers auto|CSV] [--stream|--no-stream] [--timeout SECONDS] [--format json|markdown|content] [--output PATH]`
- `smart-search route QUERY [--validation fast|balanced|strict] [--router-mode hybrid|rules|off] [--format json|markdown|content] [--output PATH]`
- `smart-search fetch URL [--format json|markdown|content] [--output PATH]`
- `smart-search exa-search QUERY [--num-results N] [--search-type neural|keyword|auto] [--include-text] [--include-highlights] [--start-published-date YYYY-MM-DD] [--include-domains DOMAIN...] [--exclude-domains DOMAIN...] [--category NAME] [--format json|markdown|content] [--output PATH]`
- `smart-search exa-similar URL [--num-results N] [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-search QUERY [--count N] [--search-engine NAME] [--search-recency-filter VALUE] [--search-domain-filter DOMAIN] [--content-size medium|high] [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-mcp-search QUERY [--count N] [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-mcp-reader URL [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-mcp-search-doc REPO QUERY [--max-results N] [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-mcp-repo-structure REPO [--ref REF] [--format json|markdown|content] [--output PATH]`
- `smart-search zhipu-mcp-read-file REPO PATH [--ref REF] [--format json|markdown|content] [--output PATH]`
- `smart-search anysearch-domains [DOMAIN] [--format json|markdown|content] [--output PATH]`
- `smart-search anysearch-search QUERY [--domain DOMAIN] [--sub-domain SUB_DOMAIN] [--max-results N] [--format json|markdown|content] [--output PATH]`
- `smart-search anysearch-extract URL [--max-length N] [--format json|markdown|content] [--output PATH]`
- `smart-search anysearch-batch QUERY... [--max-results N] [--format json|markdown|content] [--output PATH]`
- `smart-search context7-library NAME [QUERY] [--format json|markdown|content] [--output PATH]`
- `smart-search context7-docs LIBRARY_ID QUERY [--format json|markdown|content] [--output PATH]`
- `smart-search deep QUERY [--budget quick|standard|deep] [--evidence-dir PATH] [--format json|markdown|content] [--output PATH]`
- `smart-search research QUERY [--budget quick|standard|deep] [--evidence-dir PATH] [--fallback auto|off] [--format json|markdown|content] [--output PATH]`
- `smart-search route-calibrate [--models CSV] [--format json|markdown|content] [--output PATH]`
- `smart-search map URL [--instructions TEXT] [--max-depth N] [--max-breadth N] [--limit N] [--timeout SECONDS] [--format json|markdown|content] [--output PATH]`
- `smart-search doctor [--format json|markdown|content] [--output PATH]`
- `smart-search diagnose openai-compatible [--timeout SECONDS] [--format json|markdown] [--output PATH]`
- `smart-search setup [--lang zh|en] [--advanced] [--non-interactive] [--skip-skills] [--install-skills CSV] [--skills-root PATH] [--xai-api-url URL] [--xai-api-key KEY] [--xai-model ID] [--xai-tools-explicit CSV] [--openai-compatible-api-url URL] [--openai-compatible-api-key KEY] [--openai-compatible-model ID] [--openai-compatible-stream true|false] [--validation-level fast|balanced|strict] [--fallback-mode auto|off] [--minimum-profile standard|off] [--intent-router hybrid|rules|off] [--intent-embedding-api-url URL] [--intent-embedding-api-key KEY] [--intent-embedding-model ID] [--intent-embedding-threshold FLOAT] [--intent-embedding-margin FLOAT] [--intent-classifier-api-url URL] [--intent-classifier-api-key KEY] [--intent-classifier-model ID] [--intent-router-timeout SECONDS] [--exa-key KEY] [--context7-key KEY] [--zhipu-key KEY] [--zhipu-api-url URL] [--zhipu-search-engine ENGINE] [--zhipu-mcp-key KEY] [--zhipu-mcp-search-api-url URL] [--zhipu-mcp-reader-api-url URL] [--zhipu-mcp-zread-api-url URL] [--zhipu-mcp-timeout SECONDS] [--jina-key KEY] [--jina-reader-api-url URL] [--jina-respond-with MODE] [--jina-timeout SECONDS] [--tavily-api-url URL] [--tavily-key KEY] [--firecrawl-api-url URL] [--firecrawl-key KEY] [--anysearch-api-url URL] [--anysearch-key KEY] [--anysearch-timeout SECONDS] [--format json|markdown|content] [--output PATH]`
- `smart-search config path [--format json|markdown|content] [--output PATH]`
- `smart-search config list [--format json|markdown|content] [--output PATH]`
- `smart-search config set KEY VALUE [--format json|markdown|content] [--output PATH]`
- `smart-search config unset KEY [--format json|markdown|content] [--output PATH]`
- `smart-search model set MODEL [--format json|markdown|content] [--output PATH]`
- `smart-search model current [--format json|markdown|content] [--output PATH]`
- `smart-search regression`
- `smart-search smoke [--mode mock|live] [--mock] [--live] [--format json|markdown|content] [--output PATH]`
- `smart-search --version`

## Aliases

Top-level aliases must normalize to the same service behavior as their full command:

| Full command | Aliases |
| --- | --- |
| `smart-search --version` | `smart-search --v`, `smart-search -v` |
| `search` | `s` |
| `route` | `rt` |
| `fetch` | `f` |
| `map` | `m` |
| `exa-search` | `exa`, `x` |
| `exa-similar` | `xs` |
| `zhipu-search` | `z`, `zp` |
| `zhipu-mcp-search` | `zmcp-search` |
| `zhipu-mcp-reader` | `zmcp-reader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` |
| `zhipu-mcp-repo-structure` | `zmcp-tree` |
| `zhipu-mcp-read-file` | `zmcp-file` |
| `anysearch-domains` | `as-domains` |
| `anysearch-search` | `as-search`, `as` |
| `anysearch-extract` | `as-extract` |
| `anysearch-batch` | `as-batch` |
| `context7-library` | `c7`, `ctx7` |
| `context7-docs` | `c7d`, `c7docs`, `ctx7-docs` |
| `deep` | `dr` |
| `research` | `rs` |
| `route-calibrate` | `route-cal`, `rcal` |
| `doctor` | `d` |
| `diagnose` | `diag` |
| `setup` | `init` |
| `config` | `cfg` |
| `model` | `mdl` |
| `smoke` | `sm` |
| `regression` | `reg` |

Nested aliases:

| Full command | Aliases |
| --- | --- |
| `config path` | `cfg p` |
| `config list` | `cfg ls`, `cfg l` |
| `config set` | `cfg s` |
| `config unset` | `cfg rm`, `cfg u` |
| `model current` | `mdl cur`, `mdl c` |
| `model set` | `mdl s` |

## Output Format Expectations

Successful search output includes `ok`, `query`, `primary_api_mode`, `content`, `sources`, `sources_count`, `primary_sources`, `primary_sources_count`, `extra_sources`, `extra_sources_count`, `source_warning`, `routing_decision`, `providers_used`, `provider_attempts`, `fallback_used`, `validation_level`, and `elapsed_ms`. Each source should include at least `url` when available.

Route diagnostic output includes `ok`, `query`, `executed_search=false`, `provider_selection=not_executed`, backward-compatible fields `docs_intent`, `zh_current_intent`, `web_current_intent`, `fetch_intent`, `supplemental_paths`, and unified intent-router fields `intent_router_mode`, `required_capabilities`, `intent_signals`, `confidence`, `router_engines_used`, `degraded`, `degraded_reason`, `reasons`, `embedding_model`, `embedding_threshold`, `embedding_margin`, `embedding_threshold_source`, and `embedding_margin_source`. `smart-search route` must not call search/docs/fetch providers.

Route calibration output includes `ok`, `metric`, `primary_metric=semantic_macro_f1`, `full_route_metric_role=validation`, `models`, `model_results`, `dataset_size`, `dataset_counts`, `capabilities`, `recommended_model`, `recommended_threshold`, `recommended_margin`, and `failed_models`. Each model result records `ok`, `model`, availability/error fields, embedding `dimension`, `latency_ms`, `semantic_macro_f1`, `full_route_macro_f1`, recommended threshold/margin, confusion matrices, and representative failures. A failed embedding model must be recorded as `ok=false` inside `model_results` without aborting the full calibration run.

`--format json` is the stable machine-readable contract for agents and scripts. JSON output remains parseable and uses readable non-ASCII text when the terminal encoding supports it.

`--format markdown` is the human-readable report format. `route --format markdown` must render the selected capabilities, engines, confidence, embedding model/threshold/margin, degradation reason, reasons, and signals without provider execution. `route-calibrate --format markdown` must render a model comparison report rather than raw JSON. `doctor --format markdown` must render a detailed diagnostic report with overall status, active/default/legacy config paths, log path resolution, file-logging status, masked config values with sources, minimum profile, capability status, main-search provider checks, provider connectivity checks, intent router status, embedding threshold/margin metadata, model metadata, and full long error/message detail instead of falling back to raw JSON. `diagnose openai-compatible --format markdown` must render a short copy-pasteable troubleshooting report with masked config, quick chat check, real search-shape `stream=false` and `stream=true` checks, a plain-language summary, and a next command. Provider list commands such as `exa-search`, `exa-similar`, `zhipu-search`, `anysearch-*`, `context7-library`, and `map` render result lists or a clear no-results message.

`--format content` prints only the `content` field for content-bearing commands such as `search`, `fetch`, `context7-docs`, and `research`. Commands without a `content` field, including `route`, `route-calibrate`, `doctor`, `smoke`, `config`, and `model`, must print a compact non-empty text summary rather than an empty stdout.

Source provenance fields:

- `primary_sources`: sources explicitly extracted from the primary model/provider answer.
- `extra_sources`: parallel Tavily / Firecrawl candidates from `--extra-sources`; these are not automatic evidence for the generated `content`.
- `sources`: backward-compatible merged list from `primary_sources + extra_sources`, deduped by URL.

Exa domain filters:

- `--include-domains` and `--exclude-domains` accept comma-separated or whitespace-separated domains.
- Both `--include-domains docs.python.org,developer.mozilla.org` and `--include-domains docs.python.org developer.mozilla.org` normalize to the same Exa domain list.
- This normalization is intentional for Windows PowerShell, where an unquoted comma expression can be forwarded through `.ps1` wrappers as a space-separated value.
- `source_warning`: non-empty when extra source candidates were appended.

Fetch output includes `ok`, `url`, `provider`, `content`, `provider_attempts`, `fallback_used`, and `elapsed_ms`.

Zhipu Web Search API setup:

- `ZHIPU_API_URL` defaults to `https://open.bigmodel.cn/api`.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`.
- Official Web Search API service values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`.
- `smart-search setup --zhipu-api-url URL --zhipu-search-engine ENGINE` saves these values in non-interactive mode.
- Interactive setup asks for Zhipu API key, API URL, and search service when optional `web_search` reinforcement selects Zhipu.
- `config set ZHIPU_SEARCH_ENGINE VALUE` must remain free-form so newly added official services do not require a CLI release.
- `zhipu-search` corresponds to Zhipu Web Search API, not Zhipu Chat Completions `tools=[web_search]`, not Search Agent, and not the MCP Server.
- `TAVILY_API_URL` only affects Tavily and does not proxy Zhipu.
- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity timeout. It defaults to `30` so slower pooled/community endpoints are not incorrectly marked unhealthy by the diagnostic check.

Zhipu Coding Plan Remote MCP setup:

- `ZHIPU_MCP_API_KEY` configures the Coding Plan MCP auth token and must be sent as `Authorization: Bearer ...`; it must never be logged unmasked.
- `ZHIPU_MCP_SEARCH_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/web_search_prime/mcp` and calls `web_search_prime` for `web_search`.
- `ZHIPU_MCP_READER_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/web_reader/mcp` and calls `webReader` for `web_fetch`.
- `ZHIPU_MCP_ZREAD_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/zread/mcp` and calls `search_doc`, `get_repo_structure`, and `read_file` through explicit repo/docs commands.
- Zhipu Coding Plan MCP must be implemented as a separate Remote MCP-over-HTTP provider layer. Do not route it through the existing `/paas/v4/web_search` Zhipu REST provider.
- A normal Zhipu Web Search API key is not sufficient evidence of Coding Plan entitlement. If `ZHIPU_MCP_API_KEY` is missing or returns auth/provider errors, MCP providers are skipped or fall through within the same capability; zread remains explicit and does not affect the standard minimum profile.
- Provider failures must appear in `provider_attempts` and fallback must remain same-capability.
- `doctor` should report configured/not-configured, auth, rate-limit, provider, timeout, and network status without exposing the MCP token.

Jina Reader setup:

- `JINA_READER_API_URL` defaults to `https://r.jina.ai`.
- `JINA_API_KEY` is required before Jina satisfies `SMART_SEARCH_MINIMUM_PROFILE=standard`.
- Anonymous Jina Reader calls may be used only as explicit/experimental degraded fetch behavior; they must not make standard setup pass.
- `JINA_RESPOND_WITH=readerlm-v2` requires `JINA_API_KEY` and should report a configuration error without a network request when the key is missing.
- Jina Reader is `web_fetch` only, not `web_search`.
- Jina 401/403, 422, 429, timeout, network errors, and low-quality challenge pages such as `Title: Just a moment...` must be reported as failed provider attempts and allow same-capability fallback.

OpenAI-compatible streaming:

- `OPENAI_COMPATIBLE_STREAM` defaults to `false` and accepts `true`, `1`, or `yes` as true.
- `search --stream` and `search --no-stream` override `OPENAI_COMPATIBLE_STREAM` for the current invocation.
- Streaming applies only to OpenAI-compatible `search()` and provider-side `fetch()` calls. `describe_url()` and `rank_sources()` stay non-streaming. xAI Responses behavior is unchanged.

Intent router:

- `SMART_SEARCH_INTENT_ROUTER` accepts `hybrid`, `rules`, and `off`; default is `hybrid`.
- `INTENT_EMBEDDING_API_URL`, `INTENT_EMBEDDING_API_KEY`, and `INTENT_EMBEDDING_MODEL` configure optional OpenAI-compatible embeddings for semantic capability routing.
- `INTENT_EMBEDDING_THRESHOLD` defaults to `0.74`; `INTENT_EMBEDDING_MARGIN` defaults to `0.05`. Both are model-specific parameters. Normal setup should recommend the Qwen3-Embedding-8B preset: `INTENT_EMBEDDING_API_URL=https://api.siliconflow.cn/v1/embeddings`, `INTENT_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`, `INTENT_EMBEDDING_THRESHOLD=0.475`, and `INTENT_EMBEDDING_MARGIN=0.053`.
- When setup receives or prompts `Qwen/Qwen3-Embedding-8B` and threshold/margin are not explicitly configured, it auto-fills `0.475` and `0.053`. Explicit threshold/margin values win. Existing mismatched threshold/margin values should produce a warning rather than being silently overwritten.
- Semantic routing may add a capability only when the top score is at least `INTENT_EMBEDDING_THRESHOLD` and the top-vs-second score gap is at least `INTENT_EMBEDDING_MARGIN`; otherwise ambiguous semantic matches are recorded as signals only.
- `smart-search route-calibrate --models CSV` evaluates embedding models on the built-in calibration set. The primary selector is semantic-only Macro-F1; full-route Macro-F1 validates rules/classifier fallback behavior.
- After changing `INTENT_EMBEDDING_MODEL`, changing embedding endpoints, or refreshing the real-query calibration set, users should rerun `route-calibrate` and then set `INTENT_EMBEDDING_THRESHOLD` and `INTENT_EMBEDDING_MARGIN` from the report.
- `INTENT_CLASSIFIER_API_URL`, `INTENT_CLASSIFIER_API_KEY`, and `INTENT_CLASSIFIER_MODEL` configure optional OpenAI-compatible chat-completions classification.
- `INTENT_ROUTER_TIMEOUT_SECONDS` defaults to `8` and applies only to optional remote router calls.
- Hybrid mode is fail-open: missing or failing embeddings/classifier record `degraded=true` and `degraded_reason`, then local rules still route the request.
- The router returns capabilities only: `docs_search`, `web_search`, `web_fetch`, and `vertical_search`. It must not select providers.
- Classifier output is capability-whitelisted. Unknown capability names and provider names are ignored and recorded in route reasons.
- `search` and `research` use the unified router. `deep` remains an offline planner and must not call embeddings or classifier components.
- `doctor` and `route` report intent router mode, whether embeddings/classifier are configured, embedding model, threshold, margin, threshold/margin source, Qwen3-Embedding-8B preset recommendation/commands when mismatched, timeout, and that it degrades to rules. They must not expose router API keys.

AnySearch experimental output:

- AnySearch uses JSON-RPC 2.0 `tools/call` at `ANYSEARCH_API_URL`, default `https://api.anysearch.com/mcp`.
- `ANYSEARCH_API_KEY` is optional. If configured, requests include `Authorization: Bearer ...`; if missing, anonymous requests are allowed.
- `ANYSEARCH_TIMEOUT_SECONDS` defaults to `30`.
- HTTP 200 responses with `result.isError=true` must return `ok=false`, `error_type=provider_error`, and no successful source results.
- Markdown URL/title/snippet candidates should be parsed into `results`, while raw text remains in `content` and `raw_content`.
- Structured results without URLs must be preserved as raw/structured evidence, not dropped.
- Dotted vertical domain shorthand such as `security.cve` must be normalized to `domain=security` plus `sub_domain=cve` before calling AnySearch.
- `anysearch-batch` accepts at most 5 CLI query strings, sends them as JSON-RPC query objects (`{"query": "...", "max_results": N}`), and returns `error_type=parameter_error` without sending a request when the limit is exceeded.

Exa search output includes `ok`, `query`, `search_type`, `results`, `total`, and `elapsed_ms` when successful.

Exa HTTP `400` or `422` failures are returned as `ok=false` with `error_type=parameter_error`; use this to distinguish bad CLI/domain/date/category arguments from upstream network failures.

Exa similar output includes `ok`, `url`, `results`, `total`, and `elapsed_ms` when successful.

Zhipu search output includes `ok`, `query`, `provider`, `search_engine`, `results`, `total`, and `elapsed_ms` when successful.

Zhipu MCP command output includes `ok`, `provider`, `tool`, `elapsed_ms`, and either `content` for reader/file-like tools or `results` plus `total` for search-like tools.

Context7 library output includes `ok`, `query`, `provider`, `results`, `total`, and `elapsed_ms` when successful. Context7 docs output includes `ok`, `library_id`, `query`, `provider`, `results`, `total`, `content`, and `elapsed_ms` when successful.

Map output includes `ok`, `base_url`, `results`, `response_time`, `url`, and `elapsed_ms` when successful.

Deep planner output includes `ok`, `mode`, `query_mode`, `question`, `trigger_source`, `difficulty`, `intent_signals`, `decomposition`, `capability_plan`, `evidence_policy`, `preflight`, `steps`, `gap_check`, `final_answer_policy`, `usage_boundary`, `allowed_tools`, `evidence_dir`, and `elapsed_ms`. `smart-search deep` is offline by default: `preflight.executed_by_deep_command=false`, no provider calls are made, and live research only happens when an AI agent or user executes `steps[].command` or calls `smart-search research`.

Research executor output includes `ok`, `mode=deep_research_execution`, `query_mode=research`, `question`, `budget`, `research_plan`, `routing_decision`, `stage_results`, `discovery_sources`, `final_answer`, `content`, `citations`, `evidence_items`, `gap_check`, `provider_attempts`, `providers_used`, `fallback_used`, `degraded`, `route_policy_version`, `evidence_dir`, `minimum_profile_ok`, `capability_status`, and `elapsed_ms`. Citations must come only from fetched/read `evidence_items`; discovery sources are candidates until fetched. If evidence cannot close, `research` returns degraded gaps instead of unsupported claims.

Diagnostic output masks keys, reports `config_file` / `config_dir` / `config_dir_source` / `default_config_file` / Windows legacy config metadata / `config_dir_override_value` / `config_dir_override_matches_default` / `log_dir_config_value` / `resolved_log_dir` / `file_logging_enabled` / `config_sources` / `primary_api_mode` / `primary_api_mode_source` / provider timeout values / `capability_status` / `minimum_profile_ok` / `intent_router_status`, and includes `main_search_connection_tests` plus connection test objects for Exa, Tavily, Zhipu, Context7, and Firecrawl. `primary_connection_test` remains as a backward-compatible alias for the first configured main provider check. OpenAI-compatible provider health must be validated through `/chat/completions`; `/models` is supplementary metadata and must not be the health gate. Firecrawl currently reports whether `FIRECRAWL_API_KEY` is configured; it is not a live Firecrawl request.

When a Windows user reports that different versions seem to use different config paths, diagnose in this order: `config_dir_source`, `config_dir_override_value`, `config_dir_override_matches_default`, then `legacy_windows_config_exists`. A source of `environment` with `config_dir_override_matches_default=true` means the active path is pinned by `SMART_SEARCH_CONFIG_DIR` but is functionally the same as the current default. Do not delete either config file or the user-level override until the upgraded CLI has been verified with `config path`, `doctor`, and smoke/regression checks.

Smoke output includes `ok`, `mode`, `failed_cases`, `cases`, `provider_attempts`, and `elapsed_ms`. Live smoke may include `degraded_cases` when a provider fails but a same-capability fallback remains available.

## Deep Research Skill Contract

Deep Research is an optional capability orchestration workflow for prompts such as `深度搜索`, `深度调研`, `深入搜索`, `deep search`, `deep research`, multi-source verification, cross-checking, serious review, and selection/comparison research. `smart-search deep` is the public offline planner command for this workflow. `smart-search research` is the public live executor command. It must not change default `smart-search search` behavior. `deep` must not execute live providers by default. `research` executes the staged workflow and writes JSON/Markdown evidence.

Deep Research must not require fixed topic recipe ids such as `current_market_research`, `product_comparison_research`, `technical_docs_research`, `news_or_policy_research`, `claim_verification_research`, or `url_first_research`. Those phrases may appear as prompt examples, but they are not schema modes or routing enums.

Before execution, the skill should call `smart-search deep "question" --format json` to create a `research_plan` JSON artifact. Required fields are:

- `mode`: always `deep_research`.
- `query_mode`: always `deep`.
- `question`: the user's research question.
- `trigger_source`: usually `explicit_cli`.
- `difficulty`: `standard` or `high`.
- `intent_signals`: dimensional signals such as `recency_requirement`, `docs_api_intent`, `locale_domain_scope`, `known_url`, `source_authority_need`, `claim_risk`, `cross_validation_need`, and `breadth_depth_budget`.
- `decomposition`: subquestions for complex research, each with `id`, `question`, `reason`, and `required_capabilities`.
- `capability_plan`: the selected capability needs and the CLI tools chosen for each need.
- `evidence_policy`: default `fetch_before_claim`.
- `preflight`: `doctor` guidance. `deep` does not execute this by default.
- `steps`: ordered CLI command steps.
- `gap_check`: how the agent verifies that key claims have fetched evidence or downgrades unsupported claims to unverified candidates.
- `final_answer_policy`: how to cite fetched evidence and list unverified candidates.
- `usage_boundary`: user-facing distinction between fast live `search`, offline `deep` planning, and later step execution.

Each `steps[]` item must include `id`, `subquestion_id`, `tool`, `purpose`, `command`, and `output_path`. Allowed `tool` values are `search`, `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`, and `map`; these map to existing CLI commands only. `doctor` is a `preflight` action, not a `steps[]` item. Default `output_path` values live under the platform temp directory as `<platform-temp-dir>/smart-search-evidence/<timestamp>-<slug>/...`; explicit `--evidence-dir PATH` values must be preserved as supplied.

Capability boundaries:

- `search`: broad discovery and synthesis through `main_search`; use returned `routing_decision`, `provider_attempts`, `fallback_used`, and `source_warning` as orchestration signals, not as claim proof.
- `zhipu-search`: Chinese, domestic, current, policy/regulatory, announcement, and China-local source discovery.
- `context7-library` and `context7-docs`: library, SDK, API, framework, and documentation intent. Prefer Context7 before Exa for docs/API questions.
- `exa-search`: low-noise source discovery for official domains, papers, product pages, known domains, and trusted pages. It is not the default second hop for every high-risk or verification task.
- `exa-similar`: adjacent-source discovery when a known reliable URL is available.
- `search --extra-sources N`: Tavily/Firecrawl horizontal candidate collection for breadth. Treat those candidates as discovery until fetched.
- `anysearch-domains` and `anysearch-search`: experimental vertical search. Inspect domains first, then search a selected domain; do not insert it into the default fallback chain.
- `fetch`: page-content evidence. Key claims require fetched page text under `fetch_before_claim`.
- `map`: site structure exploration before many fetches from one site; not claim evidence by itself.

Default Deep Research orchestration:

1. Run `smart-search doctor --format json` as preflight when configuration is uncertain.
2. Call `smart-search deep "question" --format json` to generate `intent_signals`, `decomposition`, and `capability_plan` instead of selecting a fixed topic recipe.
3. Use planned `smart-search search ... --validation balanced --extra-sources 1..3` steps for broad discovery.
4. Add planned `zhipu-search` for Chinese/current/domestic topics, `context7-library` plus `context7-docs` for docs/API/library topics, `exa-search` for official/trusted-domain or paper discovery, `exa-similar` for URL-neighbor discovery, or `map` only when the capability boundary matches the intent.
5. Use `fetch` for key URLs before making claim-level statements.
6. Run `gap_check`: fetch missing evidence for key claims or downgrade them to unverified candidates.

`fetch_before_claim` means key claims must be backed by fetched page content. `primary_sources` and `extra_sources` are discovery candidates until fetched. Final answers should include fetched evidence, unverified candidate sources, and key commands used.

When the user wants the CLI to execute the live workflow directly, call:

```powershell
# Windows explicit-output example
smart-search research "question" --budget deep --fallback auto --format json --output C:\tmp\smart-search-evidence\research.json
```

`research --fallback auto` permits same-capability fallback inside selected routes. `research --fallback off` tries only the first selected provider in each capability route and is for debugging or provider comparison. Dynamic routing may reorder providers only inside the same capability. Every attempt must record capability, provider, status, error type, latency, and result count.

Research provider advantage routing:

- Context7 first for library/API/framework docs and docs retrieval.
- Exa for official domains, papers, product/company pages, date/domain-filtered low-noise discovery, and adjacent-source discovery.
- Zhipu REST for Chinese, domestic, current, policy, and announcement searches.
- Zhipu MCP as a separate Coding Plan quota route through `web_search_prime` and `webReader`; do not mix it into `/paas/v4/web_search`.
- Tavily for broad source discovery and site maps.
- Jina for known public URL, PDF, and arXiv clean extraction; ReaderLM-v2 requires `JINA_API_KEY`.
- Firecrawl for robust fetch fallback, JS-heavy/dynamic/browser-like extraction, OCR/PDF/structured extraction.
- AnySearch only when vertical intent is clear, such as CVE, finance, legal, academic, and repository/codebase search.

Safe research overrides are `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`. They may reorder or disable providers only inside capabilities the provider already supports; they must not move a provider across capability boundaries.

Planner closeout lessons:

- Budget limits must not break evidence policy. Even `--budget quick` plans must retain at least one `fetch` step when claim-level conclusions are expected, and retained steps must keep valid `subquestion_id` links.
- `steps[].command` and `steps[].output_path` are one contract. The `--output` path embedded in the executable command must match `output_path`; otherwise the AI agent cannot reliably find saved evidence.
- Prefer PowerShell-safe quoted commands in generated plans because Windows users often copy planned steps directly from Markdown or JSON output.

Deep Research smoke coverage is mock-full plus live-limited. Mock-full coverage should cover trigger phrases, normal search requests that should not trigger Deep Research, required `research_plan` fields, allowed tool whitelist, `fetch_before_claim`, evidence paths, capability boundaries, `intent_signals`, `capability_plan`, `gap_check`, simple current prompts such as `深度搜索一下最近的比特币行情`, docs/API prompts, claim-verification prompts, user-provided URL fetch-first flows, missing-provider failure guidance, research provider advantage routing, same-capability research fallback, and the rule that fixed topic recipe ids are not required schema. Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch` when real keys are available and live checks are expected; add one small `research` smoke when configured keys make it stable. If a smoke issue is found, fix the affected docs/code/tests and rerun the affected smoke until it passes or is proven to be an external provider blocker.

Setup and config output should include `ok` and `config_file`. Saved API keys must be masked in command output.

Interactive setup behavior:

- Default `smart-search setup` shows a Smart Search ASCII banner, asks for `zh`
  or `en`, offers user-level `smart-search-cli` skill installation, then
  shows a grouped provider wizard.
- The grouped wizard should use an arrow-key / Space / Enter selector when the
  packaged TUI dependencies are available, with a text fallback for non-TTY
  and tests.
- Skill installation installs the bundled `smart-search-cli` skill into
  selected AI-tool skill directories and must not run `trellis init`, create
  hooks, create agents, create commands, or modify other skills. Targets are
  user-level/global directories under the current user's home directory, for
  example Codex `~/.codex/skills/`, Claude Code `~/.claude/skills/`, Cursor
  `~/.cursor/skills/`, GitHub Copilot `~/.copilot/skills/`, and Hermes Agent
  `~/.hermes/skills/`.
- Skill targets are `codex`, `claude`, `cursor`, `opencode`, `copilot`,
  `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`,
  `antigravity`, `windsurf`, and `hermes`. `--skip-skills` disables skill
  installation. `--install-skills codex,claude,cursor,hermes` selects targets
  explicitly, and `--skills-root PATH` is an advanced override for the
  user-level install root used in portable installs or tests. Normal users
  should omit it.
- `smart-search skills status --targets codex,claude,cursor,hermes --format json`
  compares bundled skill files with installed user-level skill directories.
  Status values are `missing`, `up_to_date`, `stale`, `extra_files`, and
  `error`. It reports target paths, bundled file count, installed file count,
  hashes, hash match flags, missing files, stale files, and extra files. It
  must not write or delete files.
- `smart-search skills update --targets codex,claude,cursor,hermes --format json`
  overwrites the managed bundled `smart-search-cli` files for selected
  targets. `smart-search skills update --all --format json` selects every
  target id. This daily sync path must not change provider keys, run setup
  prompts, create Trellis files, create hooks, create agents, create commands,
  or delete leftover files. Extra installed files are only reported by
  `skills status`.
- `smart-search setup --non-interactive --install-skills codex` remains the
  first-time setup compatibility path. Prefer `skills status` and
  `skills update` for routine global skill synchronization after CLI upgrades.
- Required groups are `main_search`, `docs_search`, and `web_fetch`; `web_search` is optional reinforcement, followed by optional smart intent router configuration.
- `--lang zh|en` skips the language question.
- Default guided setup can configure `SMART_SEARCH_INTENT_ROUTER`, `INTENT_EMBEDDING_*`, `INTENT_CLASSIFIER_*`, and `INTENT_ROUTER_TIMEOUT_SECONDS` without `--advanced`; missing remote router pieces still degrade to rules.
- Default guided setup recommends SiliconFlow + `Qwen/Qwen3-Embedding-8B` for embeddings and auto-fills threshold `0.475` plus margin `0.053` when no explicit threshold/margin exists.
- `--advanced` shows low-level config keys one by one for compatibility with older setup behavior and does not show the skill prompt unless `--install-skills` is explicit.
- `--non-interactive` keeps script behavior and only saves values passed as flags.
- Unchecking a configured provider must not delete existing config values; use
  `smart-search config unset KEY` for deletion.
- Interactive output should summarize `minimum_profile_ok`, missing required capabilities, and next-step commands.
- Beginner filling examples for official-service and relay/pooled-endpoint
  minimum profiles must appear in the grouped wizard on stderr, not stdout.
  They must cover `main_search`, `docs_search`, and `web_fetch` so a first-time
  user can satisfy the minimum profile without understanding provider internals.

Provider endpoint setup:

- `TAVILY_API_URL` defaults to `https://api.tavily.com`.
- `TAVILY_TIMEOUT_SECONDS` defaults to `30` and applies to Tavily `doctor`
  connectivity checks.
- `ANYSEARCH_API_URL` defaults to `https://api.anysearch.com/mcp`.
- `ANYSEARCH_TIMEOUT_SECONDS` defaults to `30` and applies to experimental
  AnySearch JSON-RPC calls.
- Tavily Hikari / pooled endpoints must use the REST facade base
  `https://<host>/api/tavily`; `/mcp` is not a REST provider base.
- Setup normalizes a Hikari root host or `/mcp` URL to
  `https://<host>/api/tavily`; an existing `/api/tavily` base and official
  `https://api.tavily.com` remain unchanged.
- `FIRECRAWL_API_URL` defaults to `https://api.firecrawl.dev/v2`; custom REST
  bases are saved with scheme normalization and no trailing slash.

Search timeout output uses `ok=false`, `error_type=network_error`, includes the timeout seconds in `error`, keeps `query`, `content`, `sources`, `sources_count`, `primary_sources`, `primary_sources_count`, `extra_sources`, and `extra_sources_count`, and exits with code `4`.

Agent timeout handling contract:

- A `search` result with `ok=false`, `error_type=network_error`, and an `error` message containing `timed out` is retryable at the orchestration layer.
- Agents should retry up to 3 total attempts with `smart-search search ... --timeout 180 --extra-sources 1 --format json --output PATH`, waiting about 5 seconds between attempts and stopping as soon as the saved JSON has `"ok": true`.
- Agents must use the CLI `--timeout` option, not a shell-level `timeout` wrapper, so timeout failures remain structured JSON with exit code `4`.
- `SMART_SEARCH_RETRY_*` settings are not the contract for this path; the visible CLI result is the contract.
- After repeated timeout failures, agents should switch to source-first fallback: `exa-search` for broad source discovery, `exa-search --include-domains` for likely official domains, then `fetch` key URLs before claim-level conclusions.
- Final answers assembled through that fallback should explicitly label the evidence mode, for example `source_mode: "fallback"` or equivalent prose.

## Provider Routing

- `search` builds `main_search` from peer providers only: `XAI_API_KEY` registers official xAI Responses, while `OPENAI_COMPATIBLE_API_URL` + `OPENAI_COMPATIBLE_API_KEY` registers OpenAI-compatible Chat Completions.
- `search` uses unified `IntentRouter` output to populate `required_capabilities` and `supplemental_paths`; provider execution still follows the capability registry and same-capability fallback.
- `research` reuses the unified `IntentRouter` before provider-advantage ordering.
- `deep` uses offline rules/local signals only; it must not call remote embeddings or classifier components.
- Official xAI calls use the Responses API `/responses` route through `XAI_*`. Compatible relays/gateways use Chat Completions `/chat/completions` through `OPENAI_COMPATIBLE_*`.
- `OPENAI_COMPATIBLE_STREAM` and `search --stream/--no-stream` affect only the OpenAI-compatible Chat Completions transport for search/fetch. They do not change xAI Responses or provider-internal ranking/URL description tasks.
- Legacy `SMART_SEARCH_API_URL`, `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and `SMART_SEARCH_XAI_TOOLS` are unsupported config keys. `config set` / `config unset` must return a parameter error for them.
- `XAI_TOOLS` applies only to xAI Responses mode and supports only `web_search` and `x_search`.
- Chat Completions mode must not send xAI `web_search` / `x_search` tools or legacy `search_parameters`; xAI Chat Completions Live Search is deprecated.
- Standard minimum profile requires `main_search`, `docs_search`, and fetch capability. Missing required capabilities produce a configuration error.
- Optional experimental `vertical_search` may report AnySearch when `ANYSEARCH_API_KEY` is configured, but it is not part of the `web_search` fallback and is not required by the `standard` minimum profile.
- Jina satisfies fetch capability only when `JINA_API_KEY` is configured. Anonymous Jina Reader does not satisfy `standard`.
- Same-capability fallback is allowed; cross-capability fallback is not. Context7 is not used for unrelated broad web queries, and page extraction providers are not used as docs search providers.
- `main_search`: xAI Responses first for Grok/xAI, then OpenAI-compatible answer fallback when that peer provider is separately configured and `--fallback auto` is active.
- `web_search`: Zhipu Web Search API first when routed in, then Zhipu Coding Plan MCP `web_search_prime`, then Tavily / Firecrawl source search when configured.
- `docs_search`: Context7 first for library/API/docs intent, then Exa for official-domain, paper, product-page, trusted-site, or low-noise supplemental discovery.
- Fetch capability: Tavily first, then Jina Reader with `JINA_API_KEY`, then Zhipu Coding Plan MCP `webReader`, then Firecrawl.
- `search` calls Tavily and/or Firecrawl only when `--extra-sources` is greater than 0.
- If both Tavily and Firecrawl are configured, `search --extra-sources N` gives about 60% of extra source slots to Tavily and the remainder to Firecrawl.
- `extra_sources` are retrieved in parallel and are not automatically used by the primary model to verify its answer.
- `fetch` and known-URL `search "https://..."` use the same fetch fallback chain.
- `fetch` tries Tavily first, then Jina Reader with `JINA_API_KEY`, then Zhipu Coding Plan MCP Reader, then Firecrawl.
- `research` uses capability-first plus provider-advantage routing. Fallback remains same-capability only; low-quality fetches, challenge pages, empty content, auth/rate/timeout/provider errors, and runtime errors are failed attempts that may trigger same-capability fallback.
- `map` uses Tavily only.
- `exa-search` and `exa-similar` use Exa only.
- `zhipu-search` uses Zhipu only.
- `zhipu-mcp-search`, `zhipu-mcp-reader`, and `zhipu-mcp-*` zread commands use Zhipu Coding Plan Remote MCP only.
- `anysearch-domains`, `anysearch-search`, `anysearch-extract`, and `anysearch-batch` use AnySearch only and do not participate in default fallback chains.
- `context7-library` and `context7-docs` use Context7 only.
- Runtime config priority is environment variables first, then local config file, then defaults.
- `setup` and `config` read/write the local Smart Search config file and do not call providers.
- `model current` reports explicit provider model settings. `model set` is retained only as a parameter-error migration guard; use `config set XAI_MODEL ...` or `config set OPENAI_COMPATIBLE_MODEL ...` to change models.

## Routing Heuristics

- Use `smart-search route "query" --format markdown` when you need to explain why a query maps to `docs_search`, `web_search`, `web_fetch`, or `vertical_search` without executing providers.
- Use `exa-search --include-domains` when official documentation domains are known.
- Use `context7-library` / `context7-docs` for docs/API/SDK/library/framework intent when Context7 is configured.
- Use `zhipu-search` for Chinese, domestic, current, or domain-filtered source discovery when Zhipu is configured.
- Use `exa-search --start-published-date` for recency-constrained source discovery.
- Use `exa-similar` when a known good page is available and adjacent sources are needed.
- Use `search --format content` when a human wants only the generated answer body.
- Use `fetch --format markdown` or `fetch --format content` for user-supplied URLs or when exact page text matters.
- Use `map` before fetching many pages from a documentation site.
- Keep `search --extra-sources` small (`1` to `3`) unless broad coverage is requested.
- For current news or high-risk claims, prefer source discovery plus `fetch`; do not treat broad `search.content` plus `extra_sources` as claim-level verification.

## Maintenance Guardrails

- Provider architecture changes must be verified as distributable CLI behavior, not as behavior that only works because one developer machine has a specific wrapper, shell profile, or local config file.
- Register providers by capability first, then route by intent. Fallback is allowed only within the same capability.
- Keep xAI Responses and OpenAI-compatible as peer `main_search` providers. A failed xAI Responses request may fall back to OpenAI-compatible only when `OPENAI_COMPATIBLE_API_URL` and `OPENAI_COMPATIBLE_API_KEY` are separately configured.
- Do not use Context7 for broad news or generic web facts; do not use Tavily or Firecrawl as documentation semantic-search replacements.
- Standard installs must fail closed unless `main_search`, `docs_search`, and fetch capability each have at least one configured provider.
- After provider-routing changes, run source-checkout regression plus `smart-search smoke --mock --format json`. If live keys were used, run a targeted secret scan for exact key substrings before committing.

## Exit Codes

- `0`: success
- `2`: parameter error
- `3`: configuration error
- `4`: network or upstream error
- `4`: also used for strict insufficient-evidence search failures
- `5`: runtime or parse error

## Regression

Run `smart-search regression` before considering CLI or skill changes complete.

- In a source checkout, it runs offline pytest coverage for CLI, service, smoke, provider, and skill contract behavior.
- In npm / mise packaged installs, repository test files are not bundled; since v0.1.8 it falls back to built-in mock smoke regression so users can still verify installed CLI health.
- For release validation, use a source checkout for full pytest-backed regression and use packaged-install regression only as an install-health check.

## Release Lanes

- Stable releases are pushed as `vX.Y.Z` Git tags and publish npm `X.Y.Z` with dist-tag `latest`.
- Test releases are pushed from `main` and publish `<package.json version>-beta.N` with dist-tag `next`. The beta counter resets per base version, so `0.1.9-beta.1` and `0.1.10-beta.1` are separate sequences.
- Stable bump commits must use `chore(release): bump version to X.Y.Z`; the branch push is skipped by the npm workflow so the matching `vX.Y.Z` tag is the only publisher for npm `latest`.
- Stable GitHub release notes should be stored as `.github/releases/vX.Y.Z.md` before tagging. The publish workflow appends npm package, dist-tag, and workflow-run metadata to that body automatically.
- Historical test builds can be backfilled through GitHub Actions `workflow_dispatch` by supplying an explicit `target_ref`, exact `version`, and a non-`latest` npm tag such as `backfill`.
- npm versions are immutable. Old `*-dev.*` packages cannot be renamed in place; publish replacement `*-beta.N` packages and optionally deprecate the old names when npm owner credentials are available.

### Release Closeout Lessons

- Always read back npm before and after publishing with `npm view @konbakuyomu/smart-search versions --json` and `npm view @konbakuyomu/smart-search dist-tags --json`. A test release must leave `latest` on the stable version and move only `next` or the explicitly supplied non-`latest` tag.
- Backfill jobs can publish npm successfully even if GitHub release creation fails because the workflow token cannot access the release API. In that case, leave npm intact and create the missing GitHub prerelease with authenticated local `gh release create ... --prerelease --latest=false`.
- If concurrent backfill jobs hit npm `E409`, re-dispatch only the affected versions serially after checking whether the version already appeared in the registry.
- Finish with a diff-style gap check: expected beta version list minus npm versions equals empty, and expected `vX.Y.Z-beta.N` list minus GitHub prereleases equals empty.
- Local verification after a test release must use an exact install target, such as `mise use -g "npm:@konbakuyomu/smart-search@0.1.10-beta.3" -y --pin`, followed by `mise reshim`, `where.exe smart-search`, `smart-search --version`, packaged `smart-search regression`, and `smart-search smoke --mock --format json`. Also pipe a non-ASCII JSON command such as `smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json` to verify the Windows npm/mise wrapper is emitting UTF-8 JSON, not locale-encoded bytes.

## Tool Policy

Web research through this skill should use `smart-search` CLI. If the CLI is unavailable, report the blocker and recovery steps instead of silently falling back to another web-search route.
