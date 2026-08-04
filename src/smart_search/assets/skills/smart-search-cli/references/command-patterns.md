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
3. Use broad `search` only as synthesis or discovery, and mark claims as unverified when only `extra_sources` are available.

Deep Research planner output uses an explicit `--evidence-dir` when supplied, otherwise a generated `smart-search-evidence` directory under `tempfile.gettempdir()`. Preserve the CLI's planned `--output` path and `output_path` match; do not rewrite evidence contracts unless a separate docs/runtime fix is in scope. Hard-coded paths such as `C:\tmp\smart-search-evidence\...` should be treated as user-chosen explicit output locations.

## Common Commands

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
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain security.vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-search "CVE-2024-3094" --domain security.cve --sub-domain-params '{"type":"cve","value":"CVE-2024-3094"}' --format json
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
smart-search route "React useEffect API docs" --format markdown
smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"
smart-search setup --non-interactive --openai-compatible-stream true
smart-search setup --non-interactive --openai-compatible-fallback-models "model-a,model-b"
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
smart-search config set OPENAI_COMPATIBLE_FALLBACK_MODELS "model-a,model-b" --format json
smart-search config set OPENAI_COMPATIBLE_STREAM "true" --format json
smart-search config set ANYSEARCH_API_URL "https://api.anysearch.com/mcp" --format json
smart-search config set ANYSEARCH_API_KEY "key" --format json
smart-search config set ANYSEARCH_TIMEOUT_SECONDS "30" --format json
smart-search config set SMART_SEARCH_INTENT_ROUTER "hybrid" --format json
smart-search config set INTENT_EMBEDDING_API_URL "https://api.siliconflow.cn/v1/embeddings" --format json
smart-search config set INTENT_EMBEDDING_API_KEY "key" --format json
smart-search config set INTENT_EMBEDDING_MODEL "Qwen/Qwen3-Embedding-8B" --format json
smart-search config set INTENT_EMBEDDING_THRESHOLD "0.475" --format json
smart-search config set INTENT_EMBEDDING_MARGIN "0.053" --format json
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format json
smart-search config set INTENT_CLASSIFIER_API_URL "https://api.openai.com/v1/chat/completions" --format json
smart-search config set INTENT_CLASSIFIER_API_KEY "key" --format json
smart-search config set INTENT_CLASSIFIER_MODEL "gpt-4.1-mini" --format json
smart-search config set INTENT_ROUTER_TIMEOUT_SECONDS "8" --format json
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
4. Always use the CLI's `--timeout` option. Do not wrap `smart-search` in a shell-level `timeout` command because shell termination can prevent structured failure JSON.
5. Do not rely on `SMART_SEARCH_RETRY_*` settings; search command timeouts are surfaced by the CLI result contract and should be handled by the agent workflow.
6. If all attempts time out, fall back to source-first evidence:
   - Run `exa-search` with the original query.
   - Run `exa-search --include-domains` when likely official domains are known.
   - `fetch` the top 1-2 relevant URLs before making claim-level statements.
   - Mark the final answer as `source_mode: "fallback"` or clearly state that the answer was assembled from fetched sources rather than generated by `search`.

Agent timeout handling contract: `smart-search search ... --timeout 180 --extra-sources 1 --format json --output PATH` is the retry shape; it is not a shell-level `timeout` wrapper. `SMART_SEARCH_RETRY_*` settings are not the contract for this path. After repeated timeout failures, switch to source-first fallback with `exa-search`, `exa-search --include-domains`, and fetched evidence. Final answers assembled through that fallback should explicitly label the evidence mode, for example `source_mode: "fallback"` or equivalent prose.

## Guardrails

- Prefer JSON for agent parsing and markdown for fetched page text intended for reading.
- Use `--output` for multi-source work, long pages, or anything the answer may need to cite later.
- Keep `--extra-sources` small (`1` to `3`) unless the user asks for broad coverage.
- Do not cite `extra_sources` as proof for a sentence in `content`; fetch the URL first or cite it only as a candidate source.
- Prefer `exa-search --include-domains` for official documentation when likely domains are known.
- Do not expose API keys. Treat `doctor` output as safe only because it is expected to mask secrets.
- In this CLI-first workflow, native `web_search` is disabled unless the user explicitly configures another approved route.
- If `doctor` or a command fails, report the failure and recovery steps; do not silently fall back to another web-search route.
- Do not use legacy MCP tool names in prompts, notes, or generated instructions for this workflow.
- Treat key rotation as a hard safety gate when previous key values were pasted into chat or logs.
