# Setup And Config

## Table of Contents

- Config storage
- Doctor and diagnostics
- Setup workflow
- Browser config UI
- Skill installation sync
- Provider endpoint setup
- Intent router setup

## Config Storage

- Prefer the CLI's local config file managed by `smart-search setup` / `smart-search config`.
- Environment variables remain supported for CI and advanced users, and override the local config file.
- `SMART_SEARCH_TIMEOUT_SECONDS` persists the total monotonic `search` budget and defaults to `300`; explicit `search --timeout SECONDS` overrides environment, config, and default for one invocation. The budget is also the main-search read ceiling, so slow reasoning models are no longer cut off by a separate fixed provider read timeout.
- `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` defaults to `900` and `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` defaults to `2`. They control how long a repeatedly failing optional provider is skipped; `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS=0` disables the cooldown entirely.
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
- `doctor --format markdown` must render a detailed diagnostic report with overall status, active/default/legacy config paths, log path resolution, file-logging status, masked config values with sources, minimum profile, capability status, providers currently on failure cooldown, main-search provider checks, provider connectivity checks, Jev/local router status, model metadata, and full long error/message detail.
- Use `smart-search diagnose openai-compatible --format markdown` when `doctor` succeeds but OpenAI-compatible `search` appears to hang, returns a timeout, or differs between `--stream` and `--no-stream`. It is the beginner-facing one-command report for upstream/relay compatibility.
- `diagnose openai-compatible --format markdown` must render a short copy-pasteable troubleshooting report with masked config, the selected API mode and endpoint, a quick selected-endpoint check, real search-shape `stream=false` and `stream=true` checks, fallback-model inventory against `/models`, the remaining-budget timeout policy, a plain-language summary, and a next command.

## Setup Workflow

- Interactive `smart-search setup` is a language-selecting grouped wizard with arrow-key / Space / Enter provider selection. It groups optional providers by capability; configure one retrieval channel, then add Jev or page reading as needed.
- Default `smart-search setup` shows a Smart Search ASCII banner, asks for `zh` or `en`, offers user-level `smart-search-cli` skill installation, then shows a grouped provider wizard.
- The grouped wizard should use an arrow-key / Space / Enter selector when packaged TUI dependencies are available, with a text fallback for non-TTY and tests.
- Use `smart-search setup --lang en` for an English wizard.
- Use `smart-search setup --advanced` only when low-level config keys must be shown one by one; Jev/local routing is available in the default wizard. `--advanced` does not show the skill prompt unless `--install-skills` is explicit.
- `--non-interactive` keeps script behavior and only saves values passed as flags.
- Provider groups are optional choices: configure at least one usable retrieval channel, then add Jev and research page reading as needed.
- Unchecking a configured provider must not delete existing config values; use `smart-search config unset KEY` for deletion.
- Interactive output should summarize `minimum_profile_ok`, missing required capabilities, and next-step commands.
- Beginner filling examples for official-service and relay/pooled-endpoint minimum profiles must appear in the grouped wizard on stderr, not stdout. They must cover `main_search`, `docs_search`, and `web_fetch`.

## Browser Config UI

- `smart-search ui` opens a temporary local config page for users who prefer forms to the terminal wizard. Its test page supports offline route preview and ordinary single-pass search; start research from the App or CLI.
- It binds `127.0.0.1` on a random port, prints a URL carrying a one-time token, and exits once the browser tab stops sending heartbeats. It is not a daemon and needs no extra install: stdlib `http.server` plus one bundled HTML file.
- Flags: `--no-browser` (print the URL only), `--port N`, `--idle-timeout SEC` (default `900`, `0` disables), `--lang zh|en`, `--check` (verify the bundled page resolves, then exit), plus the usual `--format`.
- On a headless host, SSH session, or container the browser is deliberately not opened; the URL is printed and a `ssh -L` forwarding recipe is shown. Use `--port` to pin the port for forwarding.
- The page never receives unmasked secrets. Keys supplied through environment variables render as locked, because environment variables override `config.json` on every read; the page names the `unset` to run.
- Per-provider Test buttons call `smart-search providers test PROVIDER` equivalents. Each one is a real, possibly billable API request, so nothing is probed until the user clicks.
- Do not recommend the UI for scripted or non-interactive work; `smart-search setup --non-interactive` and `smart-search config set` remain the automation path.

## Skill Installation Sync

