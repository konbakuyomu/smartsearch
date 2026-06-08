# Setup And Config

## Table of Contents

- Config storage
- Doctor and diagnostics
- Setup workflow
- Skill installation sync
- Provider endpoint setup
- Intent router setup

## Config Storage

- Prefer the CLI's local config file managed by `smart-search setup` / `smart-search config`.
- Environment variables remain supported for CI and advanced users, and override the local config file.
- Do not ask users to set Windows global API-key environment variables by default.
- If keys are changed with `smart-search config set`, rerun the CLI; no Codex restart is needed.
- If PATH is changed, a new terminal or Codex restart may be needed.
- On Windows, the default local config file is `%LOCALAPPDATA%\smart-search\config.json`. Linux/macOS default to `~/.config/smart-search/config.json`.
- In sandboxed runtimes where the default config directory is not writable or must be pinned, set `SMART_SEARCH_CONFIG_DIR` to an absolute writable path. The CLI uses it for both config and relative logs and skips default-directory selection.
- Earlier Windows source defaults used `~\.config\smart-search\config.json`, while some installs were already pinned to `%LOCALAPPDATA%\smart-search` through `SMART_SEARCH_CONFIG_DIR`. If the new default file is missing but the old file exists, `doctor` reports `legacy_windows_home` as the active source so upgrades do not silently lose configuration.
- When a Windows user reports different config paths, diagnose in this order: `config_dir_source`, `config_dir_override_value`, `config_dir_override_matches_default`, then `legacy_windows_config_exists`. Do not delete either config file or the user-level override until the upgraded CLI has been verified with `config path`, `doctor`, and smoke/regression checks.

## Doctor And Diagnostics

- Use `smart-search doctor --format json` for agent/script parsing and `smart-search doctor --format markdown` when a human wants a detailed diagnostic report.
- If `smart-search doctor --format json` returns `ok: false`, follow the `error` field's guidance (`smart-search setup` or `smart-search config set KEY VALUE`); do not silently fall back to native web search.
- `doctor --format markdown` must render a detailed diagnostic report with overall status, active/default/legacy config paths, log path resolution, file-logging status, masked config values with sources, minimum profile, capability status, main-search provider checks, provider connectivity checks, intent router status, embedding threshold/margin metadata, model metadata, and full long error/message detail.
- Use `smart-search diagnose openai-compatible --format markdown` when `doctor` succeeds but OpenAI-compatible `search` appears to hang, returns a timeout, or differs between `--stream` and `--no-stream`. It is the beginner-facing one-command report for upstream/relay compatibility.
- `diagnose openai-compatible --format markdown` must render a short copy-pasteable troubleshooting report with masked config, quick chat check, real search-shape `stream=false` and `stream=true` checks, a plain-language summary, and a next command.

## Setup Workflow

- Interactive `smart-search setup` is a language-selecting grouped wizard with arrow-key / Space / Enter provider selection. It guides users through required `main_search`, `docs_search`, and fetch capability, then optional `web_search` reinforcement and optional smart intent router configuration.
- Default `smart-search setup` shows a Smart Search ASCII banner, asks for `zh` or `en`, offers user-level `smart-search-cli` skill installation, then shows a grouped provider wizard.
- The grouped wizard should use an arrow-key / Space / Enter selector when packaged TUI dependencies are available, with a text fallback for non-TTY and tests.
- Use `smart-search setup --lang en` for an English wizard.
- Use `smart-search setup --advanced` only when low-level config keys must be shown one by one; normal intent router, embeddings, and classifier setup is available in the default wizard. `--advanced` does not show the skill prompt unless `--install-skills` is explicit.
- `--non-interactive` keeps script behavior and only saves values passed as flags.
- Required groups are `main_search`, `docs_search`, and `web_fetch`; `web_search` is optional reinforcement, followed by optional smart intent router configuration.
- Unchecking a configured provider must not delete existing config values; use `smart-search config unset KEY` for deletion.
- Interactive output should summarize `minimum_profile_ok`, missing required capabilities, and next-step commands.
- Beginner filling examples for official-service and relay/pooled-endpoint minimum profiles must appear in the grouped wizard on stderr, not stdout. They must cover `main_search`, `docs_search`, and `web_fetch`.

## Skill Installation Sync

