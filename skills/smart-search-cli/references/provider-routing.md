# Provider Routing

## Intent Routing Diagnostics

`search` and `research` are the two live search modes. Both share the configured channel catalog, execution, deadlines, and evidence records.

- `search`: one routing decision, using Jev or local rules, selects one suitable channel, then returns results and sources. Necessary dependent requests (such as Context7 library resolution followed by docs) and same-capability failure fallback remain; model answers and web search are mutual fallbacks in ordinary search. It never runs evidence assessment, follow-up search, filtering, or synthesis. `--extra-sources N` limits results from that channel (up to 20), not the number of channels. `evidence_assessment.status=not_evaluated`; success is retrieval success, not factual verification. `--validation strict` requires source evidence and can return partial content with an evidence error. Model answers first undergo local checks for `NO_WEB_SEARCH`, missing sources, and preface-only replies; when Jev is configured, it also checks substantive content and contradictions with the answer's own citations; rejected answers use same-capability fallback.
- `research`: the shared loop selects complementary actions in parallel, reads discovered pages, assesses evidence gaps, and continues while useful and within budget. Jev or local rules choose from program-built original/subquestion/gap query candidates; Jev does not generate arbitrary queries or tool calls. Only fetched/read content enters `citations`. Optional filtering and `SMART_SEARCH_JEV_SYNTHESIZE=false|auto|true` apply only here.
- `deep` remains an offline planner. Its `steps[].command` entries are suggestions for manual/AI orchestration; `research` records its actual actions separately in `routing_decision.rounds` and `stage_results`.

The default is `SMART_SEARCH_INTENT_ROUTER=jev`. In Jev mode, ordinary search makes at most one routing judgment and, when Jev is configured, one additional judgment on a returned model answer; without a TypeSafe key or a valid judgment, `--fallback auto` uses local capability rules and reports degradation, while `--fallback off` fails clearly. Without a TypeSafe key, `research` stops after the first round that reads page text (`judgment_unavailable`), is always reported as degraded, and with `deep` (strict) never returns `ok=true`; read `content` and `gap_check` instead of treating that as a failed search. `SMART_SEARCH_JEV_SYNTHESIZE=true` still summarizes read evidence; `auto` needs Jev. Explicit `local` needs no TypeSafe key and never calls Jev. Legacy `hybrid` maps to `jev`; `rules` and `off` map to `local`. Old embedding/classifier keys remain stored but unused. `route-calibrate` is a retired, non-network compatibility command.

`route` previews local capabilities without calling a model or retrieval provider. Add `--remote` only for an explicit, potentially billable Jev diagnostic. Direct provider commands keep their explicit behavior.

Only configured, enabled, allowed channels outside cooldown can run. `--providers`, provider enable switches, `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`, and explicit-only boundaries are enforced before selection and dispatch. A failed ordinary channel can try another provider of the same capability, with model answers and web search treated as mutual fallbacks; it cannot turn into a research loop. User preferences do not bypass these boundaries.

The shared total timeout defaults to 300 seconds (`SMART_SEARCH_TIMEOUT_SECONDS`, overridden by `search --timeout`). Research quick/standard/deep ceilings are 2/3/10 rounds, 1/2/10 channels per round, 3/5/20 results per channel, and 45/120/configured seconds, further limited by the configured Jev budgets. Sufficient evidence, exhaustion, no progress, or deadline stops the loop. Completed results survive optional judgment/filter/synthesis failure.

For research, `SMART_SEARCH_JEV_SYNTHESIZE` accepts `true`, `false`, and `auto`. Final synthesis uses only the dedicated `SMART_SEARCH_JEV_SYNTHESIS_API_URL`, `_API_KEY`, and `_MODEL` configuration; `_API_MODE` selects `chat-completions` (default) or `responses`. It never uses the main-search model or `--model`. Auto asks Jev after optional filtering whether the retained evidence benefits from synthesis. No allowed dedicated model or a failed judgment returns evidence directly. `synthesis` reports the mode, decision probability, execution status and skip reason. With an explicit `--providers` filter, include `jev-synthesis` to permit the synthesis call.

## Provider Boundaries