- Skill installation installs the bundled `smart-search-cli` skill into selected AI-tool skill directories and must not run `trellis init`, create hooks, create agents, create commands, or modify other skills.
- Targets are user-level/global directories under the current user's home directory, for example Codex `~/.agents/skills/`, Claude Code `~/.claude/skills/`, Cursor `~/.cursor/skills/`, OpenCode `~/.config/opencode/skills/`, GitHub Copilot `~/.copilot/skills/`, and Hermes Agent `~/.hermes/skills/`.
- Skill targets are `codex`, `claude`, `cursor`, `opencode`, `copilot`, `gemini`, `kiro`, `qoder`, `codebuddy`, `droid`, `pi`, `kilo`, `antigravity`, `windsurf`, and `hermes`.
- OpenCode's canonical global skill directory is `~/.config/opencode/skills/smart-search-cli`. `skills status` reports a discovered legacy `~/.opencode/skills/smart-search-cli` directory as read-only `legacy_locations` metadata; it never migrates or deletes that tree.
- `--skip-skills` disables skill installation.
- `--install-skills codex,claude,cursor,hermes` selects targets explicitly.
- `--skills-root PATH` is an advanced synthetic home-root override used in portable installs or tests. For OpenCode, `--skills-root T` writes to `T/.config/opencode/skills/smart-search-cli`. Normal users should omit it.
- `smart-search agent-guide [relative-path]` reads current instructions directly from the installed CLI. A Skill's local invocation prefix also applies to this command.
- `smart-search skills remove --targets codex --format json` moves selected Skill files into a backup folder and disconnects automatic maintenance. It does not uninstall the CLI or remove configuration.
- CLI-owned automatic maintenance affects only explicitly connected targets bound to this installation. It preserves personal edits, missing files, extra files and each target's configuration directory. Version/capability probes and `skills status` never perform maintenance.
- `smart-search skills status --targets codex,claude,cursor,hermes --format json` compares bundled skill files with installed user-level skill directories. Status values are `missing`, `up_to_date`, `stale`, `extra_files`, and `error`. It reports target paths, bundled file count, installed file count, hashes, hash match flags, missing files, stale files, and extra files. OpenCode also reports discovered legacy locations. Status must not write or delete files.
- `smart-search skills update --targets codex,claude,cursor,hermes --format json` overwrites the managed bundled `smart-search-cli` files for selected targets. For OpenCode, setup and update write managed files only to the canonical config path; legacy trees and user extra files remain untouched. `smart-search skills update --all --format json` selects every target id.
- This daily sync path must not change provider keys, run setup prompts, create Trellis files, create hooks, create agents, create commands, or delete leftover files. Extra installed files are only reported by `skills status`.
- `smart-search setup --non-interactive --install-skills codex` remains the first-time setup compatibility path. Prefer `skills status` and `skills update` for routine global skill synchronization after CLI upgrades.

## Provider Endpoint Setup

- Setup and config output should include `ok` and `config_file`. Saved API keys must be masked in command output.
- Use `smart-search setup --non-interactive --zhipu-api-url "https://open.bigmodel.cn/api" --zhipu-search-engine "search_std"` to save Zhipu Web Search API endpoint and search service without prompts.
- Interactive setup asks for Zhipu API key, API URL, and search service when the user selects Zhipu in the provider wizard.
- `config set ZHIPU_SEARCH_ENGINE VALUE` must remain free-form so newly added official services do not require a CLI release.
- `ZHIPU_API_URL` defaults to `https://open.bigmodel.cn/api`.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`.
- Official Web Search API service values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`.
- Use `smart-search setup --non-interactive --jina-key "key"` to let Jina satisfy `web_fetch`; `JINA_RESPOND_WITH=readerlm-v2` also requires `JINA_API_KEY`.
- Use `smart-search setup --non-interactive --zhipu-mcp-key "key"` only when the user explicitly wants Coding Plan Remote MCP quota.
- Use `smart-search setup --non-interactive --openai-compatible-api-mode responses` only when a named relay requires `/responses`. The default is `chat-completions` and uses `/chat/completions`; invalid modes fail before setup saves any field.
- Use `smart-search setup --non-interactive --openai-compatible-stream true` only when an OpenAI-compatible relay benefits from SSE streaming for long requests. Default remains false.
- Use `smart-search setup --non-interactive --openai-compatible-fallback-models "model-a,model-b"` to save ordered OpenAI-compatible backup models for primary model hard failure. These models do not receive a reserved time slice; the primary model keeps the remaining shared main-search budget. `--fallback off` and `search --model MODEL` disable this model fallback for one invocation.
- Use `smart-search setup --non-interactive --search-timeout 300` or `smart-search config set SMART_SEARCH_TIMEOUT_SECONDS 300` to persist the normal search budget. Invalid non-positive values fail before provider work.
- Use `smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "key"` only for experimental AnySearch acceptance; do not add it to the normal minimum-profile setup.
- Use `smart-search setup --non-interactive --sciverse-token "key" --sciverse-api-url "https://api.sciverse.space"` only for explicit experimental Sciverse academic commands; do not add it to the normal minimum-profile setup.
- `TAVILY_API_URL` defaults to `https://api.tavily.com` and only affects Tavily REST calls. It does not proxy Zhipu.
- Use `TAVILY_API_URL=https://<host>/api/tavily` for Tavily Hikari / pooled endpoints. Root host and `/mcp` inputs are normalized by setup; `/mcp` itself is not the REST base Smart Search should call.
- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity timeout and defaults to `30`. Raise it for slower pooled/community Tavily endpoints before judging the provider unhealthy.
- `ANYSEARCH_API_URL` defaults to `https://api.anysearch.com/mcp`; `ANYSEARCH_TIMEOUT_SECONDS` defaults to `30`.
- `SCIVERSE_API_URL` defaults to `https://api.sciverse.space`; `SCIVERSE_TIMEOUT_SECONDS` defaults to `30`.
- `FIRECRAWL_API_URL` defaults to `https://api.firecrawl.dev/v2`. Use it only for a Firecrawl-compatible REST base.
- Use `smart-search setup --non-interactive --tinyfish-key "key"` to add TinyFish to `web_search` and `web_fetch`. It never satisfies `main_search` or `docs_search`; Jev can select it among the allowed channels.
- `TINYFISH_SEARCH_API_URL` defaults to `https://api.search.tinyfish.ai`, and `TINYFISH_FETCH_API_URL` defaults to `https://api.fetch.tinyfish.ai`. Both authenticate with the `X-API-Key` header, not a bearer token.
- `TINYFISH_TIMEOUT_SECONDS` defaults to `60` and covers both TinyFish search and fetch reads.
- Use `smart-search setup --non-interactive --deepseek-key "key"` to add DeepSeek to `web_search` and `web_fetch` with the same key as the DeepSeek model API. It never satisfies `main_search` or `docs_search`; Jev can select it among the allowed channels.
- Use `smart-search setup --non-interactive --yuanbao-secret-id "id" --yuanbao-secret-key "key"` to add Yuanbao Search to `web_search` with a Tencent Cloud API key that has Yuanbao Search enabled. It never satisfies `main_search`, `docs_search` or `web_fetch`. `YUANBAO_API_URL` defaults to `https://wsa.tencentcloudapi.com`, and `YUANBAO_TIMEOUT_SECONDS` defaults to `30`.
- `DEEPSEEK_API_URL` defaults to `https://api.deepseek.com`, and `DEEPSEEK_TIMEOUT_SECONDS` defaults to `60` and covers both DeepSeek search and fetch reads. Each successful DeepSeek request is billed.

