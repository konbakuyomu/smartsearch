[Guide](../README.md) · [简体中文](../zh-CN/cli.md)

# CLI guide

All commands, aliases, nested subcommands and options are listed in the [complete command reference](cli-reference.md).

## Language and scripting

The CLI uses the system language by default: Chinese for a Chinese locale, English otherwise. It has its own saved preference, independent of the App.

```sh
smart-search config set SMART_SEARCH_LANGUAGE en
smart-search --lang zh --help
smart-search config list --lang en
smart-search config set SMART_SEARCH_LANGUAGE auto
```

`--lang auto|zh|en` works before or after the command, including nested subcommands and help. `zh-CN` and `en-US` are accepted. Text after `--` is literal and is not interpreted as a language flag. Priority is the one-call flag, `SMART_SEARCH_LANGUAGE` environment variable, the current configuration file, then the system locale. A one-call flag does not write configuration. App language changes do not change any of these settings. Invalid explicit values fail with exit code `2`; an unreadable saved preference falls back to the system language with a warning on stderr.

Help, prompts and tool-owned status/error text follow the selected language. Command names, flags, JSON keys/enums, provider/model IDs, input queries and source/answer text stay unchanged. External logs remain in their original language. Use `--format json` for scripts; diagnostic warnings go to stderr. `--version` keeps its language-independent format.

| Exit code | Meaning |
| --- | --- |
| `0` | Successful result, including a successful partial result with its limitations in the payload |
| `2` | Invalid command or parameter |
| `3` | Missing or invalid configuration |
| `4` | Network failure |
| `5` | Other runtime failure |

Read `ok`, `partial_success`, status and evidence fields as well as the exit code. A successful offline research plan is not an executed search. Explicit live commands, provider tests and remote routing may use paid quota; `--help`, `--version`, local routing and mock smoke do not.

## CLI installation

Stable channel:

```powershell
npm install -g @konbakuyomu/smart-search@latest
smart-search --version
smart-search setup
```

Test channel:

```powershell
npm install -g @konbakuyomu/smart-search@next
smart-search --version
```

The new npm package selects a self-contained CLI for your OS and CPU. Python and its dependencies are bundled at release time. Installation and first launch do not find, download or configure user Python. The launcher isolates Python, virtualenv, Conda and PyInstaller environment variables.

The npm package bundles its runtime and does not use local Python, virtual environments, or Conda. If you prefer uv, install from source:
```sh
uv tool install git+https://github.com/konbakuyomu/smartsearch.git
```
To pin the Python version, append `--python 3.13` to the install command; uv downloads that version independently of your local embedded Python.
Upgrade with `uv tool upgrade smart-search`. This installation bypasses npm and is not managed by the App's CLI update entry.

Prerequisites:

- Node.js 18+ / npm.
- macOS, Windows or Linux on x64 / arm64. Linux requires glibc 2.35+; Alpine/musl is unsupported.
- Keep npm optional dependencies enabled; do not use `--omit=optional`. `--ignore-scripts` is supported.

Published npm 0.1.24 and earlier still use the Python setup flow. This behavior takes effect with the new binary npm release.

## CLI quick start

1. Configure providers, in a browser or in the terminal:

```powershell
smart-search ui                  # a temporary local page, see Configure In A Browser
smart-search setup               # or the interactive terminal wizard
smart-search doctor --format json
```

2. If OpenAI-compatible `search` hangs or times out, generate the short troubleshooting report:

```powershell
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
```

3. Run a normal live search:

```powershell
smart-search search "today's important AI news" --validation balanced --extra-sources 2 --format json
```

4. Inspect intent routing without running providers:

```powershell
smart-search route "React useEffect API docs" --format markdown
smart-search route "请核验这个链接里的说法 https://example.com/source" --format json
```

5. Fetch exact page evidence:

```powershell
smart-search fetch "https://example.com/source" --format markdown --output evidence.md
```

6. Plan Deep Research:

```powershell
smart-search deep "Deep research recent Bitcoin market movement" --budget standard --format json
```

7. Run live Deep Research when you want the CLI to execute the staged workflow:

```powershell
smart-search research "Deep research recent Bitcoin market movement" --budget deep --format markdown
```

8. Install the skill for AI tools when setup prompts you, or explicitly:

```powershell
smart-search setup --non-interactive --install-skills codex,claude,cursor,hermes
```

