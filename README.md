<div align="center">

<img src="https://raw.githubusercontent.com/konbakuyomu/smartsearch/main/assets/branding/smart-search.png" alt="Smart Search" width="112">

# Smart Search

**Search the web, read sources, and bring current information into your AI conversations.**

[简体中文](README.zh-CN.md) | English

[![npm](https://img.shields.io/npm/v/@konbakuyomu/smart-search)](https://www.npmjs.com/package/@konbakuyomu/smart-search)
[![CI](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/konbakuyomu/smartsearch/blob/main/LICENSE)

[Download the App](https://github.com/konbakuyomu/smartsearch/releases/latest) · [User guide](https://github.com/konbakuyomu/smartsearch/tree/main/docs/guide) · [Report a problem](https://github.com/konbakuyomu/smartsearch/issues)

</div>

## What is Smart Search?

Smart Search connects search and page-reading services to AI tools such as Codex and Claude Code. Use the App to configure and test services and install CLI/Skills. Your AI or terminal uses the independent CLI for everyday searches.

You choose the providers and supply their API keys. The App manages configuration; the independent command-line tool runs AI requests even after you close the App.

## When is it useful?

- **Working with a library or API:** find current documentation and read the relevant pages.
- **Following recent changes:** look up announcements or news that may be newer than a model's knowledge.
- **Checking a claim:** find its source, read the page, and compare it with other evidence.
- **Researching a larger question:** collect sources, inspect gaps, and build a cited answer.

These tasks need information from the web and a way to trace it back to its source. Smart Search puts search, page reading, and provider configuration in one place. A search hit is a starting point; read the source before relying on an important claim.

## Get started in the App

1. **Download and open Smart Search.** Choose the package for your system from [Releases](https://github.com/konbakuyomu/smartsearch/releases/latest). The App includes its own runtime.
2. **Open Configuration.** Add services for the three required jobs: answering searches, finding documentation, and reading pages. The page shows what is still missing and where to obtain each key. Check or test the settings, then save them.
3. **Open CLI & Skills.** Install the CLI; the App prepares missing dependencies and verifies its version. Select Agents and choose Install/update selected Skills to check the source, back up changes and sync.
4. **Reopen the Agent session.** Ask it to run `smart-search --version`, then try a search. Install and sign into Agent applications yourself.

Provider tests and searches may use your providers' paid quota. Opening the App or checking the local environment does not run a paid search.

Version 0.1.24 combines the refreshed native interface with Velopack on Windows and Sparkle on macOS, and publishes the first official framework update feeds. App updates include the private engine; independent CLI updates initialize their Python runtime, while Skills updates compare file contents. Existing Inno installations require a one-time full migration. Windows `-signed.exe` packages use a **self-signed certificate** and may still trigger SmartScreen; see [Windows signatures and first launch](docs/windows-signing.md). macOS uses ad-hoc bundle integrity signing and separate Sparkle EdDSA update signatures, without Developer ID signing or notarization. Final GUI and old-install migration acceptance remains separate from automated build and upgrade checks.

[App setup, supported platforms, and troubleshooting →](https://github.com/konbakuyomu/smartsearch/blob/main/docs/guide/en/app.md)

## Everyday use

**Verify configuration in the App:** use Test for search, page reading, Context7, route preview or offline smoke. Results and cancellation stay on that page. Use the CLI for full search and research workflows.

**In your AI tool:** ask naturally, for example:

> Use Smart Search to find the current React documentation for useEffect cleanup. Read the relevant page and include the source.

> Use Smart Search to check the claims in this page: https://example.com/article

The App can stay closed. Your AI calls the independent CLI using the installed integration instructions.

**Language:** the App follows your system by default. Change it in Settings → Language. The CLI has its own saved preference and a one-command `--lang en` / `--lang zh` override. These settings change the tool's interface and messages, not the text of a source page.

## Prefer the terminal?

```sh
npm install -g @konbakuyomu/smart-search@latest
smart-search setup
```

Manual CLI installation needs Node.js 18+ and Python 3.10+. See the [CLI guide](https://github.com/konbakuyomu/smartsearch/blob/main/docs/guide/en/cli.md) for installation, language settings, commands, and examples.

## Need more detail?

The [complete guide](https://github.com/konbakuyomu/smartsearch/tree/main/docs/guide) covers all commands and configuration keys, provider choices, research, and troubleshooting. Development and release instructions are there too.

Thanks to the [LINUX DO](https://linux.do/) community for its feedback and discussion.

[![Star History Chart](https://api.star-history.com/svg?repos=konbakuyomu/smartsearch&type=Date)](https://www.star-history.com/#konbakuyomu/smartsearch&Date)

Licensed under [MIT](https://github.com/konbakuyomu/smartsearch/blob/main/LICENSE).