- `deep` uses offline rules/local signals only and must not call remote embeddings or classifier components.
- Official xAI uses `/responses` through `XAI_*`. OpenAI-compatible relays default to `/chat/completions`; `OPENAI_COMPATIBLE_API_MODE=responses` explicitly selects `/responses` for a relay that supports the documented subset.
- `search --stream` and `research --stream` set `stream=true` for xAI Responses and OpenAI-compatible search, including Grok search selected by Jev. `--no-stream` disables streaming for that request. `OPENAI_COMPATIBLE_STREAM=true` remains the default switch for OpenAI-compatible search and provider-side fetch.
- `XAI_STREAM` defaults to `false` and accepts `true`, `1`, or `yes` as true. When true, every xAI Responses request uses `stream=true`, including `research` and Grok search selected by Jev; `--stream` / `--no-stream` override it for one run. A failed xAI stream is an error; it is not retried with `stream=false`.
- Legacy `SMART_SEARCH_API_URL`, `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and `SMART_SEARCH_XAI_TOOLS` are unsupported config keys.
- xAI Responses mode may use only `XAI_TOOLS=web_search,x_search` and a subset of those tools.
- `XAI_REASONING_EFFORT` accepts `low`, `medium`, or `high` (case-insensitive, stored lowercase). Optional; when set, sends reasoning.effort in xAI Responses requests; omitted by default. This also applies to Grok search selected by Jev. Unsupported reasoning values reported by the upstream API remain errors; the field is not silently removed and retried. The xAI connection test in `doctor` and the App sends the same `reasoning.effort` and `stream` as a search, without tools, and reports them under `sent`.
- Neither OpenAI-compatible API mode sends xAI `web_search` / `x_search` tools or legacy `search_parameters`; xAI Chat Completions Live Search is deprecated.
- AnySearch is reported only as optional experimental `vertical_search`; it is not part of the `web_search` fallback and is not required by the `standard` minimum profile.
- Sciverse is reported only as optional experimental explicit-only `vertical_search`; it is not `docs_search`, not part of default `search` / `research` fallback, and not required by the `standard` minimum profile.
- Jina Reader is `web_fetch` only, not a general search provider. `JINA_API_KEY` is required before Jina satisfies the standard minimum profile; anonymous `r.jina.ai` is explicit/experimental fetch behavior.
- Same-capability fallback is allowed; model answers and web search are mutual fallbacks in ordinary search. Context7 is not used for unrelated broad web queries, and page extraction providers are not used as docs search providers.
- `TAVILY_ENABLED=false` removes Tavily from registered `web_search` and `web_fetch` routes even when its key is present. Direct Tavily search/extract calls, `map`, `doctor`, and smoke must make no Tavily network request; `map` reports a local configuration error. Firecrawl remains independently configured and all fallback stays within its capability.
- In Jev mode, Jev chooses among allowed capabilities and providers for the question; there is no mandatory main-model call or fixed global provider order. Local routing prioritizes suitable capabilities and configured preferences; a docs question with no docs channel configured uses web search instead of no channel.
- `main_search` contains xAI Responses and OpenAI-compatible model channels; `web_search` contains Zhipu REST/MCP, Tavily, Firecrawl, TinyFish and DeepSeek; `docs_search` contains Context7 and Exa. Failure fallback stays within the selected capability family; model answers and web search are mutual fallbacks in ordinary search.
- Ordinary Context7 uses the first library in Context7's ranked candidates, without a second Jev call. Research may use Jev to select the matching library, using the first candidate if Jev fails or no score reaches its threshold. Empty results may fall through to same-capability Exa; explicit Context7 commands remain unchanged.
- `--extra-sources N` controls the selected channel's result count. It does not add channels, split a budget between providers, or make Tavily/Firecrawl a required extra stage. A known-URL search follows the configured Jev/local routing; local routing prefers page reading.
- `fetch` tries Tavily first, then Jina with `JINA_API_KEY`, then Zhipu Coding Plan MCP Reader, then Firecrawl, then TinyFish, then DeepSeek.

TinyFish:

- `TINYFISH_API_KEY` is optional and registers TinyFish for both `web_search` and `web_fetch`. It never satisfies `main_search` or `docs_search`. Jev may select it directly; the direct `fetch` fallback order remains as listed above.
- `TINYFISH_SEARCH_API_URL` defaults to `https://api.search.tinyfish.ai` and is called as `GET ?query=...`; `TINYFISH_FETCH_API_URL` defaults to `https://api.fetch.tinyfish.ai` and is called as `POST` with `{"urls": [url], "format": "markdown"}`.
- Both endpoints send `X-API-Key`, not `Authorization: Bearer`. Never log or echo the key.
- Search results normalize `snippet` to `description`, `site_name` to `source`, and `date` to `published_date`. An empty result set is a successful empty response, not a failure.
- Fetch reads `results[0].text`; `errors[]` entries are surfaced as `provider_error` with the upstream message. A payload with neither results nor errors is `provider_error`, and a non-object payload is `parse_error`.
- Challenge pages such as `Checking if the site connection is secure` are reported as `quality_error` so same-capability fallback can continue.
- `401`/403 map to `auth_error`, `408` to `timeout`, `429` to `rate_limited`, `5xx` to `network_error`, and `400`/422 to `parameter_error`.
DeepSeek:

- `DEEPSEEK_API_KEY` is optional and registers DeepSeek for both `web_search` and `web_fetch`; it is the same key as the DeepSeek model API. It never satisfies `main_search` or `docs_search`. Jev may select it directly; the direct `fetch` fallback order remains as listed above.
- `DEEPSEEK_API_URL` defaults to `https://api.deepseek.com`; search calls `POST /v1/tools/search` with `{"query", "count"}` and fetch calls `POST /v1/tools/fetch` with `{"url"}`, both with `Authorization: Bearer`. A trailing `/v1` in the base URL is accepted. Never log or echo the key.
- DeepSeek accepts queries of at most 128 characters, so longer queries are shortened at a word boundary. `site:`, `-site:`, `lang:`, `after:`/`before:` and quoted phrases in the query pass through unchanged.
- Search results normalize `summary` (falling back to `snippet`) to `description`, `site_name` to `source`, and `date` to `published_date`. Summaries are not page text: fetch a key page before citing it. An empty result set is a successful empty response.
- Fetch returns the page Markdown. HTTP 403 (URL refused by DeepSeek's safety policy) and 404 (no usable page content, which currently includes PDF links and private network addresses) mean that page has nothing to read: the attempt is `empty`, fallback continues, and the provider is not cooled down. `401` maps to `auth_error`, `402` (insufficient balance) to `provider_error`, `429` to `rate_limited`, `5xx` to `network_error`.
- DeepSeek bills each successful search or fetch request. `doctor` and `providers test deepseek` send one real request to each.
- `map` currently uses Tavily only.
- `exa-search` and `exa-similar` use Exa only.
- `context7-library` and `context7-docs` use Context7 only.
- `anysearch-domains`, `anysearch-search`, `anysearch-extract`, and `anysearch-batch` use AnySearch only. Treat results as acceptance evidence until the target vertical domain is reviewed.
- `sciverse-catalog`, `sciverse-search`, `sciverse-semantic`, `sciverse-read`, and `sciverse-relations` use Sciverse only. They are explicit academic commands and must not be inserted into default provider fallback.
- `zhipu-search` uses Zhipu only.
- `zhipu-mcp-search`, `zhipu-mcp-reader`, and `zhipu-mcp-*` zread commands use Zhipu Coding Plan Remote MCP only.
- Runtime config priority is environment variables first, then local config file, then defaults.
- `setup` and `config` read/write the local Smart Search config file and do not call providers.
- `model current` reports explicit provider model settings. `model set` is retained only as a parameter-error migration guard; use `config set XAI_MODEL ...` or `config set OPENAI_COMPATIBLE_MODEL ...` to change models.

Provider attempt errors:

- Provider exceptions must be visible as `provider_attempts[].status="error"`, never silently converted to empty output. Use the stable taxonomy: HTTP `400`/`422` is `parameter_error`, `401`/`403` is `auth_error`, timeout is `timeout`, `429` is `rate_limited`, `5xx` or request failure is `network_error`, invalid response decoding is `parse_error`, and explicit upstream tool failures are `provider_error`.
- A successfully decoded response with no normalized candidates or content is `status="empty"`, so same-capability fallback can continue without misreporting a provider failure.

Zhipu Web Search API:

- `zhipu-search` corresponds to the official Zhipu Web Search API route, using `ZHIPU_API_URL` plus `ZHIPU_SEARCH_ENGINE`; it is not Zhipu Chat Completions `tools=[web_search]`, not Search Agent, and not the MCP Server.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`. Official Web Search API service values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`; keep custom values possible because official services may change.
- `TAVILY_API_URL` only affects Tavily REST calls and does not proxy Zhipu.

Zhipu Coding Plan Remote MCP:

- `ZHIPU_MCP_API_KEY` configures the Coding Plan MCP auth token and must be sent as `Authorization: Bearer ...`; it must never be logged unmasked.
- `ZHIPU_MCP_SEARCH_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/web_search_prime/mcp` and calls `web_search_prime` for `web_search`.
- `ZHIPU_MCP_READER_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/web_reader/mcp` and calls `webReader` for `web_fetch`.
- `ZHIPU_MCP_ZREAD_API_URL` defaults to `https://open.bigmodel.cn/api/mcp/zread/mcp` and calls `search_doc`, `get_repo_structure`, and `read_file` through explicit repo/docs commands.
- Zhipu Coding Plan MCP must be implemented as a separate Remote MCP-over-HTTP provider layer. Do not route it through the existing `/paas/v4/web_search` Zhipu REST provider.
- A normal Zhipu Web Search API key is not sufficient evidence of Coding Plan entitlement. If `ZHIPU_MCP_API_KEY` is missing or returns auth/provider errors, MCP providers are skipped or fall through within the same capability; zread remains explicit and does not affect the standard minimum profile.
- Provider failures must appear in `provider_attempts` and fallback must remain same-capability, with model answers and web search treated as mutual fallbacks in ordinary search.
- `doctor` should report configured/not-configured, auth, rate-limit, provider, timeout, and network status without exposing the MCP token.

Jina Reader:

- `JINA_READER_API_URL` defaults to `https://r.jina.ai`.
- `JINA_API_KEY` is required before Jina satisfies `SMART_SEARCH_MINIMUM_PROFILE=standard`.
- Anonymous Jina Reader calls may be used only as explicit/experimental degraded fetch behavior; they must not make standard setup pass.
- `JINA_RESPOND_WITH=readerlm-v2` requires `JINA_API_KEY` and should report a configuration error without a network request when the key is missing.
- Jina Reader is `web_fetch` only, not `web_search`.
- Jina 401/403, 422, 429, timeout, network errors, and low-quality challenge pages such as `Title: Just a moment...` must be reported as failed provider attempts and allow same-capability fallback.

AnySearch:

- AnySearch uses JSON-RPC 2.0 `tools/call` at `ANYSEARCH_API_URL`, default `https://api.anysearch.com/mcp`.
- `ANYSEARCH_API_KEY` is optional. If configured, requests include `Authorization: Bearer ...`; if missing, anonymous requests are allowed.
- `ANYSEARCH_TIMEOUT_SECONDS` defaults to `30`.
- Live MCP tools are `search`, `batch_search`, `extract`, and `get_sub_domains`. `anysearch-domains` maps to `get_sub_domains` (not the removed `list_domains` tool).
- `anysearch-domains DOMAIN` calls the live `get_sub_domains` tool; without `DOMAIN`, it reads the `tools/list` schema for the available domains.
- HTTP 200 responses with `result.isError=true` must return `ok=false`, `error_type=provider_error`, and no successful source results.
- Markdown URL/title/snippet candidates should be parsed into `results`, while raw text remains in `content` and `raw_content`.
- Structured results without URLs must be preserved as raw/structured evidence, not dropped.
- Dotted vertical domain shorthand such as `code.doc` is allowed for simple subdomains and must be normalized to `domain=code` plus `sub_domain=doc`; parameterized subdomains parse `--sub-domain-params` JSON first, then repeatable `--param KEY=VALUE` entries override matching keys. Invalid JSON, non-object JSON, a missing `=`, or an empty key fails before the network request.
- `anysearch-extract --max-length` sends only `url` to the live tool. A positive value truncates successful top-level and result text fields locally; zero or negative values preserve the normalized payload.
- `anysearch-batch` accepts at most 5 CLI query strings and returns `error_type=parameter_error` without sending a request when the limit is exceeded.

Sciverse:

- `SCIVERSE_API_URL` defaults to `https://api.sciverse.space`; `SCIVERSE_TIMEOUT_SECONDS` defaults to `30`.
- `SCIVERSE_API_TOKEN` is required. Missing token returns `error_type=config_error` without a network request; configured requests send `Authorization: Bearer ...` and must never expose the token.
- Commands map directly to Sciverse OpenAPI: catalog -> `GET /meta-catalog`, search -> `POST /meta-search`, semantic -> `POST /agentic-search`, read -> `GET /content`, relations -> `POST /meta-paper-relations`.
- Current `meta-catalog` and `meta-search` schemas have no `collection` selector. Legacy `--collection papers` is accepted without being sent upstream; `authors` and `sources` return `parameter_error` before a request. `meta-search` sends only `query`, `filters`, `sort`, `freshness_boost`, `page`, and `page_size`. `--title-contains` / `--abstract-contains` fold into `query`; author, journal, subject, and year conveniences become current filter items.
- Advanced filters and sorts are structured local contracts: filters require `field` and `value` with a current `operator` such as `FILTER_OP_GTE`; legacy `op` is accepted only when it maps unambiguously. Sort items require `field` and normalize `order` to `SORT_ORDER_ASC` or `SORT_ORDER_DESC`. Full-text `query` and any `sort` conflict, so `--sort-by-year` defaults to `none` and sorting is filter-only.
- `sciverse-semantic --retrieval hybrid|milvus|es` is the current semantic contract. Deprecated `--mode fast|balanced|quality` maps to `retrieval=hybrid` with a warning; it conflicts with explicit `milvus` or `es`. Semantic `--source-types` accepts only `web,pdf`.
- `sciverse-read` uses `doc_id`; `sciverse-relations` uses `unique_id`.
- Relation direction must stay explicit: `CITATIONS` means papers citing the target paper, `REFERENCES` means papers cited by the target paper, and `RELATED_WORKS` means related work suggestions.
- Sciverse's documented HTTP `504` deadline response is `timeout`; other `5xx` responses remain `network_error`.
- Local limits reject before network: search `page_size <= 200` and `page * page_size <= 10000`, semantic `top_k <= 100`, read `limit <= 16384`, relations `page_size <= 200`.
- `--filters-advanced` and `--sort-advanced` must be JSON arrays of valid objects and fail with `parameter_error` before service/provider calls when malformed.

OpenAI-compatible streaming:

- `OPENAI_COMPATIBLE_API_MODE` defaults to `chat-completions` and accepts only `chat-completions` or `responses`. The selected protocol applies consistently to `search()`, provider-side `fetch()`, `describe_url()`, `rank_sources()`, `doctor`, and `diagnose openai-compatible`.
- Responses mode handles the official `model` + `instructions`/`input` subset, heterogeneous `output` text parts, URL citations, typed stream deltas, and terminal failures. It does not promise `/responses` support from every relay marketed as OpenAI-compatible; accept each named relay with both diagnose stream probes.
- `OPENAI_COMPATIBLE_STREAM` defaults to `false` and accepts `true`, `1`, or `yes` as true.
- For OpenAI-compatible search, `search --stream` means "prefer stream first"; stream empty/timeout/retryable protocol failures fall back to the same provider/model with `stream=false`.
- `search --no-stream` forces `stream=false` for the current invocation.
- `SMART_SEARCH_TIMEOUT_SECONDS` defines one 300-second default monotonic `search` budget. Jev selection, channel dependencies and failure fallback share its remaining time; no budget is reserved for a mandatory main model. `search --timeout` overrides the saved value for one invocation. Research uses the same deadline with its configured budget ceilings.
- `OPENAI_COMPATIBLE_FALLBACK_MODELS` is an optional comma-separated ordered list. It is fail-over after a hard primary-model failure, not a time slice. The current candidate keeps the remaining shared main-search budget; extra fallback models must not shrink that budget. `--fallback off` or `--model MODEL` disables this model fallback for the invocation.
- `timeout_phase`, `phase_attempts`, elapsed/remaining deadline values, and `partial_success` report execution progress. Research judgment/filter/synthesis failures preserve completed evidence; ordinary search has no extra/supplemental phase. Strict validation still reports an evidence error when its source requirements are not met.
- OpenAI-compatible attempts may include `model`, `transport`, `fallback_from_transport`, `fallback_from_model`, and `breaker_state`. `transport_fallback_used` records stream-to-non-stream recovery separately from provider/model `fallback_used`.
- Streaming applies to xAI Responses `search()` and OpenAI-compatible `search()` and provider-side `fetch()` calls. `describe_url()` and `rank_sources()` stay non-streaming. xAI Responses uses the shared Responses SSE parser and does not retry with `stream=false`.

Exa domain filters:

- `--include-domains` and `--exclude-domains` accept comma-separated or whitespace-separated domains.
- Both `--include-domains docs.python.org,developer.mozilla.org` and `--include-domains docs.python.org developer.mozilla.org` normalize to the same Exa domain list.
- This normalization is intentional for Windows PowerShell, where an unquoted comma expression can be forwarded through `.ps1` wrappers as a space-separated value.

## Provider Failure Cooldown

- Same-capability fallback assumes a failing provider is worth retrying. A provider whose key is revoked, quota is exhausted, or endpoint is down is not, so its failures are persisted in `provider_health.json` and the provider is skipped for `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` instead of being called again on every invocation.
- Hard failures (`auth_error`, `config_error`) open the cooldown immediately for four cooldown windows and are not probed. Soft failures need `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` consecutive failures within one window, and automatic search respects cooldown until expiry or an explicit reset. Direct fetch retains its bounded recovery probe.
- A skipped provider appears in `provider_attempts` with `status=skipped`, the remembered `error_type`, and a `provider_health` block. It is not a silent drop, and it does not change same-capability fallback order.
- Zhipu reports several failures inside an HTTP `200` body. Those payloads are classified (`auth_error`, `rate_limited`, `provider_error`) instead of being reported as an empty result set, so a dead Zhipu channel is diagnosable and coolable.
- Recovery paths: `smart-search providers reset PROVIDER`, a credential change through `smart-search config set`, a successful `smart-search doctor` probe, or waiting out the cooldown.

## Provider Output Details

- Exa HTTP `400` or `422` failures are returned as `ok=false` with `error_type=parameter_error`; use this to distinguish bad CLI/domain/date/category arguments from upstream network failures.
- AnySearch experimental output should preserve structured results without URLs as raw/structured evidence.
- Sciverse experimental output should preserve raw response data under `raw` while exposing normalized `fields`, `results`, `hits`, `text`, or `items` depending on the command.
- Diagnostic output should report Firecrawl status as whether `FIRECRAWL_API_KEY` is configured; it is not currently a live Firecrawl request.

## Routing Heuristics

- Use `smart-search route "query" --format markdown` when you need to explain why a query maps to `docs_search`, `web_search`, `web_fetch`, or `vertical_search` without executing providers.
- Use `exa-search --include-domains` when official documentation domains are known.
- Use `context7-library` / `context7-docs` for docs/API/SDK/library/framework intent when Context7 is configured.
- Use `zhipu-search` for Chinese, domestic, current, or domain-filtered source discovery when Zhipu is configured.
- Use `exa-search --start-published-date` for recency-constrained source discovery.
- Use `exa-similar` when a known good page is available and adjacent sources are needed.
- Use `search --format content` when a human wants the selected channel output.
- Use `fetch --format markdown` or `fetch --format content` for user-supplied URLs or when exact page text matters.
- Use `map` before fetching many pages from a documentation site.
- Keep `search --extra-sources` small (`1` to `3`) unless broad coverage is requested.
- For current news or high-risk claims, prefer source discovery plus `fetch`; do not treat broad `search.content` plus source metadata as claim-level verification.

## Maintenance Guardrails

- Provider architecture changes must be verified as distributable CLI behavior, not as behavior that only works because one developer machine has a specific wrapper, shell profile, or local config file.
- Register providers by capability first, then route by intent. Fallback is allowed only within the same capability family; model answers and web search are mutual fallbacks in ordinary search.
- Keep xAI Responses and OpenAI-compatible as peer `main_search` providers. A failed xAI Responses request may fall back to OpenAI-compatible only when `OPENAI_COMPATIBLE_API_URL` and `OPENAI_COMPATIBLE_API_KEY` are separately configured.
- Do not use Context7 for broad news or generic web facts; do not use Tavily or Firecrawl as documentation semantic-search replacements.
- After provider-routing changes, run source-checkout regression plus `smart-search smoke --mock --format json`. If live keys were used, run a targeted secret scan for exact key substrings before committing.

`primary_sources` preserves citations from a selected model channel; these are discovery candidates until read. `sources` contains returned source metadata; `extra_sources` is retained as an empty compatibility list.

Explicit cancellation returns `error_type=cancelled` with completed evidence and `partial_success`; do not treat the interrupted request as complete. App cancellation retains the same result and research artifacts.