Skill installation writes the bundled `smart-search-cli` skill into user-level tool directories such as
`~/.agents/skills`, `~/.claude/skills`, `~/.cursor/skills`, `~/.hermes/skills`, and OpenCode
`~/.config/opencode/skills/smart-search-cli`. It does not initialize Trellis, hooks, agents, or commands. `--skills-root PATH` is a
synthetic home-root override for portable or test installs, so an OpenCode install under `T` writes to
`T/.config/opencode/skills/smart-search-cli`.

9. After upgrading the CLI, refresh the installed global skill:

```powershell
smart-search skills status --targets codex --format json
smart-search skills update --targets codex --format json
```

`setup --install-skills` remains available for first-time setup. For routine synchronization after package updates, use
`skills status` and `skills update`; they only inspect or overwrite the managed `smart-search-cli` files and do not change
provider keys or create Trellis/hooks/agents/commands. OpenCode status reports a discovered legacy
`~/.opencode/skills/smart-search-cli` tree as read-only `legacy_locations` metadata; it is never moved or deleted automatically. Setup and update write
only managed bundled files to the canonical OpenCode target and leave legacy and other extra files untouched.

## Local browser configuration

68 config keys read badly as a wall of text. `smart-search ui` opens a temporary local page instead, grouped by what each key is for:

```powershell
smart-search ui
```

It starts on `127.0.0.1` with a random port, prints a URL carrying a one-time token, and exits once you close the tab. Nothing is left running and nothing is installed — the server is Python's standard library and the page is one HTML file.

What it does:

- a three-step wizard for the only three capabilities you actually need, with a live indicator that turns green when the minimum profile is satisfied
- every key grouped by provider, with secrets shown masked and never sent to the browser in the clear
- a **Test** button per provider that checks whether a saved key still works — each click is one real API request, so nothing is tested until you ask
- which providers are on cooldown, and a button to clear one
- skill install status for all 15 agent targets

Useful flags:

| Flag | Effect |
| --- | --- |
| `--no-browser` | Print the URL without opening a browser |
| `--port N` | Bind a fixed port instead of a random one |
| `--idle-timeout SEC` | Exit after this many idle seconds (default `900`, `0` disables) |
| `--lang zh\|en` | Interface language |
| `--check` | Verify the bundled page is installed, then exit |

On a remote machine no browser opens; forward the port instead:

```bash
smart-search ui --no-browser --port 8765
ssh -L 8765:127.0.0.1:8765 user@host      # then open the printed URL locally
```

