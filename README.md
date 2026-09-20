<div align="center">

<img src="assets/branding/smart-search.png" alt="Smart Search" width="112">

# smart-search

**Put your AI and your terminal online: search the web, read pages, run deep research**

[简体中文](README.zh-CN.md) | English

[![npm](https://img.shields.io/npm/v/@konbakuyomu/smart-search?label=npm&logo=npm&color=CB3837)](https://www.npmjs.com/package/@konbakuyomu/smart-search)
[![downloads](https://img.shields.io/npm/dm/@konbakuyomu/smart-search?label=downloads&logo=npm)](https://www.npmjs.com/package/@konbakuyomu/smart-search)
[![CI](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![node](https://img.shields.io/badge/node-%3E%3D18-5FA04E?logo=node.js&logoColor=white)](package.json)
[![python](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![stars](https://img.shields.io/github/stars/konbakuyomu/smartsearch?style=flat&logo=github)](https://github.com/konbakuyomu/smartsearch/stargazers)

</div>

## What it is

An AI assistant cannot go online by itself. Ask it what happened today or how a
library's new API works, and it answers from whatever it memorized during
training, or makes something up.

smart-search does the looking up and hands back the actual page text. There are
two ways to use it.

- **Desktop app**: download an installer, open the window, fill in your keys,
  then search, read pages and run deep research. No Python or Node needed.
- **Command line**: install the CLI, and AI tools such as Claude Code, Codex and
  Cursor call it through a bundled skill.

Both share one config and one search core, and the CLI keeps working while the
app is closed.

The search capacity comes from third-party providers, so you bring your own API
keys. smart-search does not ship search quota.

## Install

### Desktop app

All four installers are on the
[v0.1.20 release page](https://github.com/konbakuyomu/smartsearch/releases/tag/v0.1.20).
Pick the one for your machine.

| Your machine | Download |
| --- | --- |
| Windows (Intel / AMD) | [win-x64 installer](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-win-x64-Setup-unsigned-test.exe) |
| Windows (ARM64) | [win-arm64 installer](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-win-arm64-Setup-unsigned-test.exe) |
| macOS (Apple silicon) | [macos-arm64 disk image](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-macos-arm64-unsigned-test.dmg) |
| macOS (Intel) | [macos-x86_64 disk image](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-macos-x86_64-unsigned-test.dmg) |

The installers are unsigned and the macOS builds are not notarized, so the
system will stop you once. On Windows, click **More info → Run anyway** in the
SmartScreen dialog. On macOS, open **System Settings → Privacy & Security** and
click **Open Anyway**. To check that a download was not tampered with, the
release page carries a `SHA256SUMS.txt` with a hash for every file.

Windows x64 has been through install, upgrade, uninstall and daily use on real
hardware. The macOS and Windows ARM64 packages are CI builds whose on-device
validation is not finished.

### Command line

```bash
npm install -g @konbakuyomu/smart-search@latest
smart-search --version
```

You need Node.js (npm) and Python 3.10 or newer. The install builds its own
isolated Python runtime, and afterwards you only ever type `smart-search`.

## Configure

Configuring means filling in API keys. One key for each of three capabilities is
enough for everyday use.

| Capability | What it does | Where to get a key (pick one) |
| --- | --- | --- |
| Main search | Ask a question, get an answer with sources | [xAI](https://console.x.ai/team/default/api-keys), or any OpenAI-compatible endpoint including relays |
| Docs search | Look up official library, framework and API docs | [Context7](https://context7.com/), [Exa](https://dashboard.exa.ai/api-keys) |
| Web fetch | Pull the body text out of a given URL | [Tavily](https://app.tavily.com/home), [Jina](https://jina.ai/), [Firecrawl](https://www.firecrawl.dev/app/api-keys) |

If you often search Chinese news and policy, add
[Zhipu Web Search](https://open.bigmodel.cn/usercenter/apikeys) as well. The
remaining providers are all optional and listed in the
[full reference](docs/reference.md#provider-and-api-key-guide).

**In the app**: open the Providers page, fill in URL, key and model, test the
draft, then save. An empty key box keeps the stored value. The Overview page
tells you whether all three capabilities are covered.

**In a browser** (for CLI users):

```bash
smart-search ui
```

It serves a temporary page on `127.0.0.1` at a random port, prints a URL
carrying a one-time token, and exits when you close the tab. All 68 config keys
are grouped by provider, secrets stay masked, and each provider has a **Test**
button. One click is one real API request against your quota, and nothing is
tested until you click.

The terminal wizard `smart-search setup` does the same job.

**Then check your work**:

```bash
smart-search doctor --format markdown
```

It prints the current config with secrets masked, and says which of the three
capabilities are covered and which key fails to connect.

## Use it

### The app

The app has six pages; these four are the ones you will live in.

- **Overview**: what is missing from your config and what to set up next
- **Search & research**: search, read pages, look up docs, generate an offline
  plan or run live research, then copy or export the result
- **Activity**: which stage is running, through which provider, how long it
  took, how it ended
- **AI integration**: CLI paths and versions, how to call them, and which tools
  to install the skill into

Of the remaining two, the Providers page is covered above, and Settings & About
handles the config directory, the theme and update checks. The
[desktop guide](docs/desktop.md) has the details.

### The CLI

This one runs with no keys configured at all. It only explains which kind of
search a question needs, and calls no provider:

```bash
smart-search route "React useEffect cleanup function docs" --format markdown
```

Once configured, these five cover daily work:

```bash
smart-search search "today's important AI news" --format markdown          # search and answer
smart-search fetch "https://example.com/post" --format markdown            # pull this page's text
smart-search deep "recent Bitcoin market movement" --format markdown       # break the question down, offline
smart-search research "recent Bitcoin market movement" --budget deep --format markdown  # run the full live workflow
smart-search doctor --format markdown                                      # health check
```

Use `--format markdown` to read, `--format json` for scripts and agents. The
full command table is in the [reference](docs/reference.md#commands).

### Let AI tools call it

```bash
smart-search setup --non-interactive --install-skills codex,claude,cursor
```

This writes the `smart-search-cli` skill into each tool's user directory, such
as `~/.claude/skills`. After that you just ask Claude Code a question, and it
calls smart-search when it needs to look something up. Fifteen tool targets are
supported; `smart-search skills status --format json` lists them all.

After upgrading the CLI, resync the skill:

```bash
smart-search skills update --targets codex,claude,cursor --format json
```

## When something breaks

| What you see | Try this first |
| --- | --- |
| `doctor` reports `config_error` | `smart-search setup` again, then rerun `doctor` |
| Search hangs and never returns | `smart-search diagnose openai-compatible --format markdown` |
| Search is slow | Lower `--extra-sources`, split a broad question into smaller ones |
| One provider keeps failing | `smart-search providers status --format markdown` shows whether it is on cooldown; `smart-search providers reset <name>` clears it |
| Not sure the install worked | `smart-search --version` and `smart-search regression` |

Installing the app does not overwrite an existing config, and uninstalling it
keeps your config, research evidence and exported results.

## Going further

| What you want | Where to look |
| --- | --- |
| Every command, provider setting, routing rule and deep-research detail | [Full reference](docs/reference.md) |
| Desktop pages, activity, updates and uninstall | [Desktop guide](docs/desktop.md) |
| JEV semantic routing and filtering | [Jev routing](docs/jev-routing.md) |
| What changed in this version | [v0.1.20 release notes](https://github.com/konbakuyomu/smartsearch/releases/tag/v0.1.20) |

## Acknowledgements

Thanks to the [LINUX DO](https://linux.do/) community for the feedback and
discussion that shaped this tool.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=konbakuyomu/smartsearch&type=Date)](https://www.star-history.com/#konbakuyomu/smartsearch&Date)

## License

MIT
