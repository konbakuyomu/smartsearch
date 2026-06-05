---
name: smart-search-cli
description: CLI-first web research and source retrieval through the local smart-search command. Use when Codex needs current web search, source-backed fact checking, URL fetching, site mapping, official/API/documentation search, or reproducible search evidence via Skill + CLI instead of MCP tools.
---

# Smart Search CLI

Use the local `smart-search` command as the default execution layer for web research. The skill decides routing; the CLI performs the work; JSON or saved files provide evidence.

## Default workflow

1. Run `smart-search doctor --format json` when configuration or availability is uncertain.
2. If `doctor` reports missing configuration, use `smart-search setup` or `smart-search config set KEY VALUE` when the user provides keys. Do not ask users to edit global environment variables by default.
3. If OpenAI-compatible `search` hangs or times out after `doctor` succeeds, run `smart-search diagnose openai-compatible --format markdown` and use its summary/recommendation. This one command tests quick chat plus real search-shape `stream=false` and `stream=true`.
4. If `doctor` returns `ok: true`, use only `smart-search` CLI subcommands for web research. Do not call Codex native web search in the same task.
5. Use `smart-search skills status --targets codex --format json` when the global skill may be stale; use `smart-search skills update --targets codex --format json` to refresh this skill without rerunning setup.
6. Use `smart-search smoke --mock --format json` after CLI/provider architecture changes. Use `--live` only when real keys are available and the user expects live checks.
7. Use `smart-search search` as the first hop for realtime, broad exploration, community signals, multi-source summaries, and routing metadata.
8. Use `smart-search zhipu-search` for Chinese-language, domestic China, policy/regulatory, announcements, current news, or China-local source discovery.
9. Use `smart-search context7-library` / `context7-docs` first for library, SDK, API, framework, or documentation intent.
10. Use `smart-search exa-search` for official domains, papers, product pages, trusted sites, and low-noise discovery. Do not treat Exa as the universal second hop for every high-risk or verification task.
11. Use `smart-search search --extra-sources N` for Tavily/Firecrawl horizontal candidates, and `smart-search fetch` for page text that can support final claims.
12. Use `smart-search anysearch-*` only for explicit experimental vertical search: call `anysearch-domains` first, then `anysearch-search` in a selected domain. Do not use AnySearch as default fallback.
13. Use `smart-search exa-similar` when the user gives a representative URL and wants related pages or neighboring sources.
14. Use `smart-search fetch` when the user gives a URL or a claim depends on page content.
15. Use `smart-search map` when a documentation site or domain structure matters.
16. Use `smart-search model current` only to inspect explicit provider models. To change models, use `smart-search config set XAI_MODEL ...` or `smart-search config set OPENAI_COMPATIBLE_MODEL ...`.
17. For current-news, policy, finance, health, or other high-risk facts, do not answer from broad `search.content` alone. Select the second source by intent: Zhipu for Chinese/current/domestic, Context7 for docs/API, Exa for official/trusted domains or papers, then `fetch` key pages and summarize only what fetched text supports.
18. Use `smart-search research "question" --format json` when the user wants the CLI to run live Deep Research end to end instead of only planning. It executes plan -> discover -> fetch/read -> gap check -> evidence-only synthesis.
19. Preserve command lines and source URLs in your answer. Prefer citing fetched pages or `primary_sources`; treat `extra_sources` as follow-up candidates, not verified evidence for generated claims.

## Deep Research Mode

Use Deep Research Mode when the user asks for `深度搜索`, `深度调研`, `深入搜索`, `deep search`, `deep research`, multi-source verification, cross-checking, serious review, or selection/comparison research. This is a capability-based orchestration workflow. The offline route calls `smart-search deep "question" --format json` to get a plan, then composes existing `smart-search` CLI building blocks. The live executor route calls `smart-search research "question" --format json` and lets the CLI execute plan -> discover -> fetch/read -> gap check -> evidence-only synthesis. `smart-search deep` is a public planner entrypoint, not an executor; it does not call providers, run `doctor`, or fetch pages by default. `smart-search research` is the public live executor entrypoint. This does not change default `smart-search search`, and it does not depend on an MCP session.

