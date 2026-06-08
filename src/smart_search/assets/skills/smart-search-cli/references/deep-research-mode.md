# Deep Research Mode

## Deep Research Skill Contract

This contract keeps Deep Research capability-based and evidence-first:
`smart-search deep` only plans, `smart-search research` executes live work, and
claim-level conclusions require fetched evidence. Evidence paths come from an
explicit `--evidence-dir` or the CLI's platform temporary directory; preserve the
planned `steps[].command --output` value and matching `steps[].output_path`.

## Table of Contents

- Trigger and boundary
- Offline planner and live executor
- Planner shape
- Required field semantics
- Step contract
- Capability boundaries
- Live executor output
- Closeout lessons
- Smoke coverage

## Trigger And Boundary

Use Deep Research Mode when the user asks for `深度搜索`, `深度调研`, `深入搜索`, `deep search`, `deep research`, multi-source verification, cross-checking, serious review, or selection/comparison research. This is a capability-based orchestration workflow.

Do not select a fixed topic recipe. Market, product, technical docs, news, policy, claim-checking, and URL-first prompts are examples of user language, not schema modes. Deep Research must not require fixed topic recipe ids such as `current_market_research`, `product_comparison_research`, `technical_docs_research`, `news_or_policy_research`, `claim_verification_research`, or `url_first_research`; fixed topic recipe ids are not required schema.

Deep Research does not change default `smart-search search` behavior and does not depend on an MCP session. It must not change default `smart-search search` behavior.

## Offline Planner And Live Executor

- `smart-search deep` is the public offline planner command and a public planner entrypoint, not an executor. It does not call providers, run `doctor`, or fetch pages by default.
- `smart-search research` is the public live executor command and public live executor entrypoint. It executes plan -> discover -> fetch/read -> gap check -> evidence-only synthesis.
- Before manual execution, run `smart-search deep "question" --format json` and use the returned `research_plan` as your planning artifact.
- Use `smart-search research "question" --format json` when the user wants the CLI to run live Deep Research end to end instead of only planning.

Default orchestration:

