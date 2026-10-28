# Command Patterns

## Table of Contents

- Evidence files
- Common commands
- Short aliases
- Timeout retry policy
- Guardrails

## Evidence Files

For multi-source research, use `--output` to save evidence with a descriptive timestamped filename. Stdout should still contain the full JSON result unless markdown or content output was explicitly chosen for human reading.

For claim-level evidence, prefer this order:

1. Discover candidate URLs with source-focused `search`, `zhipu-search` for Chinese/current/domestic topics, Context7 for docs/API/library topics, or `exa-search` for official/trusted domains and papers.
2. Fetch the exact pages that matter.
3. Build claim-level conclusions from fetched pages, or use `research` for automatic multi-source work. Ordinary `search` returns one selected channel and performs no post-retrieval synthesis. Unread sources remain unverified; `extra_sources` is an empty compatibility field.

Deep Research planner output uses an explicit `--evidence-dir` when supplied, otherwise a generated `smart-search-evidence` directory under `tempfile.gettempdir()`. Preserve the CLI's planned `--output` path and `output_path` match; do not rewrite evidence contracts unless a separate docs/runtime fix is in scope. Hard-coded paths such as `C:\tmp\smart-search-evidence\...` should be treated as user-chosen explicit output locations.

## Common Commands

```powershell
smart-search search "query" --extra-sources 5 --timeout 300 --format json --output result.json
smart-search search "query" --stream --format json
smart-search diagnose openai-compatible --format markdown
smart-search search "query" --platform "Reuters" --model "model-id" --extra-sources 3 --timeout 300 --format json
smart-search search "nba战报" --format content
smart-search search "query" --validation strict --fallback auto --providers auto --format json
smart-search exa-search "query" --num-results 5 --search-type neural --include-text --include-highlights --include-domains docs.example.com developer.mozilla.org --format json
smart-search exa-similar "https://example.com/article" --num-results 5 --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/reactjs/react.dev" "useEffect cleanup" --format json
smart-search zhipu-search "today China AI news" --count 5 --format json
smart-search anysearch-domains security --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-search "CVE-2024-3094" --domain security.cve --sub-domain-params '{"type":"legacy","value":"old"}' --param type=cve --param value=CVE-2024-3094 --format json
smart-search anysearch-extract "https://example.com/source" --max-length 12000 --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
smart-search sciverse-catalog --collection papers --format json
smart-search sciverse-search "transformer retrieval" --year-from 2020 --page-size 5 --format json
smart-search sciverse-semantic "attention mechanism" --top-k 3 --retrieval hybrid --source-types web,pdf --format json
smart-search sciverse-read "doc-id-from-search" --offset 0 --limit 4096 --format json
smart-search sciverse-relations "unique-id-from-search" --relation CITATIONS --page-size 25 --format json
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
smart-search route "React useEffect API docs" --format markdown
smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"
smart-search setup --non-interactive --openai-compatible-api-mode responses
smart-search setup --non-interactive --openai-compatible-stream true
smart-search setup --non-interactive --openai-compatible-fallback-models "model-a,model-b"
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "key"
smart-search setup --non-interactive --sciverse-token "key" --sciverse-api-url "https://api.sciverse.space"
smart-search setup --non-interactive --tavily-api-url "https://api.tavily.com" --tavily-key "key"
smart-search --version
smart-search config path --format json
smart-search config list --format json
smart-search config list --format markdown
smart-search config set XAI_API_KEY "key" --format json
smart-search config set XAI_MODEL "grok-4-fast" --format json
smart-search config set XAI_TOOLS "web_search,x_search" --format json
smart-search config set XAI_REASONING_EFFORT "high" --format json
smart-search config set XAI_STREAM "true" --format json
smart-search search "Latest Grok news" --providers xai-responses --stream --format json
smart-search config set OPENAI_COMPATIBLE_API_URL "https://api.openai.com/v1" --format json
smart-search config set OPENAI_COMPATIBLE_API_KEY "key" --format json
smart-search config set OPENAI_COMPATIBLE_MODEL "model-id" --format json
smart-search config set OPENAI_COMPATIBLE_API_MODE "responses" --format json
smart-search config set OPENAI_COMPATIBLE_FALLBACK_MODELS "model-a,model-b" --format json
smart-search config set OPENAI_COMPATIBLE_STREAM "true" --format json
smart-search config set SMART_SEARCH_TIMEOUT_SECONDS "180" --format json
smart-search config set ANYSEARCH_API_URL "https://api.anysearch.com/mcp" --format json
smart-search config set SCIVERSE_API_TOKEN "key" --format json
smart-search config set ANYSEARCH_API_KEY "key" --format json
smart-search config set ANYSEARCH_TIMEOUT_SECONDS "30" --format json
smart-search config set SMART_SEARCH_INTENT_ROUTER "jev" --format json
smart-search config set EXA_API_KEY "key" --format json
smart-search config set CONTEXT7_API_KEY "key" --format json
smart-search config set ZHIPU_API_KEY "key" --format json
smart-search config set ZHIPU_API_URL "https://open.bigmodel.cn/api" --format json
smart-search config set ZHIPU_SEARCH_ENGINE "search_pro" --format json
smart-search config set TAVILY_API_URL "https://api.tavily.com" --format json
smart-search config set TAVILY_ENABLED "false" --format json
smart-search config set TAVILY_TIMEOUT_SECONDS "45" --format json
smart-search config set FIRECRAWL_API_URL "https://api.firecrawl.dev/v2" --format json
smart-search config set TINYFISH_API_KEY "key" --format json
smart-search config set TINYFISH_SEARCH_API_URL "https://api.search.tinyfish.ai" --format json
smart-search config set TINYFISH_FETCH_API_URL "https://api.fetch.tinyfish.ai" --format json
smart-search config set DEEPSEEK_API_KEY "key" --format json
smart-search config set DEEPSEEK_API_URL "https://api.deepseek.com" --format json
smart-search config set YUANBAO_SECRET_ID "id" --format json
smart-search config set YUANBAO_SECRET_KEY "key" --format json
smart-search model current --format json
smart-search doctor --format json
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
smart-search regression
smart-search smoke --mock --format json
smart-search smoke --mock --format markdown
```