In WSL the Windows default browser opens instead. If the page does not load under `networkingMode=mirrored`, see [Using Smart Search in WSL or on Linux](troubleshooting.md#using-smart-search-in-wsl-or-on-linux).

A key set through an environment variable shows as locked and cannot be edited from the page, because environment variables override `config.json` on every read. The page tells you which `unset` to run.

The CLI equivalents remain: `smart-search setup`, `smart-search config set KEY VALUE`, and `smart-search providers test PROVIDER`.

## Commands and examples

| Command | Alias | Purpose |
| --- | --- | --- |
| `search` | `s` | Fast live search and broad synthesis |
| `route` | `rt` | Explain required capabilities without running providers |
| `deep` | `dr` | Offline Deep Research plan |
| `research` | `rs` | Live Deep Research execution |
| `fetch` | `f` | Fetch one URL as JSON, Markdown, or content |
| `map` | `m` | Map a website structure |
| `exa-search` | `exa`, `x` | Exa source discovery |
| `exa-similar` | `xs` | Similar pages from one URL |
| `zhipu-search` | `z`, `zp` | Zhipu Web Search API |
| `zhipu-mcp-search` | `zmcp-search` | Zhipu Coding Plan MCP `web_search_prime` |
| `zhipu-mcp-reader` | `zmcp-reader` | Zhipu Coding Plan MCP `webReader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` | Search open-source repository docs through zread MCP |
| `zhipu-mcp-repo-structure` | `zmcp-tree` | Read repository structure through zread MCP |
| `zhipu-mcp-read-file` | `zmcp-file` | Read one repository file through zread MCP |
| `anysearch-domains` | `as-domains` | Experimental AnySearch domain discovery |
| `anysearch-search` | `as-search`, `as` | Experimental AnySearch vertical/general search |
| `anysearch-extract` | `as-extract` | Experimental AnySearch URL extraction |
| `anysearch-batch` | `as-batch` | Experimental AnySearch batch search, up to 5 queries |
| `sciverse-catalog` | `sv-catalog` | Experimental Sciverse academic field catalog |
| `sciverse-search` | `sv-search`, `sv` | Experimental Sciverse structured academic search |
| `sciverse-semantic` | `sv-semantic` | Experimental Sciverse semantic paper search |
| `sciverse-read` | `sv-read` | Experimental Sciverse document chunk read by `doc_id` |
| `sciverse-relations` | `sv-relations` | Experimental Sciverse citation/reference/related-work relations by `unique_id` |
| `context7-library` | `c7`, `ctx7` | Resolve Context7 library candidates |
| `context7-docs` | `c7d`, `c7docs`, `ctx7-docs` | Fetch Context7 docs |
| `route-calibrate` | `route-cal`, `rcal` | Retired compatibility command; no remote calls |
| `doctor` | `d` | Masked config and connectivity check |
| `diagnose` | `diag` | Focused OpenAI-compatible troubleshooting report |
| `setup` | `init` | Interactive or scripted setup |
| `config` | `cfg` | Local config read/write |
| `model` | `mdl` | Show explicit provider model settings; use `config set XAI_MODEL` or `OPENAI_COMPATIBLE_MODEL` to change them |
| `providers` | `prov` | Inspect (`status`) or clear (`reset`) the persisted failure cooldown for optional providers |
| `smoke` | `sm` | Provider routing smoke tests |
| `regression` | `reg` | Offline regression checks |

Smoke output includes `status` (`healthy`, `degraded`, or `failed`) and explicit `skipped_cases`. A healthy or degraded smoke report remains `ok: true` with exit code `0`; only failed smoke is non-zero.

When `search` returns `error_type: "timeout"`, inspect `timeout_phase` and `provider_attempts` first. Retry the same search at most once with `--extra-sources 1`. If it times out again, switch to source-first commands such as `exa-search`, fetch the relevant pages, and label the evidence mode as `source_mode: "fallback"` or equivalent prose. Agents must set their command execution timeout at least 30 seconds above the smart-search total budget (at least 330 seconds for the default 300 seconds), or run the command in the background; otherwise the agent can kill smart-search before it returns structured results.

Useful examples:

```powershell
smart-search search "query" --validation balanced --extra-sources 3 --timeout 300 --format json --output result.json
smart-search route "React useEffect API docs" --format markdown
smart-search research "query" --budget deep --fallback auto --format json --output research.json
smart-search search "query" --stream --format json
smart-search search "query" --no-stream --format json
smart-search config set OPENAI_COMPATIBLE_API_MODE "responses" --format json
smart-search config set OPENAI_COMPATIBLE_TOOLS "web_search" --format json
smart-search config set OPENAI_COMPATIBLE_FALLBACK_MODELS "grok-4.3-fast" --format json
smart-search search "nba report" --format content
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/reactjs/react.dev" "useEffect cleanup" --format json
smart-search zhipu-search "today China AI news" --search-engine search_pro_sogou --count 5 --format json
smart-search zhipu-mcp-search "today China AI news" --count 5 --format json
smart-search zhipu-mcp-reader "https://example.com/source" --format json
smart-search zhipu-mcp-search-doc "owner/repo" "install" --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --max-length 12000 --format json
smart-search sciverse-search "transformer retrieval" --year-from 2020 --page-size 5 --format json
smart-search sciverse-relations "unique-id-from-search" --relation CITATIONS --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --limit 50 --format json
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
smart-search providers status --format markdown
smart-search providers reset zhipu --format json
smart-search smoke --mock --format json
smart-search regression
```

## Offline first check

Without `--remote`, `route` explains which capabilities a query needs locally, so it returns exit code `0` on a fresh install with no API key:

```powershell
smart-search route "React useEffect cleanup function docs" --format markdown
```

```text
# Intent Route

Status: OK
Query: `React useEffect cleanup function docs`
Mode: `jev`
Executed search: NO
Required capabilities: `docs_search`
Confidence: `0.82`
Engines: `rules`
Degraded: YES
Executed search: NO; provider_selection: not_executed

## Reasons
- rules matched docs/API/library terms
```

The same call in `--format json` is what an agent consumes:

```json
{
  "ok": true,
  "query": "今天 OpenAI 发布了什么",
  "executed_search": false,
  "provider_selection": "not_executed",
  "required_capabilities": ["docs_search", "web_search"],
  "confidence": 0.84,
  "router_engines_used": ["rules"],
  "reasons": [
    "rules matched docs/API/library terms",
    "rules matched current/locale/news terms"
  ]
}
```