Do not select a fixed topic recipe. Market, product, technical docs, news, policy, claim-checking, and URL-first prompts are examples of user language, not schema modes. Decide from intent dimensions and capability needs.

Before running deep research commands, run `smart-search deep "question" --format json` and use the returned `research_plan` as your planning artifact. Use this shape:

```json
{
  "mode": "deep_research",
  "query_mode": "deep",
  "question": "user question",
  "trigger_source": "explicit_cli",
  "difficulty": "standard|high",
  "intent_signals": {
    "recency_requirement": "none|recent|current",
    "docs_api_intent": false,
    "locale_domain_scope": "global|china|known_domains|mixed",
    "known_url": false,
    "source_authority_need": "normal|high",
    "claim_risk": "low|medium|high",
    "cross_validation_need": "normal|high",
    "breadth_depth_budget": "quick|standard|deep"
  },
  "decomposition": [
    {
      "id": "sq1",
      "question": "subquestion",
      "reason": "why this subquestion is needed",
      "required_capabilities": ["broad_discovery"]
    }
  ],
  "capability_plan": [
    {
      "capability": "broad_discovery",
      "tools": ["search"],
      "reason": "Find the initial answer shape and candidate sources."
    }
  ],
  "preflight": {
    "tool": "doctor",
    "command": "smart-search doctor --format json",
    "when": "configuration or availability is uncertain"
  },
  "evidence_policy": "fetch_before_claim",
  "steps": [
    {
      "id": "s1",
      "subquestion_id": "sq1",
      "tool": "search",
      "purpose": "broad discovery",
      "command": "smart-search search \"query\" --validation balanced --extra-sources 1 --format json --output C:\\tmp\\smart-search-evidence\\YYYYMMDD-HHMM-topic\\01-search.json",
      "output_path": "C:\\tmp\\smart-search-evidence\\YYYYMMDD-HHMM-topic\\01-search.json"
    }
  ],
  "gap_check": {
    "required": true,
    "rule": "fetch missing evidence for key claims or downgrade them to unverified candidates"
  },
  "final_answer_policy": "cite fetched evidence, list unverified candidates, and include key commands",
  "usage_boundary": {
    "search": "smart-search search runs live fast/broad search immediately.",
    "deep": "smart-search deep is an offline planner; it does not execute provider calls or fetch pages.",
    "execution": "An AI agent or user executes the listed steps with existing CLI commands, then performs gap_check."
  }
}
```

Allowed `steps[].tool` values are `search`, `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`, and `map`. Each step must include `id`, `subquestion_id`, `purpose`, `command`, and `output_path`. `doctor` is preflight and must not appear in `steps[]`. Simple plans may have one subquestion; complex plans should use 2-6 subquestions unless the user explicitly asks for exhaustive coverage.

Capability boundaries:

- `search`: broad discovery and synthesis through `main_search`; inspect `routing_decision`, `provider_attempts`, `fallback_used`, and `source_warning`. Do not treat broad answers as proof for high-risk claims.
- `zhipu-search`: Chinese, domestic, current, policy/regulatory, announcement, and China-local source discovery.
- `context7-library` / `context7-docs`: library, SDK, API, framework, and documentation intent. Prefer Context7 before Exa for docs/API questions.
- `exa-search`: low-noise discovery for official domains, papers, product pages, known domains, and trusted pages. Use it when that boundary fits; it is not the default second hop for every verification task.
- `exa-similar`: adjacent-source discovery when a known reliable URL is available.
- `search --extra-sources N`: Tavily/Firecrawl horizontal candidate collection for breadth. Treat those candidates as discovery until fetched.
- `anysearch-domains` / `anysearch-search`: experimental vertical search. Inspect domains first, then search a selected domain; do not insert it into the default fallback chain.
- `fetch`: page-content evidence. Use it before claim-level conclusions.
- `map`: site structure exploration before many fetches from one site; not claim evidence by itself.