`TAVILY_ENABLED=false` is a complete Tavily no-network switch even if `TAVILY_API_KEY` is still saved. It removes Tavily from automatic web-search/fetch routes, makes direct Tavily boundaries and `doctor` local-only, and makes `map` return a configuration error; it does not configure Firecrawl.

## Short Aliases

```powershell
smart-search --v
smart-search s "query" --format json
smart-search rt "React useEffect API docs" --format markdown
smart-search s "nba战报" --format content
smart-search rs "query" --format json
smart-search f "https://example.com" --format markdown
smart-search exa "OpenAI Responses API documentation" --format json
smart-search z "today China AI news" --format json
smart-search c7 "react" "hooks" --format json
smart-search c7docs "/reactjs/react.dev" "useEffect cleanup" --format json
smart-search cfg ls --format json
smart-search d --format markdown
smart-search mdl cur --format json
smart-search sm --format json
smart-search reg
```

## Degraded Provider Recovery

When a search succeeds but `provider_notices` reports a degraded optional provider, or a provider attempt has `status=skipped`, the channel is on a persisted failure cooldown rather than being retried on every call.

1. Run `smart-search providers status --format json` to see the remembered `error_type`, `error`, and `cooldown_remaining_seconds`.
2. For `auth_error` or `config_error`, fix the credential with `smart-search config set` or `smart-search setup`. Re-keying clears the cooldown automatically.
3. For a transient failure, run `smart-search doctor --format json`; a successful probe clears the record.
4. Use `smart-search providers reset PROVIDER` to force an immediate retry, or `smart-search providers reset` to clear every cooldown.
5. Do not work around a cooled-down provider with a different-capability provider; same-capability fallback already covers the query.

## Timeout Retry Policy

When `smart-search search` returns `ok: false` with `error_type: "timeout"`, inspect `timeout_phase` and `provider_attempts` first. Partial results can remain in `content`; ordinary search has no automatic optional source phase.

1. Retry the same search at most once, adding `--extra-sources 1` to limit the selected channel result count.
2. Use `--format json` and `--output PATH` for each attempt; inspect the saved JSON and stop on `"ok": true`.
3. Set the agent's command execution timeout at least 30 seconds longer than the smart-search total budget, or run the command in the background. With the default 300-second budget, the agent timeout must be at least 330 seconds; otherwise the agent can kill smart-search before it returns structured results. `SMART_SEARCH_TIMEOUT_SECONDS` supplies the default; `--timeout` overrides one call.
4. If the retry also times out, switch to source-first evidence:
   - Run `exa-search` with the original query.
   - Run `exa-search --include-domains` when likely official domains are known.
   - `fetch` the top 1-2 relevant URLs before making claim-level statements.
   - Mark the final answer as `source_mode: "fallback"` or state that it was assembled from fetched sources after the original search failed.

Agent timeout handling contract: on `error_type: "timeout"`, inspect `timeout_phase` and `provider_attempts`, then retry the same search at most once with `--extra-sources 1`, for example `smart-search search ... --timeout 300 --extra-sources 1 --format json --output PATH`. Set the agent's command execution timeout at least 30 seconds above the smart-search total budget (at least 330 seconds for the default 300 seconds), or run it in the background, so the agent does not kill it before structured results return. If the retry also times out, switch to source-first fallback with `exa-search`, `exa-search --include-domains`, and fetched evidence, and label the evidence mode as `source_mode: "fallback"` or equivalent prose.

## Guardrails

- Prefer JSON for agent parsing and markdown for fetched page text intended for reading.
- Use `--output` for multi-source work, long pages, or anything the answer may need to cite later.
- Keep `--extra-sources` small (`1` to `3`) unless the user asks for broad coverage.
- Do not cite unread `sources` or model `primary_sources` as proof for a sentence in `content`; fetch the URL first. `extra_sources` remains an empty compatibility list.
- Prefer `exa-search --include-domains` for official documentation when likely domains are known.
- Do not expose API keys. Treat `doctor` output as safe only because it is expected to mask secrets.
- In this CLI-first workflow, native `web_search` is disabled unless the user explicitly configures another approved route.
- If `doctor` or a command fails, report the failure and recovery steps; do not silently fall back to another web-search route.
- Do not use legacy MCP tool names in prompts, notes, or generated instructions for this workflow.
- Treat key rotation as a hard safety gate when previous key values were pasted into chat or logs.
