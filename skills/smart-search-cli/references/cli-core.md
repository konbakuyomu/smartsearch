# CLI Core

## Table of Contents

- Entrypoints
- Commands
- Aliases
- Output format expectations
- Exit codes
- Tool policy

## Entrypoints

- `smart-search` is the primary CLI and should resolve from the user's PATH.
- `smart-search --version`, `smart-search --v`, and `smart-search -v` print the installed version and exit with code `0`.
- This bundled skill is maintained with the `smartsearch` repository.
- Private API keys should be saved with `smart-search setup` or `smart-search config set`; environment variables remain supported for CI and advanced users.
- Do not depend on MCP inline `env` values or committed API-key environment variables for CLI use.
- On Windows with mise, the managed package name is `npm:@konbakuyomu/smart-search`; the executable remains `smart-search`. Diagnose mise managed installs with `mise ls "npm:@konbakuyomu/smart-search"` and `mise which smart-search`.

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
- `smart-search config path|list|set|unset ... [--format json|markdown|content] [--output PATH]`
- `smart-search model set MODEL [--format json|markdown|content] [--output PATH]`
- `smart-search model current [--format json|markdown|content] [--output PATH]`
- `smart-search regression`
- `smart-search smoke [--mode mock|live] [--mock] [--live] [--format json|markdown|content] [--output PATH]`

## Aliases

Top-level aliases normalize to the same service behavior as their full command: `search`/`s`, `route`/`rt`, `fetch`/`f`, `map`/`m`, `exa-search`/`exa`/`x`, `exa-similar`/`xs`, `zhipu-search`/`z`/`zp`, `zhipu-mcp-search`/`zmcp-search`, `zhipu-mcp-reader`/`zmcp-reader`, `zhipu-mcp-search-doc`/`zmcp-doc`, `zhipu-mcp-repo-structure`/`zmcp-tree`, `zhipu-mcp-read-file`/`zmcp-file`, `anysearch-domains`/`as-domains`, `anysearch-search`/`as-search`/`as`, `anysearch-extract`/`as-extract`, `anysearch-batch`/`as-batch`, `context7-library`/`c7`/`ctx7`, `context7-docs`/`c7d`/`c7docs`/`ctx7-docs`, `deep`/`dr`, `research`/`rs`, `route-calibrate`/`route-cal`/`rcal`, `doctor`/`d`, `diagnose`/`diag`, `setup`/`init`, `config`/`cfg`, `model`/`mdl`, `smoke`/`sm`, and `regression`/`reg`.

Nested aliases: `config path`/`cfg p`, `config list`/`cfg ls`/`cfg l`, `config set`/`cfg s`, `config unset`/`cfg rm`/`cfg u`, `model current`/`mdl cur`/`mdl c`, and `model set`/`mdl s`.

## Output Format Expectations

- `--format json` is the stable machine-readable contract for agents and scripts. JSON output remains parseable and uses readable non-ASCII text when the terminal encoding supports it.
- `--format markdown` is the human-readable report format. `route --format markdown`, `route-calibrate --format markdown`, `doctor --format markdown`, and `diagnose openai-compatible --format markdown` must render useful reports rather than raw JSON dumps.
- `--format content` prints only the `content` field for content-bearing commands such as `search`, `fetch`, `context7-docs`, and `research`. Commands without a `content` field, including `route`, `route-calibrate`, `doctor`, `smoke`, `config`, and `model`, must print a compact non-empty text summary.
- Successful search output includes `ok`, `query`, `primary_api_mode`, `content`, `sources`, `sources_count`, `primary_sources`, `primary_sources_count`, `extra_sources`, `extra_sources_count`, `source_warning`, `routing_decision`, `providers_used`, `provider_attempts`, `fallback_used`, `validation_level`, and `elapsed_ms`.
- Route diagnostic output includes `ok`, `query`, `executed_search=false`, `provider_selection=not_executed`, backward-compatible fields `docs_intent`, `zh_current_intent`, `web_current_intent`, `fetch_intent`, `supplemental_paths`, and unified intent-router fields `intent_router_mode`, `required_capabilities`, `intent_signals`, `confidence`, `router_engines_used`, `degraded`, `degraded_reason`, `reasons`, `embedding_model`, `embedding_threshold`, `embedding_margin`, `embedding_threshold_source`, and `embedding_margin_source`. `smart-search route` must not call search/docs/fetch providers.
- Route calibration output includes `ok`, `metric`, `primary_metric=semantic_macro_f1`, `full_route_metric_role=validation`, `models`, `model_results`, `dataset_size`, `dataset_counts`, `capabilities`, `recommended_model`, `recommended_threshold`, `recommended_margin`, and `failed_models`.
- Fetch output includes `ok`, `url`, `provider`, `content`, `provider_attempts`, `fallback_used`, and `elapsed_ms`.
- Exa search output includes `ok`, `query`, `search_type`, `results`, `total`, and `elapsed_ms`. Exa similar output includes `ok`, `url`, `results`, `total`, and `elapsed_ms`.
- Zhipu search output includes `ok`, `query`, `provider`, `search_engine`, `results`, `total`, and `elapsed_ms`.
- Zhipu MCP command output includes `ok`, `provider`, `tool`, `elapsed_ms`, and either `content` for reader/file-like tools or `results` plus `total` for search-like tools.
- Context7 library output includes `ok`, `query`, `provider`, `results`, `total`, and `elapsed_ms`; Context7 docs output also includes `library_id`, `content`, and result metadata.
- Map output includes `ok`, `base_url`, `results`, `response_time`, `url`, and `elapsed_ms`.
- Deep planner output includes `ok`, `mode`, `query_mode`, `question`, `trigger_source`, `difficulty`, `intent_signals`, `decomposition`, `capability_plan`, `evidence_policy`, `preflight`, `steps`, `gap_check`, `final_answer_policy`, `usage_boundary`, `allowed_tools`, `evidence_dir`, and `elapsed_ms`.
- Research executor output includes `ok`, `mode=deep_research_execution`, `query_mode=research`, `question`, `budget`, `research_plan`, `routing_decision`, `stage_results`, `discovery_sources`, `final_answer`, `content`, `citations`, `evidence_items`, `gap_check`, `provider_attempts`, `providers_used`, `fallback_used`, `degraded`, `route_policy_version`, `evidence_dir`, `minimum_profile_ok`, `capability_status`, and `elapsed_ms`.
- Diagnostic output masks keys and reports config paths, Windows legacy config metadata, provider timeout values, `capability_status`, `minimum_profile_ok`, `intent_router_status`, `main_search_connection_tests`, and provider connectivity checks. OpenAI-compatible health must be validated through `/chat/completions`; `/models` is supplementary metadata.
- Smoke output includes `ok`, `mode`, `failed_cases`, `cases`, `provider_attempts`, and `elapsed_ms`. Live smoke may include `degraded_cases` when a provider fails but a same-capability fallback remains available.

## Exit Codes

- `0`: success
- `2`: parameter error
- `3`: configuration error
- `4`: network or upstream error, also used for strict insufficient-evidence search failures
- `5`: runtime or parse error

## Tool Policy

Web research through this skill should use `smart-search` CLI. If the CLI is unavailable, report the blocker and recovery steps instead of silently falling back to another web-search route.
