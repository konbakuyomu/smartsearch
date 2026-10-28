[Guide](../README.md) · [简体中文](../zh-CN/research.md)

# Search and research

`search` and `research` are the two live search modes. Both share the configured channel catalog, execution, deadlines, and evidence records.

- `search`: one Jev routing judgment selects one suitable channel, then returns results and sources. Necessary dependent requests (such as Context7 library resolution followed by docs) and same-capability failure fallback remain; model answers and web search are mutual fallbacks in ordinary search. It never runs evidence assessment, follow-up search, filtering, or synthesis. `--extra-sources N` limits results from that channel (up to 20), not the number of channels. `evidence_assessment.status=not_evaluated`; success is retrieval success, not factual verification. `--validation strict` requires source evidence and can return partial content with an evidence error.
- `research`: Jev selects complementary actions in parallel, reads discovered pages, assesses evidence gaps, and continues while useful and within budget. It chooses from program-built original/subquestion/gap query candidates; Jev does not generate arbitrary queries or tool calls. Only fetched/read content enters `citations`. Optional filtering and `SMART_SEARCH_JEV_SYNTHESIZE=false|auto|true` apply only here.
- `deep` remains an offline planner. Its `steps[].command` entries are suggestions for manual/AI orchestration; `research` records its actual actions separately in `routing_decision.rounds` and `stage_results`.

The default is `SMART_SEARCH_INTENT_ROUTER=jev`. Without a TypeSafe key or a valid judgment, `--fallback auto` uses local capability rules and reports degradation; `--fallback off` fails clearly. Without a TypeSafe key, `research` stops after the first round that reads page text (`judgment_unavailable`) and is always reported as degraded; `deep` uses strict validation, which needs Jev to judge the evidence sufficient, so it never returns `ok=true`. `SMART_SEARCH_JEV_SYNTHESIZE=true` still summarizes the evidence that was read; `auto` needs Jev. Configure a TypeSafe key for dependable research. Explicit `local` never calls Jev. Legacy `hybrid` maps to `jev`; `rules` and `off` map to `local`. Old embedding/classifier keys remain stored but unused. `route-calibrate` is a retired, non-network compatibility command.

`route` previews local capabilities without calling a model or retrieval provider. Add `--remote` only for an explicit, potentially billable Jev diagnostic. Direct provider commands keep their explicit behavior.

Only configured, enabled, allowed channels outside cooldown can run. `--providers`, provider enable switches, `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`, and explicit-only boundaries are enforced before selection and dispatch. A failed ordinary channel can try another provider of the same capability, with model answers and web search treated as mutual fallbacks; it cannot turn into a research loop. User preferences do not bypass these boundaries.

The shared total timeout defaults to 300 seconds (`SMART_SEARCH_TIMEOUT_SECONDS`, overridden by `search --timeout`). Research quick/standard/deep ceilings are 2/3/10 rounds, 1/2/10 channels per round, 3/5/20 results per channel, and 45/120/configured seconds, further limited by the configured Jev budgets. Sufficient evidence, exhaustion, no progress, or deadline stops the loop. Completed results survive optional judgment/filter/synthesis failure.

## Capabilities and providers

| Capability | Main commands | Providers | Role |
| --- | --- | --- | --- |
| `main_search` | `search` | xAI Responses, OpenAI-compatible Chat Completions or Responses | Broad answer generation and synthesis |
| `docs_search` | `context7-library`, `context7-docs`, `exa-search` | Context7, Exa | Official docs, SDKs, APIs, framework/library evidence |
| `web_search` | `zhipu-search`, `zhipu-mcp-search`, selected by `search` | Zhipu Web Search API, Zhipu Coding Plan MCP, Tavily, Firecrawl, TinyFish, DeepSeek, Yuanbao Search | Chinese, domestic, current, domain-filtered, or supplementary web discovery |
| `web_fetch` | `fetch`, `zhipu-mcp-reader` | Tavily, Jina Reader, Zhipu Coding Plan MCP Reader, Firecrawl, TinyFish, DeepSeek | Exact URL content extraction for evidence |
| `vertical_search` | `anysearch-domains`, `anysearch-search`, `anysearch-extract`, `anysearch-batch`, `sciverse-catalog`, `sciverse-search`, `sciverse-semantic`, `sciverse-read`, `sciverse-relations` | AnySearch and Sciverse (experimental) | Explicit structured vertical domains; Sciverse covers academic literature search, semantic search, content chunks, and citation relations |
| `site_map` | `map` | Tavily | Site/documentation structure discovery |
| `deep_planner` | `deep` / `dr` | Local planner only | Offline plan generation; no provider call by default |
| `research_executor` | `research` / `rs` | Registered providers by capability | Shared Jev loop with fetched evidence |

```powershell
smart-search search "React useEffect API docs" --format json
smart-search research "Compare the documented limitations" --budget deep --evidence-dir "./evidence" --format json
smart-search deep "Plan a comparison" --budget standard --format json
smart-search route "React useEffect API docs" --format markdown
smart-search fetch "https://example.com/source" --format markdown
```

Use `sources` as discovery metadata until page content is read. `primary_sources` contains model citations when a model channel was selected. The legacy `extra_sources` list stays empty. Research saves its plan, evidence Markdown, `summary.json`, and `report.json` under `evidence_dir`; inspect `gap_check`, `provider_attempts`, `warnings`, and `partial_success` before drawing conclusions. Sciverse stays explicit-only; use `sciverse-*` commands directly. See [configuration](configuration.md) and [Jev details](../../jev-routing.md).

## Offline plan and evidence fields

Deep Research is not a fixed topic recipe system. Plans expose `intent_signals`, `decomposition`, `capability_plan`, and `usage_boundary`; `doctor` is preflight, not a research step. Runtime reports preserve `route_policy_version`, `intent_router_mode`, `required_capabilities`, and `degraded_reason` alongside actual attempts. Unsupported key claims must be fetched or downgraded to unverified candidates.

AnySearch and Sciverse are not part of the `web_search` fallback and are not required by the `standard` minimum profile. Sciverse is not `docs_search` and remains explicit-only. AnySearch can be selected for a supported vertical question when configured.

Explicit cancellation stops pending work and returns `error_type=cancelled` with completed content, sources, citations, and `partial_success`. App task status remains cancelled; partial evidence is also saved in the research report.