Default Deep Research orchestration:

1. Run `smart-search doctor --format json` as preflight when configuration is uncertain.
2. Call `smart-search deep "question" --format json` to create an offline `research_plan`.
3. Inspect `intent_signals`, `decomposition`, and `capability_plan`; do not choose fixed topic recipe ids.
4. Execute planned `search --validation balanced --extra-sources 1..3` steps for broad discovery and read routing metadata.
5. Execute planned `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, or `map` only when their capability boundary matches the intent.
6. Use `fetch` on key URLs before making claim-level statements.
7. Run `gap_check`: if an important claim lacks fetched evidence, fetch another source or mark the claim/source as unverified.

Default evidence policy is `fetch_before_claim`: key claims in the final answer must be supported by fetched page text. Treat `primary_sources` and `extra_sources` as discovery candidates until the relevant URL has been fetched. The final answer should include fetched evidence, unverified candidate sources, and key commands used.

Live Deep Research executor:

- `smart-search research QUERY [--budget quick|standard|deep] [--evidence-dir PATH] [--fallback auto|off] [--format json|markdown|content] [--output PATH]` runs the staged workflow directly.
- Default `--fallback auto` permits same-capability fallback inside selected routes. Use `--fallback off` only for debugging or deterministic provider checks.
- Research output includes `final_answer`, `citations`, `evidence_items`, `gap_check`, `provider_attempts`, `fallback_used`, `degraded`, `route_policy_version`, and `evidence_dir`.
- The synthesis is evidence-only. It may cite fetched/read evidence, but it must not cite unfetched discovery candidates as proof.
- If providers are exhausted or evidence cannot close, return the degraded gaps rather than inventing missing claims.

Research provider advantage routing:

- Context7: library/API/framework docs resolution and docs retrieval.
- Exa: official domains, papers, product/company pages, date/domain-filtered low-noise discovery, and adjacent-source discovery.
- Zhipu REST: Chinese, domestic, current, policy, and announcement searches.
- Zhipu MCP: separate Coding Plan quota route through `web_search_prime` and `webReader`.
- Tavily: broad source discovery and site map.
- Jina: known public URL, PDF, and arXiv clean extraction; ReaderLM-v2 requires `JINA_API_KEY`.
- Firecrawl: robust fetch fallback, JS-heavy/dynamic pages, browser-like extraction, OCR/PDF/structured extraction.
- AnySearch: explicit vertical intent only, such as CVE, finance, legal, academic, and repository/codebase search.

Safe research overrides are `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`. They may reorder or disable providers only within capabilities the provider already supports; they must not move a provider across capability boundaries.

Deep Research smoke matrix for workflow maintenance is mock-full plus live-limited. Mock-full coverage should include trigger phrases, normal search requests that should not trigger Deep Research, required `research_plan` fields, allowed tool whitelist, `fetch_before_claim`, evidence output paths, capability boundaries, `intent_signals`, `capability_plan`, `gap_check`, simple current prompts such as `深度搜索一下最近的比特币行情`, docs/API prompts, claim-verification prompts, user-provided URL fetch-first flows, missing-provider failure guidance, and the rule that fixed topic recipe ids are not required schema. Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch` only when real keys are available and the user expects live checks.