- Skill installation installs the bundled `smart-search-cli` skill into selected AI-tool skill directories and must not run `trellis init`, create hooks, create agents, create commands, or modify other skills.
- Targets are user-level/global directories under the current user's home directory, for example Codex `~/.codex/skills/`, Claude Code `~/.claude/skills/`, Cursor `~/.cursor/skills/`, GitHub Copilot `~/.copilot/skills/`, and Hermes Agent `~/.hermes/skills/`.
- Skill targets are `codex`, `claude`, `cursor`, `opencode`, `copilot`, `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`, `antigravity`, `windsurf`, and `hermes`.
- `--skip-skills` disables skill installation.
- `--install-skills codex,claude,cursor,hermes` selects targets explicitly.
- `--skills-root PATH` is an advanced override for the user-level install root used in portable installs or tests. Normal users should omit it.
- `smart-search skills status --targets codex,claude,cursor,hermes --format json` compares bundled skill files with installed user-level skill directories. Status values are `missing`, `up_to_date`, `stale`, `extra_files`, and `error`. It reports target paths, bundled file count, installed file count, hashes, hash match flags, missing files, stale files, and extra files. It must not write or delete files.
- `smart-search skills update --targets codex,claude,cursor,hermes --format json` overwrites the managed bundled `smart-search-cli` files for selected targets. `smart-search skills update --all --format json` selects every target id.
- This daily sync path must not change provider keys, run setup prompts, create Trellis files, create hooks, create agents, create commands, or delete leftover files. Extra installed files are only reported by `skills status`.
- `smart-search setup --non-interactive --install-skills codex` remains the first-time setup compatibility path. Prefer `skills status` and `skills update` for routine global skill synchronization after CLI upgrades.

## Provider Endpoint Setup

- Setup and config output should include `ok` and `config_file`. Saved API keys must be masked in command output.
- Use `smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"` to save Zhipu Web Search API endpoint and search service without prompts.
- Interactive setup asks for Zhipu API key, API URL, and search service when optional `web_search` reinforcement selects Zhipu.
- `config set ZHIPU_SEARCH_ENGINE VALUE` must remain free-form so newly added official services do not require a CLI release.
- `ZHIPU_API_URL` defaults to `https://open.bigmodel.cn/api`.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`.
- Official Web Search API service values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`.
- Use `smart-search setup --non-interactive --jina-key "key"` to let Jina satisfy `web_fetch`; `JINA_RESPOND_WITH=readerlm-v2` also requires `JINA_API_KEY`.
- Use `smart-search setup --non-interactive --zhipu-mcp-key "key"` only when the user explicitly wants Coding Plan Remote MCP quota.
- Use `smart-search setup --non-interactive --openai-compatible-stream true` only when an OpenAI-compatible relay benefits from SSE streaming for long requests. Default remains false.
- Use `smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "key"` only for experimental AnySearch acceptance; do not add it to the normal minimum-profile setup.
- `TAVILY_API_URL` defaults to `https://api.tavily.com` and only affects Tavily REST calls. It does not proxy Zhipu.
- Use `TAVILY_API_URL=https://<host>/api/tavily` for Tavily Hikari / pooled endpoints. Root host and `/mcp` inputs are normalized by setup; `/mcp` itself is not the REST base Smart Search should call.
- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity timeout and defaults to `30`. Raise it for slower pooled/community Tavily endpoints before judging the provider unhealthy.
- `ANYSEARCH_API_URL` defaults to `https://api.anysearch.com/mcp`; `ANYSEARCH_TIMEOUT_SECONDS` defaults to `30`.
- `FIRECRAWL_API_URL` defaults to `https://api.firecrawl.dev/v2`. Use it only for a Firecrawl-compatible REST base.

## Intent Router Setup

- Interactive setup asks for `SMART_SEARCH_INTENT_ROUTER`, `INTENT_EMBEDDING_*`, `INTENT_CLASSIFIER_*`, and `INTENT_ROUTER_TIMEOUT_SECONDS` when optional smart intent routing is selected. Keep examples official or neutral and keep keys masked.
- Default guided setup can configure `SMART_SEARCH_INTENT_ROUTER`, `INTENT_EMBEDDING_*`, `INTENT_CLASSIFIER_*`, and `INTENT_ROUTER_TIMEOUT_SECONDS` without `--advanced`.
- Default guided setup recommends SiliconFlow + `Qwen/Qwen3-Embedding-8B` for embeddings and auto-fills threshold `0.475` plus margin `0.053` when no explicit threshold/margin exists.
- Existing mismatched threshold/margin values should produce a warning rather than being silently overwritten.
