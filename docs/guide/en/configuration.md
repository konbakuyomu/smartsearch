[Guide](../README.md) · [简体中文](../zh-CN/configuration.md)

# Configuration guide

Every saved key, its purpose, accepted values and default is in [All configuration keys](configuration-reference.md). For ordinary use, start with the [App setup steps](app.md).

## Precedence and local preferences

Environment variables override saved values; a command's explicit per-call option overrides its matching setting. `config set KEY VALUE` saves a value using the existing atomic configuration write. It does not remove an environment override. Keys are masked in diagnostic output. Use a separate configuration directory for isolated tests rather than changing production keys.

`SMART_SEARCH_LANGUAGE` accepts `auto`, `zh`, `en` and compatible locale forms such as `zh-CN`. The CLI flag `--lang` takes priority over the environment and saved preference. See [CLI language and scripting](cli.md#language-and-scripting). App language is saved separately in App settings. Neither choice changes query or source languages.

The runtime also recognizes environment-only inputs: `SMART_SEARCH_CONFIG_DIR` selects the configuration directory; `SMART_SEARCH_PYTHON` is used only when the App installs or repairs older npm packages without a bundled runtime; `LC_ALL`, `LC_MESSAGES` and `LANG` supply the CLI's automatic locale. They are not saved provider keys. Current npm packages bundle their runtime and ignore `SMART_SEARCH_PYTHON`.

## Providers, keys and configuration

Use `smart-search setup` for normal configuration. Environment variables remain supported for CI and advanced users.
The default wizard offers Jev or local routing. The CLI browser page remains available through `smart-search ui`.

| Provider / route | Used for | Main config keys | Official docs | Key / dashboard |
| --- | --- | --- | --- | --- |
| xAI Responses API | Primary live search with `web_search,x_search` tools | `XAI_API_KEY`, `XAI_API_URL`, `XAI_MODEL`, `XAI_TOOLS`, `XAI_REASONING_EFFORT`, `XAI_STREAM` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions / Responses | Primary search through OpenAI or a compatible relay; no xAI search tools are sent in either mode | `OPENAI_COMPATIBLE_API_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL`, `OPENAI_COMPATIBLE_API_MODE`, `OPENAI_COMPATIBLE_FALLBACK_MODELS`, `OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) or your relay provider |
| Exa | Low-noise official docs, API, paper, product, trusted-page discovery | `EXA_API_KEY` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 | SDK, library, framework, and API documentation fallback | `CONTEXT7_API_KEY`, `CONTEXT7_BASE_URL` | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| Zhipu Web Search API | Chinese, domestic, current, or domain-filtered web discovery | `ZHIPU_API_KEY`, `ZHIPU_API_URL`, `ZHIPU_SEARCH_ENGINE` | [Zhipu web search docs](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [Zhipu API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Zhipu Coding Plan Remote MCP | Coding Plan quota web search, page reading, and open-source repo discovery | `ZHIPU_MCP_API_KEY`, `ZHIPU_MCP_SEARCH_API_URL`, `ZHIPU_MCP_READER_API_URL`, `ZHIPU_MCP_ZREAD_API_URL` | [search MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server), [reader MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server), [zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [Zhipu API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | Extra web sources, URL fetch, and site map | `TAVILY_API_URL`, `TAVILY_API_KEY`, `TAVILY_ENABLED` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | Known URL page extraction for `web_fetch`; key required for standard minimum profile | `JINA_API_KEY`, `JINA_READER_API_URL`, `JINA_RESPOND_WITH`, `JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | Fetch fallback and supplementary web sources | `FIRECRAWL_API_URL`, `FIRECRAWL_API_KEY` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| TinyFish | Search and fetch fallback | `TINYFISH_API_KEY`, `TINYFISH_SEARCH_API_URL`, `TINYFISH_FETCH_API_URL`, `TINYFISH_TIMEOUT_SECONDS` | [TinyFish docs](https://docs.tinyfish.ai/) | [TinyFish API keys](https://agent.tinyfish.ai/api-keys) |
| DeepSeek Search / Fetch | Web search and page fetch with the same key as the DeepSeek model API, billed per successful request | `DEEPSEEK_API_KEY`, `DEEPSEEK_API_URL`, `DEEPSEEK_TIMEOUT_SECONDS` | [Search & Fetch](https://api-docs.deepseek.com/guides/search) | [DeepSeek API keys](https://platform.deepseek.com/api_keys) |
| Yuanbao Search (Tencent Cloud wsa) | Web search that adds Tencent content such as Tencent News; a Tencent Cloud SecretId/SecretKey with Yuanbao Search enabled | `YUANBAO_SECRET_ID`, `YUANBAO_SECRET_KEY`, `YUANBAO_API_URL`, `YUANBAO_TIMEOUT_SECONDS` | [Yuanbao Search docs](https://cloud.tencent.com/document/product/1806) | [Tencent Cloud API keys](https://console.cloud.tencent.com/cam/capi) |
| TypeSafe / Jev | Optional semantic routing and evidence judgments | `TYPESAFE_API_KEY`, `TYPESAFE_API_URL`, `TYPESAFE_MODEL` | [TypeSafe API](https://docs.typesafe.ai/api) | See the TypeSafe documentation |
| AnySearch | Experimental vertical search acceptance surface; not a default fallback | `ANYSEARCH_API_URL`, `ANYSEARCH_API_KEY`, `ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch docs](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |
| Sciverse | Explicit experimental academic search, semantic paper retrieval, document chunks, and citation/reference relations; not a default fallback | `SCIVERSE_API_TOKEN`, `SCIVERSE_API_URL`, `SCIVERSE_TIMEOUT_SECONDS` | [Sciverse Agent Tools](https://github.com/opendatalab/Sciverse-Agent-Tools) | Sciverse dashboard / token provider |

## Routing and migration

`search` and `research` are the two live search modes. Both share the configured channel catalog, execution, deadlines, and evidence records.

- `search`: one Jev routing judgment selects one suitable channel, then returns results and sources. Necessary dependent requests (such as Context7 library resolution followed by docs) and same-capability failure fallback remain; model answers and web search are mutual fallbacks in ordinary search. It never runs evidence assessment, follow-up search, filtering, or synthesis. `--extra-sources N` limits results from that channel (up to 20), not the number of channels. `evidence_assessment.status=not_evaluated`; success is retrieval success, not factual verification. `--validation strict` requires source evidence and can return partial content with an evidence error.
- `research`: Jev selects complementary actions in parallel, reads discovered pages, assesses evidence gaps, and continues while useful and within budget. It chooses from program-built original/subquestion/gap query candidates; Jev does not generate arbitrary queries or tool calls. Only fetched/read content enters `citations`. Optional filtering and `SMART_SEARCH_JEV_SYNTHESIZE=false|auto|true` apply only here.
- `deep` remains an offline planner. Its `steps[].command` entries are suggestions for manual/AI orchestration; `research` records its actual actions separately in `routing_decision.rounds` and `stage_results`.

Final research synthesis uses only a separately configured JEV synthesis model, independently of the main-search model. Configure `SMART_SEARCH_JEV_SYNTHESIS_API_URL`, `SMART_SEARCH_JEV_SYNTHESIS_API_KEY`, `SMART_SEARCH_JEV_SYNTHESIS_MODEL`, and `SMART_SEARCH_JEV_SYNTHESIS_API_MODE` (`chat-completions` or `responses`). See [Jev routing and filtering](../../jev-routing.md) for the synthesis modes and diagnostics.

The default is `SMART_SEARCH_INTENT_ROUTER=jev`. Without a TypeSafe key or a valid judgment, `--fallback auto` uses local capability rules and reports degradation; `--fallback off` fails clearly. Explicit `local` never calls Jev. Legacy `hybrid` maps to `jev`; `rules` and `off` map to `local`. Old embedding/classifier keys remain stored but unused. `route-calibrate` is a retired, non-network compatibility command.

`route` previews local capabilities without calling a model or retrieval provider. Add `--remote` only for an explicit, potentially billable Jev diagnostic. Direct provider commands keep their explicit behavior.

Only configured, enabled, allowed channels outside cooldown can run. `--providers`, provider enable switches, `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`, and explicit-only boundaries are enforced before selection and dispatch. A failed ordinary channel can try another provider of the same capability, with model answers and web search treated as mutual fallbacks; it cannot turn into a research loop. User preferences do not bypass these boundaries.

The shared total timeout defaults to 300 seconds (`SMART_SEARCH_TIMEOUT_SECONDS`, overridden by `search --timeout`). Research quick/standard/deep ceilings are 2/3/10 rounds, 1/2/10 channels per round, 3/5/20 results per channel, and 45/120/configured seconds, further limited by the configured Jev budgets. Sufficient evidence, exhaustion, no progress, or deadline stops the loop. Completed results survive optional judgment/filter/synthesis failure.

Important boundaries:

- xAI official live search uses `/responses` through `XAI_*`. OpenAI-compatible relays use `/chat/completions` by default; set `OPENAI_COMPATIBLE_API_MODE=responses` only for a relay that explicitly supports the documented Responses subset.
- `chat-completions` sends no search tools. If a model on a relay can search only through the Responses `web_search` tool (for example, grok), point `XAI_API_URL`, `XAI_API_KEY`, and `XAI_MODEL` at that relay and confirm with the “联网搜索能力” (web search capability) check in `smart-search diagnose openai-compatible`.
- `smart-search search --stream` and `smart-search research --stream` set `stream=true` for xAI Responses and OpenAI-compatible search, including Grok search selected by Jev. `--no-stream` disables streaming for that request. `OPENAI_COMPATIBLE_STREAM=true` remains the default switch for OpenAI-compatible search and provider-side fetch.
- `XAI_STREAM` defaults to `false` and accepts `true`, `1`, or `yes` as true. When true, every xAI Responses request uses `stream=true`, including `research` and Grok search selected by Jev; `--stream` / `--no-stream` override it for one run. A failed xAI stream is returned as an error; it is not retried with `stream=false`.
- `XAI_REASONING_EFFORT` accepts `low`, `medium`, or `high` (case-insensitive, stored lowercase). Optional; when set, sends reasoning.effort in xAI Responses requests; omitted by default. This also applies to Grok search selected by Jev. Provider attempts report the actual `stream` and `reasoning_effort` values, and xAI attempts also report `transport` (`stream` or `non_stream`); `doctor` displays `XAI_REASONING_EFFORT` and `XAI_STREAM`, and `model current` shows `xai_stream`. The xAI connection test in `doctor` and the App sends the same `reasoning.effort` and `stream` as a search, without tools, and names them in its message and under `sent`; a stream that fails after HTTP 200 fails the test. Upstream 4xx errors for unsupported reasoning are returned without dropping the field or retrying.
- `SMART_SEARCH_TIMEOUT_SECONDS` is the persistent total `search` budget. Environment values override the local config file; `search --timeout SECONDS` overrides both. The default is `300` seconds.
- The main-search provider uses the whole remaining budget as its read ceiling. There is no separate fixed provider read cap to cut a slow reasoning model short before the shared deadline.
- `OPENAI_COMPATIBLE_FALLBACK_MODELS` is fail-over, not a time slice. The primary model keeps the remaining shared main-search budget. A fallback model is tried only after a hard failure such as `model_not_found`, auth, empty content, or a non-retryable protocol error. `doctor` and `diagnose openai-compatible` warn when a configured fallback id is missing from `/models`.
- Legacy `SMART_SEARCH_API_URL`, `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and `SMART_SEARCH_XAI_TOOLS` are not supported config keys. Use `XAI_*` or `OPENAI_COMPATIBLE_*` explicitly.
- Do not force xAI `web_search` / `x_search` tools or legacy `search_parameters` into either OpenAI-compatible API mode.
- Responses mode supports the official `model` + `instructions`/`input` request subset, heterogeneous `output` text parts, URL-citation annotations, and typed terminal stream events. It is not a claim that every "OpenAI-compatible" relay implements `/responses`; use `diagnose openai-compatible` with both stream settings to accept a named relay before relying on it.
- `zhipu-search` support is the Web Search API route, not Zhipu Chat Completions `tools=[web_search]`, not Search Agent, and not the MCP Server.
- Zhipu Coding Plan support is a separate Remote MCP route. `web_search_prime` maps to `web_search`, `webReader` maps to `web_fetch`, and zread tools map to explicit repo/docs discovery commands. It is not mixed into the existing `/paas/v4/web_search` Zhipu REST provider.
- Zhipu Coding Plan MCP requires its own Coding Plan entitlement. A normal `ZHIPU_API_KEY` for Web Search API does not prove `zhipu-mcp-search` or zread access. If `ZHIPU_MCP_API_KEY` is absent or unauthorized, Smart Search skips those MCP providers; the `standard` minimum profile and same-capability fallback still work through the configured REST/search/fetch providers.
- Jina Reader is not a general search provider. `JINA_API_KEY` is required for Jina to count toward `standard`; `JINA_RESPOND_WITH=readerlm-v2` also requires `JINA_API_KEY`.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`. Supported official values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`; custom values remain allowed for future services.
- `TAVILY_API_URL` affects Tavily only. It does not proxy Zhipu. For Tavily Hikari / pooled endpoints, use `https://<host>/api/tavily`; setup normalizes root-host or `/mcp` inputs to that REST base.
- `TAVILY_ENABLED` defaults to `true`. Set it to `false` to disable Tavily even when a key is present: Tavily is removed from web-search and fetch routing, direct Tavily calls and `doctor` make no Tavily request, and `map` returns a local configuration error. This does not enable Firecrawl or change same-capability fallback boundaries.
- `FIRECRAWL_API_URL` defaults to `https://api.firecrawl.dev/v2`.
- `DEEPSEEK_API_URL` defaults to `https://api.deepseek.com`; a `.../v1` base also works. Smart Search calls `/v1/tools/search` and `/v1/tools/fetch`. One `DEEPSEEK_API_KEY` joins both `web_search` and `web_fetch` and never satisfies `main_search` or `docs_search`. DeepSeek accepts queries of at most 128 characters, so longer queries are shortened at a word boundary; operators such as `site:`, `lang:` and `after:` pass through unchanged. A fetch answered with 403 (refused by the safety policy) or 404 (no usable page content, which currently includes PDF links and private network addresses) only means that page cannot be read: fallback continues and DeepSeek is not cooled down. Every successful request is billed, and `doctor` and `providers test deepseek` each send one real search and one real fetch.
- AnySearch uses JSON-RPC 2.0 `tools/call` at `https://api.anysearch.com/mcp` by default. It allows anonymous calls when no key is configured, but authenticated calls send `Authorization: Bearer ...`. HTTP 200 responses with `result.isError=true` are treated as provider errors, not as successful evidence. `--sub-domain-params` is decoded as a JSON object before repeatable `--param key=value` entries override matching keys; malformed parameters fail before a request.
- Sciverse uses native HTTP/OpenAPI at `https://api.sciverse.space` by default. It requires `SCIVERSE_API_TOKEN`, returns `config_error` without a network request when the token is absent, sends `Authorization: Bearer ...` when configured, and remains explicit-only: not `docs_search`, not `standard`, and not default `search` / `research` fallback.

Non-interactive setup example:

```powershell
smart-search setup --non-interactive `
  --xai-api-key "your-xai-key" `
  --xai-model "grok-4-fast" `
  --openai-compatible-api-url "https://api.openai.com/v1" `
  --openai-compatible-api-key "your-openai-or-relay-key" `
  --openai-compatible-model "gpt-4.1" `
  --openai-compatible-api-mode "chat-completions" `
  --openai-compatible-stream "false" `
  --validation-level "balanced" `
  --search-timeout "300" `
  --fallback-mode "auto" `
  --minimum-profile "standard" `
  --intent-router "jev" `
  --exa-key "your-exa-key" `
  --context7-key "your-context7-key" `
  --zhipu-key "your-zhipu-key" `
  --zhipu-api-url "https://open.bigmodel.cn/api" `
  --zhipu-search-engine "search_pro_sogou" `
  --zhipu-mcp-key "your-zhipu-coding-plan-key" `
  --jina-key "your-jina-key" `
  --tavily-api-url "https://api.tavily.com" `
  --tavily-key "your-tavily-key" `
  --firecrawl-api-url "https://api.firecrawl.dev/v2" `
  --firecrawl-key "your-firecrawl-key"
```

The `standard` minimum is at least one enabled automatic retrieval channel. Jev and a main model are optional. The requested operation still needs a capable channel; a page-reader alone cannot discover URLs.

AnySearch is optional and supports vertical-intent retrieval:

```powershell
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "your-anysearch-key"
smart-search anysearch-domains security --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --max-length 12000 --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
```

For simple vertical domains, dotted shorthand such as `code.doc` is still accepted and sent as `domain=code` plus `sub_domain=doc`. Parameterized domains should use the split form with `--sub-domain-params` JSON and/or repeatable `--param key=value`; repeated parameters override matching JSON keys, and invalid JSON, a missing `=`, or an empty key fails before a request. `anysearch-domains DOMAIN` calls the live `get_sub_domains` tool, while omitting `DOMAIN` reads its `tools/list` schema. `anysearch-extract --max-length` sends only `url` upstream and, when the value is positive, truncates successful top-level and result text fields locally.

Experimental Sciverse configuration is also optional and does not satisfy or change the `standard` minimum profile:

```powershell
smart-search setup --non-interactive --sciverse-token "your-sciverse-token" --sciverse-api-url "https://api.sciverse.space"
smart-search sciverse-catalog --collection papers --format json
smart-search sciverse-search "transformer retrieval" --year-from 2020 --page-size 5 --format json
smart-search sciverse-semantic "attention mechanism" --top-k 3 --retrieval hybrid --source-types web,pdf --format json
smart-search sciverse-read "doc-id-from-search" --offset 0 --limit 4096 --format json
smart-search sciverse-relations "unique-id-from-search" --relation CITATIONS --page-size 25 --format json
```

The current `GET /meta-catalog` and `POST /meta-search` schemas have no `collection` selector. Legacy `--collection papers` remains accepted without being sent upstream; `authors` and `sources` return `parameter_error` before a request. The `POST /meta-search` body uses only `query`, `filters`, `sort`, `freshness_boost`, `page`, and `page_size`. `--title-contains` and `--abstract-contains` are folded into `query`; authors, journals, subjects, and year bounds become current `FieldFilterItem` filters.

`--filters-advanced` and `--sort-advanced` accept structured JSON arrays, not arbitrary pass-through JSON. A filter item needs `field` and `value`, uses current `operator` values such as `FILTER_OP_GTE`, and accepts legacy `op` only when it maps unambiguously. A sort item needs `field` and accepts `order` values `SORT_ORDER_ASC` or `SORT_ORDER_DESC` (or `asc` / `desc`). Full-text `query` cannot be combined with any sort in the current schema, so `--sort-by-year` defaults to `none` and sorting is for filter-only searches.

Use `--retrieval hybrid|milvus|es` for semantic search. Legacy `--mode fast|balanced|quality` remains accepted with a deprecation warning and maps to `--retrieval hybrid`; combining it with `--retrieval milvus` or `--retrieval es` is a parameter error. Semantic `--source-types` accepts `web,pdf`. Use `doc_id` for `sciverse-read` and `unique_id` for `sciverse-relations`. `CITATIONS` means papers citing the target paper; `REFERENCES` means papers cited by the target paper; `RELATED_WORKS` means related work suggestions.

Local config path:

- Windows default: `%LOCALAPPDATA%\smart-search\config.json`.
- Linux/macOS default: `~/.config/smart-search/config.json`.
- `SMART_SEARCH_CONFIG_DIR` is an advanced override for CI, containers, sandboxes, or portable installs.
- `SMART_SEARCH_TIMEOUT_SECONDS` saves the default total `search` budget. Environment wins over this file; `search --timeout` is the one-call override.
- `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` are advanced overrides for automatic routing in both ordinary search and `research`; the names are historical. They accept provider CSV values and can only reorder or disable providers inside existing capability boundaries.
- Earlier Windows source builds defaulted to `~\.config\smart-search\config.json`, while some installs were already pinned to `%LOCALAPPDATA%\smart-search` through `SMART_SEARCH_CONFIG_DIR`. If the new Windows default file is missing but the old home config exists, Smart Search reads the old file as `legacy_windows_home` so upgrades do not lose configuration. `doctor` reports the active path, default path, old home path, `SMART_SEARCH_CONFIG_DIR`, and whether that override merely matches the current default.

Provider timeouts:

- `SMART_SEARCH_TIMEOUT_SECONDS` defaults to `300`. It is a shared service deadline and the main-search read ceiling, not a separate per-provider read timeout. JSON output adds `timeout_phase`, `phase_attempts`, elapsed/remaining deadline values, and `partial_success` when optional work is cut short after primary output succeeds.
- `TAVILY_ENABLED` accepts `true`, `1`, or `yes` as enabled; any other value disables Tavily without making a Tavily network request.
- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity check timeout and defaults to `30`.
- `ANYSEARCH_TIMEOUT_SECONDS` controls experimental AnySearch JSON-RPC calls and defaults to `30`.
- `SCIVERSE_TIMEOUT_SECONDS` controls explicit Sciverse academic API calls and defaults to `30`.
- Raise it for slower Tavily Hikari / pooled / community endpoints before treating the provider as unhealthy.

## Provider failure cooldown

Optional providers (`web_search`, `docs_search`, `web_fetch`, `vertical_search`) are additive. When one of them keeps failing - a revoked Zhipu key, an exhausted quota, a dead endpoint - retrying it on every invocation only costs latency and repeats the same error. Smart Search is a short-lived CLI process, so it remembers those failures in `provider_health.json` next to `config.json`:

- A hard failure (`auth_error`, `config_error`) opens the cooldown on the first occurrence and is not probed again; a bad key does not heal itself.
- A soft failure (timeout, `5xx`, rate limit) needs `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` consecutive failures inside one cooldown window, and stays probeable so a recovered provider returns without user action.
- An empty result set is not a failure and never opens a cooldown.
- Main-search providers are never skipped this way. A cooled-down provider is reported, not hidden: its attempt has `status=skipped` with the remembered `error_type`, and `provider_notices` carries one deduplicated entry per degraded provider instead of a repeated error.

Recovery is automatic in the common cases. The record is keyed to a fingerprint of the provider's credentials, so re-keying with `smart-search config set` clears it, and a successful `smart-search doctor` probe clears it too.

```powershell
smart-search providers status --format markdown
smart-search providers reset zhipu --format json
smart-search providers reset --format json
smart-search config set SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS "0" --format json
```