Standard user-facing Deep Research tests:

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search deep "帮我核验这个说法是真是假：某某工具已经完全替代 Tavily 做 AI 搜索了" --format json
smart-search deep "https://example.com/source" --format json
```

## Provider Routing

- `search` builds `main_search` from configured peer providers: `XAI_API_KEY` for xAI Responses and `OPENAI_COMPATIBLE_API_URL` + `OPENAI_COMPATIBLE_API_KEY` for OpenAI-compatible Chat Completions.
- `search` is the default first hop for broad exploration, current synthesis, and routing metadata.
- Official xAI uses the Responses API `/responses` route through `XAI_*`. Compatible relays/gateways use Chat Completions `/chat/completions` through `OPENAI_COMPATIBLE_*`.
- `OPENAI_COMPATIBLE_STREAM=true` or `search --stream` sets `stream=true` only for OpenAI-compatible `search` and provider-side `fetch`; it is a relay compatibility switch and does not affect xAI Responses, URL description, or source ranking.
- Legacy `SMART_SEARCH_API_URL`, `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and `SMART_SEARCH_XAI_TOOLS` are unsupported config keys.
- xAI Responses mode may use only `XAI_TOOLS=web_search,x_search` and a subset of those tools.
- Chat Completions mode must not send xAI `web_search` / `x_search` tools or legacy `search_parameters`; xAI Chat Completions Live Search is deprecated.
- The standard minimum profile requires one configured provider in each of `main_search`, `docs_search`, and fetch capability. Missing required capabilities should be treated as a hard configuration failure.
- AnySearch is reported only as optional experimental `vertical_search`; it is not part of the `web_search` fallback and is not required by the `standard` minimum profile.
- Jina Reader is `web_fetch` only, not a general search provider. `JINA_API_KEY` is required before Jina satisfies the standard minimum profile; anonymous `r.jina.ai` is explicit/experimental fetch behavior.
- `search` exposes `--validation fast|balanced|strict`, `--fallback auto|off`, and `--providers auto|CSV`. Default validation is `balanced`; fallback only happens within the same capability.
- xAI Responses is the default main answer route for Grok/xAI. In `fallback=auto`, a failed xAI Responses main route can fall back to OpenAI-compatible only when the OpenAI-compatible provider is separately configured.
- Docs/API/library routing should prefer Context7 first. Exa is for official-domain or low-noise supplemental discovery, not the default docs answer route.
- Zhipu Web Search API is a general web-search reinforcement and same-capability fallback for Chinese, domestic, current, or domain-filtered source discovery.
- Zhipu Coding Plan Remote MCP is a separate route: `web_search_prime` maps to `web_search`, `webReader` maps to `web_fetch`, and zread tools map to explicit repo/docs discovery commands. Do not mix it into the existing `/paas/v4/web_search` REST provider.
- `search` calls Tavily and/or Firecrawl only when `--extra-sources N` is greater than 0.
- With both Tavily and Firecrawl configured, `search --extra-sources N` splits extra sources between them, with Tavily receiving about 60% and Firecrawl the rest.
- Search JSON separates `primary_sources`, `extra_sources`, and backward-compatible merged `sources`.
- `primary_sources` are extracted from the primary model answer. `extra_sources` are parallel Tavily / Firecrawl candidates and are not automatically used to verify `content`.
- `fetch` tries Tavily first, then Jina with `JINA_API_KEY`, then Zhipu Coding Plan MCP Reader, then Firecrawl.
- `map` currently uses Tavily only.
- `exa-search` and `exa-similar` use Exa only.
- `context7-library` and `context7-docs` use Context7 only.
- `anysearch-domains`, `anysearch-search`, `anysearch-extract`, and `anysearch-batch` use AnySearch only. Treat results as acceptance evidence until the target vertical domain is reviewed.
- `zhipu-search` uses Zhipu only.
- `zhipu-search` corresponds to the official Zhipu Web Search API route, using `ZHIPU_API_URL` plus `ZHIPU_SEARCH_ENGINE`; it is not Zhipu Chat Completions `tools=[web_search]`, not Search Agent, and not the MCP Server.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`. Official Web Search API service values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`; keep custom values possible because official services may change.
- `TAVILY_API_URL` only affects Tavily REST calls and does not proxy Zhipu. Zhipu defaults to `https://open.bigmodel.cn/api` unless `ZHIPU_API_URL` is set.
- `doctor` tests configured main-search providers, Exa, Tavily, Jina, Zhipu Web Search API, Zhipu Coding Plan MCP, and Context7 connectivity. Firecrawl status currently means the key is configured, not that a live Firecrawl request succeeded.

## Evidence Files