1. Run `smart-search doctor --format json` as preflight when configuration is uncertain.
2. Call `smart-search deep "question" --format json` to create an offline `research_plan`.
3. Inspect `intent_signals`, `decomposition`, and `capability_plan`; do not choose fixed topic recipe ids.
4. Execute planned `smart-search search ... --validation balanced --extra-sources 1..3` steps for broad discovery and read routing metadata.
5. Execute planned `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, or `map` only when their capability boundary matches the intent.
6. Use `fetch` on key URLs before making claim-level statements.
7. Run `gap_check`: if an important claim lacks fetched evidence, fetch another source or mark the claim/source as unverified.

Default evidence policy is `fetch_before_claim`: key claims in the final answer must be supported by fetched page text. Treat `primary_sources` and `extra_sources` as discovery candidates until the relevant URL has been fetched. Final answers should include fetched evidence, unverified candidate sources, and key commands used.

## Planner Shape

Use this shape as the planning artifact:

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
      "command": "smart-search search \"query\" --validation balanced --extra-sources 1 --format json --output \"<evidence-dir>/YYYYMMDD-HHMM-topic/01-search.json\"",
      "output_path": "<evidence-dir>/YYYYMMDD-HHMM-topic/01-search.json"
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

## Required Field Semantics

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
- `allowed_tools`, `evidence_dir`, and `elapsed_ms` may appear in planner output and should be preserved when saving evidence.
- `evidence_dir`: the explicit `--evidence-dir` value, or a generated `smart-search-evidence` directory under the platform temporary directory when omitted.

`smart-search deep` is offline by default: `preflight.executed_by_deep_command=false`, no provider calls are made, and live research only happens when an AI agent or user executes `steps[].command` or calls `smart-search research`.

## Step Contract

Allowed `tool` values are `search`, `exa-search`, `exa-similar`, `zhipu-search`, `context7-library`, `context7-docs`, `fetch`, and `map`; these are the only valid `steps[].tool` values and map to existing CLI commands only. `doctor` is a `preflight` action, not a `steps[]` item. Simple plans may have one subquestion; complex plans should use 2-6 subquestions unless the user explicitly asks for exhaustive coverage.

Each `steps[]` item must include `id`, `subquestion_id`, `tool`, `purpose`, `command`, and `output_path`. `steps[].command` and `steps[].output_path` are one contract: the `--output` path embedded in the executable command must match `output_path`, otherwise the AI agent cannot reliably find saved evidence.

Prefer PowerShell-safe quoted commands in generated plans because Windows users often copy planned steps directly from Markdown or JSON output. Avoid hard-coding operating-system-specific roots in reusable examples; use `--evidence-dir PATH` or the CLI-generated `evidence_dir`.

## Capability Boundaries

- `search`: broad discovery and synthesis through `main_search`; use returned `routing_decision`, `provider_attempts`, `fallback_used`, and `source_warning` as orchestration signals, not as claim proof.
- `zhipu-search`: Chinese, domestic, current, policy/regulatory, announcement, and China-local source discovery.
- `context7-library` and `context7-docs`: library, SDK, API, framework, and documentation intent. Prefer Context7 before Exa for docs/API questions.
- `exa-search`: low-noise source discovery for official domains, papers, product pages, known domains, and trusted pages. Do not treat Exa as the universal second hop for every high-risk or verification task.
- `exa-similar`: adjacent-source discovery when a known reliable URL is available.
- `search --extra-sources N`: Tavily/Firecrawl horizontal candidate collection for breadth. Treat those candidates as discovery until fetched.
- `anysearch-domains` and `anysearch-search`: experimental vertical search. Inspect domains first, then search a selected domain; do not insert it into the default fallback chain.
- `fetch`: page-content evidence. Key claims require fetched page text under `fetch_before_claim`.
- `map`: site structure exploration before many fetches from one site; not claim evidence by itself.

## Live Executor Output

Use this form when the user wants the CLI to execute the live workflow directly:

```powershell
smart-search research "question" --budget deep --fallback auto --evidence-dir "<evidence-dir>" --format json --output "research.json"
```

`research --fallback auto` permits same-capability fallback inside selected routes. `research --fallback off` tries only the first selected provider in each capability route and is for debugging or provider comparison. Dynamic routing may reorder providers only inside the same capability. Every attempt must record capability, provider, status, error type, latency, and result count.

Research output includes `final_answer`, `citations`, `evidence_items`, `gap_check`, `provider_attempts`, `fallback_used`, `degraded`, `route_policy_version`, and `evidence_dir`. The synthesis is evidence-only. It may cite fetched/read evidence, but it must not cite unfetched discovery candidates as proof. If providers are exhausted or evidence cannot close, return the degraded gaps rather than inventing missing claims.

Research provider advantage routing:

- Context7: library/API/framework docs resolution and docs retrieval.
- Exa: official domains, papers, product/company pages, date/domain-filtered low-noise discovery, and adjacent-source discovery.
- Zhipu REST: Chinese, domestic, current, policy, and announcement searches.
- Zhipu MCP: separate Coding Plan quota route through `web_search_prime` and `webReader`.
- Tavily: broad source discovery and site map.
- Jina: known public URL, PDF, and arXiv clean extraction; ReaderLM-v2 requires `JINA_API_KEY`.
- Firecrawl: robust fetch fallback, JS-heavy/dynamic pages, browser-like extraction, OCR/PDF/structured extraction.
- AnySearch: explicit vertical intent only, such as CVE, finance, legal, academic, and repository/codebase search.

Safe research overrides are `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`. They may reorder or disable providers only inside capabilities the provider already supports; they must not move a provider across capability boundaries.

## Closeout Lessons

- Budget limits must not break evidence policy. Even `--budget quick` plans must retain at least one `fetch` step when claim-level conclusions are expected, and retained steps must keep valid `subquestion_id` links.
- If a smoke issue is found, fix the affected docs/code/tests and rerun the affected smoke until it passes or is proven to be an external provider blocker.
- Final answers assembled from discovery-only output should list unverified candidates rather than presenting them as supported claims.

## Smoke Coverage

Deep Research smoke matrix for workflow maintenance is mock-full plus live-limited. Mock-full coverage should cover trigger phrases, normal search requests that should not trigger Deep Research, required `research_plan` fields, allowed tool whitelist, `fetch_before_claim`, evidence output paths, capability boundaries, `intent_signals`, `capability_plan`, `gap_check`, simple current prompts such as `深度搜索一下最近的比特币行情`, docs/API prompts, claim-verification prompts, user-provided URL fetch-first flows, missing-provider failure guidance, research provider advantage routing, same-capability research fallback, and the rule that fixed topic recipe ids are not required schema.

Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch` only when real keys are available and the user expects live checks. Add one small `research` smoke when configured keys make it stable.

Standard user-facing Deep Research tests:

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search deep "帮我核验这个说法是真是假：某某工具已经完全替代 Tavily 做 AI 搜索了" --format json
smart-search deep "https://example.com/source" --format json
```