## Provider Failure Cooldown

- Optional providers (`web_search`, `docs_search`, `web_fetch`, `vertical_search`) are additive. When one keeps failing, Smart Search records it in `provider_health.json` next to `config.json` and skips it instead of re-calling it on every invocation. Search-model channels also respect the shared health gate.
- A hard failure (`auth_error`, `config_error`) opens the cooldown on the first occurrence and is never probed, because a bad key does not heal itself. Soft failures (timeout, `5xx`, rate limit) need `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` consecutive failures and automatic search waits until cooldown expiry or an explicit reset.
- An empty result set is not a failure and never opens a cooldown.
- The record is keyed to a fingerprint of the provider's credentials, so re-keying a provider with `smart-search config set` clears its cooldown automatically. A successful `smart-search doctor` probe also clears it.
- `smart-search providers test PROVIDER [PROVIDER...]` checks whether saved credentials still work for one provider at a time, instead of `doctor`'s all-at-once fan-out. Each run is a real API request. `--timeout` caps each probe. A passing test clears that provider's cooldown, the same way a `doctor` probe does. Firecrawl reports `probe: presence` because only key presence can be checked.
- Use `smart-search providers status --format json` to see which providers are cooling and why, and `smart-search providers reset PROVIDER` to retry one immediately. `smart-search providers reset` with no argument clears every cooldown.
- Use `smart-search setup --non-interactive --provider-cooldown 600 --provider-failure-threshold 3`, or `smart-search config set SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS VALUE`, to persist the cooldown policy. A negative or non-numeric cooldown and a non-positive threshold fail before setup saves any field.
- A skipped provider is still reported: the attempt has `status=skipped` with the remembered `error_type`, and `provider_notices` carries one deduplicated entry per degraded provider.

## Intent Router Setup

- `--search-timeout` (also `--search-timeout-seconds`) is the non-interactive setup flag for the total search budget; it does not change individual provider endpoint timeouts.

## Language and complete handbook

From v0.1.21, Smart Search supports `smart-search --lang en --help`, `smart-search search QUERY --lang zh`, and saved `SMART_SEARCH_LANGUAGE=auto|zh|en` through `config set`. Priority is per-call flag, dedicated environment variable, saved configuration, then system locale. Command/JSON identifiers and source content stay unchanged. App language is independent.

The [bilingual handbook](https://github.com/konbakuyomu/smartsearch/tree/main/docs/guide) contains the [complete command reference](https://github.com/konbakuyomu/smartsearch/blob/main/docs/guide/en/cli-reference.md) and [all saved configuration keys](https://github.com/konbakuyomu/smartsearch/blob/main/docs/guide/en/configuration-reference.md).

## Current routing configuration

`SMART_SEARCH_INTENT_ROUTER=jev|local` defaults to `jev`. `hybrid` maps to `jev`; `rules`/`off` map to `local`. Retired `INTENT_EMBEDDING_*`, `INTENT_CLASSIFIER_*`, and `INTENT_ROUTER_TIMEOUT_SECONDS` keys stay stored, without remote calls or preset changes.

```powershell
smart-search config set TYPESAFE_API_KEY "your-key"
smart-search config set SMART_SEARCH_INTENT_ROUTER jev
smart-search route "React docs" --format json
```

`TYPESAFE_API_KEY` is optional with `--fallback auto`; local routing needs no router credentials. See `references/provider-routing.md` for the two-mode execution contract.