For multi-source research, use `--output` to save evidence under `C:\tmp\smart-search-evidence\` with a descriptive timestamped filename. Stdout should still contain the full JSON result unless markdown or content output was explicitly chosen for human reading.

For claim-level evidence, prefer this order:

1. Discover candidate URLs with source-focused `search`, `zhipu-search` for Chinese/current/domestic topics, Context7 for docs/API/library topics, or `exa-search` for official/trusted domains and papers.
2. Fetch the exact pages that matter.
3. Use broad `search` only as synthesis or discovery, and mark claims as unverified when only `extra_sources` are available.

Prefer shorter, source-directed commands:

```powershell
smart-search exa-search "Reuters Iran Hormuz latest" --num-results 5 --include-highlights --format json --output C:\tmp\smart-search-evidence\iran-hormuz-exa.json
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format json --output C:\tmp\smart-search-evidence\source-fetch.json
smart-search search "Iran Hormuz latest military talks" --extra-sources 3 --timeout 90 --format json --output C:\tmp\smart-search-evidence\iran-hormuz-search.json
```

## Local wrapper contract

- Expect `smart-search` to resolve from the user's PATH.
- This bundled skill is maintained with the `smartsearch` repository.
- Prefer the CLI's local config file managed by `smart-search setup` / `smart-search config`.
- Environment variables remain supported for CI and advanced users, and override the local config file.
- Do not ask users to set Windows global API-key environment variables by default.
- If keys are changed with `smart-search config set`, rerun the CLI; no Codex restart is needed.
- If PATH is changed, a new terminal or Codex restart may be needed.
- On Windows, the default local config file is `%LOCALAPPDATA%\smart-search\config.json`. Linux/macOS default to `~/.config/smart-search/config.json`.
- In sandboxed runtimes (Codex CLI, containers, CI) where the default config directory is not writable or must be pinned, set `SMART_SEARCH_CONFIG_DIR` to an absolute writable path. The CLI uses it for both config and relative logs and skips default-directory selection.
- Earlier Windows source defaults used `~\.config\smart-search\config.json`, while some installs were already pinned to `%LOCALAPPDATA%\smart-search` through `SMART_SEARCH_CONFIG_DIR`. If the new default file is missing but the old file exists, `doctor` reports `legacy_windows_home` as the active source so upgrades do not silently lose configuration. It also reports the override value and whether it matches the current default.
- Use `smart-search doctor --format json` for agent/script parsing and `smart-search doctor --format markdown` when a human wants a detailed diagnostic report.
- If `smart-search doctor --format json` returns `ok: false`, follow the `error` field's guidance (`smart-search setup` or `smart-search config set KEY VALUE`); do not silently fall back to native web search.
- Use `smart-search diagnose openai-compatible --format markdown` when `doctor` succeeds but OpenAI-compatible `search` appears to hang, returns a timeout, or differs between `--stream` and `--no-stream`. It is the beginner-facing one-command report for upstream/relay compatibility.
- Interactive `smart-search setup` is a language-selecting grouped wizard with arrow-key / Space / Enter provider selection. It guides users through required `main_search`, `docs_search`, and fetch capability, then optional `web_search` reinforcement.
- The setup wizard prints beginner filling examples for official-service and relay/pooled-endpoint minimum profiles. Keep that guidance on stderr so stdout remains parseable JSON/Markdown/content output.
- Use `smart-search setup --lang en` for an English wizard and `smart-search setup --advanced` only when low-level config keys must be shown one by one.
- Use `smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"` to save Zhipu Web Search API endpoint and search service without prompts.
- Use `smart-search setup --non-interactive --jina-key "key"` to let Jina satisfy `web_fetch`; `JINA_RESPOND_WITH=readerlm-v2` also requires `JINA_API_KEY`.
- Use `smart-search setup --non-interactive --zhipu-mcp-key "key"` only when the user explicitly wants Coding Plan Remote MCP quota.
- Use `smart-search setup --non-interactive --openai-compatible-stream true` only when an OpenAI-compatible relay benefits from SSE streaming for long requests. Default remains false.
- Use `smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "key"` only for experimental AnySearch acceptance; do not add it to the normal minimum-profile setup.
- Interactive setup asks for Zhipu API key, API URL, and search service when optional `web_search` reinforcement selects Zhipu.
- Use `TAVILY_API_URL=https://<host>/api/tavily` for Tavily Hikari / pooled endpoints. Root host and `/mcp` inputs are normalized by setup; `/mcp` itself is not the REST base Smart Search should call.
- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity timeout and defaults to `30`. Raise it for slower pooled/community Tavily endpoints before judging the provider unhealthy.
- Use `FIRECRAWL_API_URL` only for a Firecrawl-compatible REST base. Official default is `https://api.firecrawl.dev/v2`.

