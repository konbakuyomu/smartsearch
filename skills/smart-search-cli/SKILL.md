---
name: smart-search-cli
description: "Instructions for AI agents to use the local smart-search CLI for current web search, source-backed fact checking, URL fetching, site mapping, official/API/documentation search, deep research, and reproducible evidence instead of MCP tools or native web search."
---

# Smart Search CLI

Use the local `smart-search` command as the default execution layer for web research. This entrypoint keeps only routing, boundaries, and reference selection; load the focused reference file when command details or provider contracts matter.

## What This Skill Is

`smart-search-cli` is an instruction bundle for an AI tool. It explains when to call the local `smart-search` executable, which command fits the user's intent, how to preserve source evidence, and how to interpret provider status and fallback fields.

- The Skill does not provide search access by itself; the configured `smart-search` CLI and its providers do the work.
- The Skill is not an MCP server, does not store provider API keys, and does not create Trellis, hooks, agents, or commands.
- `smart-search setup --install-skills ...` connects selected Agents. Installed Skills use a short bootstrap: run `smart-search agent-guide` for this CLI's current instructions and `smart-search agent-guide references/<name>.md` for a referenced document.
- The App's **Update Skills** page reads the selected CLI's catalog. Explicit sync backs up changed files; **Remove Skills** backs up and disconnects selected targets. Automatic maintenance belongs to the CLI, works with the App closed, and preserves personal edits. Each connected target retains its CLI installation and configuration profile.
- After upgrading the CLI, normal use checks its managed Skills; `skills status` remains read-only and `skills update` provides an explicit refresh. Reopen the Agent session after changes (Gemini: `/skills reload`).
- Skill updates do not change provider configuration or API keys. Missing optional keys remain skipped rather than being treated as successful live checks.

## Default Workflow

1. Run `smart-search doctor --format json` when configuration or availability is uncertain.
2. If `doctor` reports missing configuration, use `smart-search setup` or `smart-search config set KEY VALUE` when the user provides keys. Do not ask users to edit global environment variables by default.
3. If OpenAI-compatible `search` hangs or times out after `doctor` succeeds, run `smart-search diagnose openai-compatible --format markdown` and use its summary.
4. Keep `OPENAI_COMPATIBLE_API_MODE=chat-completions` unless a named relay has passed the official Responses subset probes; set `responses` only for that relay and keep the diagnostic evidence. For a model that searches only through the Responses `web_search` tool (for example `gpt-6.1-sol` with an official OpenAI key), also set `OPENAI_COMPATIBLE_TOOLS=web_search`.
5. If `doctor` returns `ok: true`, use only `smart-search` CLI subcommands for web research. Do not call Codex native web search in the same task.
6. Use `smart-search skills status --targets codex --format json` when the installed global skill may be stale; use `smart-search skills update --targets codex --format json` to refresh it without rerunning setup.
7. Use `smart-search smoke --mock --format json` after CLI/provider architecture changes. Use `--live` only when real keys are available and the user expects live checks.
8. Treat `TAVILY_ENABLED=false` as an intentional no-network boundary: do not work around it with direct Tavily or `map` calls. Check `doctor` and live smoke for disabled/skipped Tavily state; Firecrawl remains independently configured.
9. If a result reports a degraded provider in `provider_notices`, or a provider attempt is `skipped`, run `smart-search providers status --format json`. The channel is on a persisted failure cooldown; fix the credential or run `smart-search providers reset PROVIDER` instead of retrying the same failing provider.
10. Preserve command lines and source URLs in your answer. Prefer citing fetched pages; treat model citations and unread search sources as discovery candidates.

## Routing

- `search`: single-pass retrieval: Jev or local rules select one suitable channel, which returns results and sources; no automatic assessment, follow-up, filtering, or synthesis.
- `route`: explain capability routing locally without executing providers; `--router-mode jev --remote` explicitly opts into a potentially billable TypeSafe judgment.
- `research`: shared bounded loop with Jev or local routing for complementary discovery, fetch/read, evidence gaps, and optional synthesis.
- `deep`: offline Deep Research planner; it does not run providers, fetch pages, or replace default `search`.
- `zhipu-search`: Chinese-language, domestic China, policy/regulatory, announcements, current news, or China-local source discovery.
- `context7-library` / `context7-docs`: library, SDK, API, framework, or documentation intent. Ordinary search uses the first library in Context7's ranked candidates; research may ask Jev to choose a candidate, using the first candidate if Jev fails or no score reaches its threshold. Unresolved libraries allow same-capability fallback. Explicit commands retain the candidate list and supplied library id.
- `exa-search`: official domains, papers, product pages, trusted pages, date/domain-filtered low-noise discovery, and adjacent source discovery through `exa-similar`.
- `fetch`: user-provided URLs or any claim that depends on page content.
- `map`: documentation site or domain structure before fetching many pages from one site.
- `anysearch-*`: explicit experimental vertical search only. Inspect domains first and do not use AnySearch as default fallback. Parse JSON parameters before repeatable `--param key=value` overrides; `anysearch-extract --max-length` sends only the URL upstream and truncates successful text locally.
- `sciverse-*`: explicit experimental academic search only. Use for catalog/search/semantic/read/relations; do not use Sciverse as `docs_search`, `standard`, or default `search` / `research` fallback.
- `providers status` / `providers reset`: inspect or clear the persisted failure cooldown for optional providers; use it when a channel keeps reporting the same failure.
- `model current`: inspect explicit provider models only. Change models with `smart-search config set XAI_MODEL ...` or `smart-search config set OPENAI_COMPATIBLE_MODEL ...`.

## Key Boundaries

- `smart-search` should resolve from the user's PATH.
- Private API keys should be saved with `smart-search setup` or `smart-search config set`; environment variables remain supported for CI and advanced users.
- In sandboxed runtimes, set `SMART_SEARCH_CONFIG_DIR` to an absolute writable path when the default config directory is unavailable or must be pinned.
- The standard minimum profile requires at least one enabled retrieval channel. Jev and a main model are optional; the requested operation still needs a capable channel.
- Fallback stays within the same capability family; model answers and web search are mutual fallbacks in ordinary search. Do not use Context7 for broad news/web facts or page-extraction providers as documentation search replacements.
- Inspect `answer_check` and `primary_sources_count` before trusting `content`.
- xAI Responses and OpenAI-compatible are peer `main_search` providers. Do not reuse one provider's URL/key to fabricate the other provider as fallback.
- For current-news, policy, finance, health, and other high-risk facts, do not answer from broad `search.content` alone. Fetch key pages and summarize only what fetched text supports.
- Native `web_search` is disabled in this CLI-first workflow unless the user explicitly configures another approved route; do not silently fall back to another web-search route.

## References

- Command examples, evidence files, timeout retry policy, and guardrails: `references/command-patterns.md`
- Deep Research planner/executor workflow, plan fields, gap check, and smoke matrix: `references/deep-research-mode.md`
- CLI entrypoints, command signatures, aliases, output fields, exit codes, and tool policy: `references/cli-core.md`
- Setup, config storage, skill installation, provider endpoints, and OpenAI-compatible diagnostics: `references/setup-config.md`
- Intent routing, provider capabilities, source provenance, fallback boundaries, and routing maintenance: `references/provider-routing.md`
- Regression, packaged install checks, release lanes, and release closeout lessons: `references/regression-release.md`
- Compatibility reference map for older instructions that mention the original monolithic file: `references/cli-contract.md`