## Command Patterns

```powershell
smart-search search "query" --extra-sources 5 --timeout 90 --format json --output result.json
smart-search search "query" --stream --format json
smart-search diagnose openai-compatible --format markdown
smart-search search "query" --platform "Reuters" --model "model-id" --extra-sources 3 --timeout 90 --format json
smart-search search "nba战报" --format content
smart-search search "query" --validation strict --fallback auto --providers auto --format json
smart-search exa-search "query" --num-results 5 --search-type neural --include-text --include-highlights --include-domains docs.example.com developer.mozilla.org --format json
smart-search exa-similar "https://example.com/article" --num-results 5 --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/facebook/react" "useEffect cleanup" --format json
smart-search zhipu-search "today China AI news" --count 5 --format json
smart-search anysearch-domains security --format json
smart-search anysearch-search "CVE-2024-3094" --domain security.cve --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
smart-search fetch "https://example.com" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --max-breadth 20 --limit 50 --format json
smart-search research "OpenAI Responses API web_search vs Chat Completions search" --budget deep --fallback auto --format json
smart-search rs "https://example.com/source" --fallback off --format markdown
smart-search setup
smart-search setup --lang en
smart-search setup --advanced
smart-search setup --non-interactive --install-skills hermes
smart-search skills status --targets codex --format json
smart-search skills update --targets codex --format json
smart-search skills update --all --format json
smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"
smart-search setup --non-interactive --openai-compatible-stream true
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "key"
smart-search setup --non-interactive --tavily-api-url "https://api.tavily.com" --tavily-key "key"
smart-search --version
smart-search config path --format json
smart-search config list --format json
smart-search config list --format markdown
smart-search config set XAI_API_KEY "key" --format json
smart-search config set XAI_MODEL "grok-4-fast" --format json
smart-search config set XAI_TOOLS "web_search,x_search" --format json
smart-search config set OPENAI_COMPATIBLE_API_URL "https://api.openai.com/v1" --format json
smart-search config set OPENAI_COMPATIBLE_API_KEY "key" --format json
smart-search config set OPENAI_COMPATIBLE_MODEL "model-id" --format json
smart-search config set OPENAI_COMPATIBLE_STREAM "true" --format json
smart-search config set ANYSEARCH_API_URL "https://api.anysearch.com/mcp" --format json
smart-search config set ANYSEARCH_API_KEY "key" --format json
smart-search config set ANYSEARCH_TIMEOUT_SECONDS "30" --format json
smart-search config set EXA_API_KEY "key" --format json
smart-search config set CONTEXT7_API_KEY "key" --format json
smart-search config set ZHIPU_API_KEY "key" --format json
smart-search config set ZHIPU_API_URL "https://open.bigmodel.cn/api" --format json
smart-search config set ZHIPU_SEARCH_ENGINE "search_pro" --format json
smart-search config set TAVILY_API_URL "https://api.tavily.com" --format json
smart-search config set TAVILY_TIMEOUT_SECONDS "45" --format json
smart-search config set FIRECRAWL_API_URL "https://api.firecrawl.dev/v2" --format json
smart-search model current --format json
smart-search doctor --format json
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
smart-search regression
smart-search smoke --mock --format json
smart-search smoke --mock --format markdown
```

Short aliases are supported for interactive use:

```powershell
smart-search --v
smart-search s "query" --format json
smart-search s "nba战报" --format content
smart-search rs "query" --format json
smart-search f "https://example.com" --format markdown
smart-search exa "OpenAI Responses API documentation" --format json
smart-search z "today China AI news" --format json
smart-search c7 "react" "hooks" --format json
smart-search c7docs "/facebook/react" "useEffect cleanup" --format json
smart-search cfg ls --format json
smart-search d --format markdown
smart-search mdl cur --format json
smart-search sm --format json
smart-search reg
```

## Timeout Retry Policy

When `smart-search search` returns `ok: false` with `error_type: "network_error"` and an error message containing `timed out`, treat it as a retryable CLI-level timeout, not as a terminal research failure.

1. Retry up to 3 total attempts with `--timeout 180`, waiting about 5 seconds between attempts.
2. Use `--format json` and `--output PATH` for each attempt; after each attempt, inspect the saved JSON and stop on the first `"ok": true`.
3. Use `--extra-sources 1` during retry attempts to keep Tavily/Firecrawl overhead small.
4. Always use the CLI's `--timeout` option. Do not wrap `smart-search` in a shell-level `timeout` command because shell termination can prevent the CLI from writing structured failure JSON.
5. Do not rely on `SMART_SEARCH_RETRY_*` settings for this path; search command timeouts are surfaced by the CLI result contract and should be handled by the agent workflow.
6. If all attempts time out, fall back to source-first evidence:
   - Run `exa-search` with the original query for broad source discovery.
   - Run `exa-search --include-domains` when likely official domains are known.
   - `fetch` the top 1-2 relevant URLs before making claim-level statements.
   - Mark the final answer as `source_mode: "fallback"` or clearly state that the answer was assembled from fetched sources rather than generated by `search`.

Example retry flow:

```powershell
smart-search search "query" --validation balanced --extra-sources 1 --timeout 180 --format json --output result-attempt-1.json
smart-search search "query" --validation balanced --extra-sources 1 --timeout 180 --format json --output result-attempt-2.json
smart-search search "query" --validation balanced --extra-sources 1 --timeout 180 --format json --output result-attempt-3.json
smart-search exa-search "query" --num-results 5 --include-text --format json --output exa.json
smart-search exa-search "query" --include-domains platform.openai.com developers.openai.com --num-results 3 --include-text --format json --output exa-official.json
smart-search fetch "https://example.com/source" --format markdown --output fetch.md
```

## Guardrails

- Prefer JSON for agent parsing and markdown for fetched page text intended for reading.
- Use `--output` for multi-source work, long pages, or anything the answer may need to cite later.
- Keep `--extra-sources` small (`1` to `3`) unless the user asks for broad coverage. Large values are slower and can add noise.
- Do not cite `extra_sources` as proof for a sentence in `content`; fetch the URL first or cite it only as a candidate source.
- Prefer `exa-search --include-domains` for official documentation when likely domains are known.
- Do not expose API keys. Treat `doctor` output as safe only because it is expected to mask secrets.
- In this CLI-first workflow, native `web_search` is disabled unless the user explicitly configures another approved route.
- If `doctor` or a command fails, report the failure and recovery steps; do not silently fall back to another web-search route.
- If the user explicitly asks to bypass smart-search, state that another approved web-search route must be configured first.
- Do not use legacy MCP tool names in prompts, notes, or generated instructions for this workflow.
- Treat key rotation as a hard safety gate when previous key values were pasted into chat or logs.
- For provider architecture maintenance, verify the distributable contract rather than the current developer machine's wrappers or local config. Keep fallback same-capability only.
- Treat xAI Responses and OpenAI-compatible as peer `main_search` providers. Do not reuse one provider's URL/key to fabricate the other provider as a fallback.

## Supporting Reference

Read `references/cli-contract.md` when you need command details, output fields, exit codes, or regression expectations.
