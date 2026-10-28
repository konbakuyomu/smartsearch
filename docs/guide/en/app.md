[Guide](../README.md) · [简体中文](../zh-CN/app.md)

# Set up and use the App

## Install and open

Download the package for your operating system and architecture from [Releases](https://github.com/konbakuyomu/smartsearch/releases/latest). Windows installs for the current user. The App contains a native interface and installation manager, without a bundled CLI. Overview starts by detecting your Node.js / npm or accepting a manual npm path. The CLI is installed through that npm and includes Python. The App does not download Node.js or Python.

Environment preparation and full App/CLI language switching are available from v0.1.21; the Update Skills page is available from v0.1.22. Windows self-signing and the new transparent icon are available from v0.1.23. Windows `-signed.exe` packages use a self-signed certificate that Windows does not trust by default, so SmartScreen may still appear. Check the official release source and [public certificate fingerprint](../../windows-signing.md), then decide whether to use the options allowed by your system. This does not permanently trust the certificate or require disabling security protection. Older `-unsigned-test.exe` packages remain unsigned; older macOS packages use ad-hoc signing; after maintainer setup, new packages use a fixed self-signed identity, without Developer ID or notarization. See [macOS signing](../../macos-signing.md). Complete macOS/Windows ARM64 device use, clean-machine operation and the DPI matrix still require manual validation.

Version 0.1.24 introduces the first official Velopack/Sparkle update feeds and the refreshed native interface. Existing Inno installations need the one-time full migration described below. This first framework release provides complete update packages; later releases can add deltas against its verified baseline.

Open **Smart Search** from the Start menu or Applications. Existing configuration is reused. Overview shows whether you have providers for main search, documentation lookup, and page reading.

### macOS installation and first launch

1. Choose a Mac installer from the release download table. The universal version supports both Apple Silicon and Intel.
2. Open the DMG, drag **Smart Search** to **Applications**, and wait for the copy to finish.
3. Double-click **Smart Search** in Applications once to attempt the first launch.
4. If macOS cannot verify the developer or check the app, confirm it came from this project's release page. Open **Apple menu → System Settings → Privacy & Security**, scroll to Security, and click **Open Anyway** beside the Smart Search message.
5. Authenticate if requested, then click **Open** in the confirmation dialog. macOS remembers the exception for this app; future launches can use Applications directly.

If Open Anyway is missing, try launching the app again before returning to Settings. Organization-managed Macs may restrict this setting. See [Apple's first-launch instructions](https://support.apple.com/en-us/102445). For a damaged-app or will-damage-your-computer warning, first check the source, integrity and signature using the [macOS troubleshooting guide](troubleshooting.md#macos-says-the-app-is-damaged-or-the-developer-cannot-be-verified), rather than treating it as an unidentified-developer warning.

## Configure services

1. Open **Providers** and select a service for each missing capability. The page links to the provider's documentation and key registration page. See [Providers and configuration](configuration.md) for the choices.
2. Enter the address, API key and model that your provider supplies. Leave optional settings at their defaults unless your provider requires otherwise.
3. Test the draft if you want to check the connection, then preview and save the changes. Testing and searches can consume paid provider quota; simply opening the App does not run them.

Edits stay in a draft until saved. An empty key field keeps the saved key; select the explicit clear option to remove it. Fields overridden by environment variables show their effective source, and saving does not replace those environment values. Tasks already running keep their original configuration snapshot.

## Update Agent Skills

1. Open **Update Skills** to read the selected CLI's Skill catalog and target paths. Use **Refresh CLI Skills** to read it again.
2. Select Agents and confirm the changed files. Updates back up changed content and retain extra files, unselected targets and historical copies.
3. The installed Skill calls `smart-search agent-guide` for the current CLI's full instructions. Reopen the Agent session and verify invocation with `smart-search --version`.
4. **Remove Skills** moves selected files to a backup folder and removes those targets from automatic maintenance.

Automatic maintenance is enabled for connected targets by default. It checks on first use after a CLI upgrade and daily thereafter, even when the App is closed or removed. Personal edits and missing files are preserved for manual review. Disable maintenance in Skill preferences if needed.

Codex, Claude Code, Cursor, Copilot, Gemini, OpenCode, Cline, Roo Code and the other listed targets use the same Skill. Codex uses `~/.agents/skills/smart-search-cli`; other compatible Agents may read that shared directory too. Historical `.codex/skills` copies are kept. Claude respects an absolute `CLAUDE_CONFIG_DIR`. OpenCode uses `~/.config/opencode/skills` and reports old `.opencode/skills` copies. WSL, remote hosts and Cloud Agents need their own setup; local files are not automatically synced there.

## Manage the independent CLI

Overview is the single **Local environment** entry for installation, version, connection and updates. Follow its steps to prepare the environment, configure providers, test the connection, then optionally connect Skills. Open **Environment details…** for paths, ownership and update preferences.

Automatic discovery checks PATH, common Node.js directories, mise, nvm and Volta, including the separate Smart Search tool resolved through global mise. Select an installation or specify npm in **Environment details…**. A missing selected path never silently switches installations.

At launch the App connects with the previous detection and then detects again in the background. When nothing changed, it stays quiet. When the CLI in use changed (for example, after an upgrade in a terminal), it switches and tells you, or asks you to use the refresh button at the top right later if a task or unsaved edit is open. When the CLI in use is no longer found, it keeps the current connection and tells you. The refresh button at the top right and **Detect again** show detection while it runs. The first launch, or one whose previous CLI no longer exists, detects in full as before. npm operations retain their original prefix; mise updates retain mise ownership and recognized options. Complex mise settings require updating from the original terminal. Changing the selection does not move or remove another installation or adopt a pip/uv development CLI.

CLI updates are checked at App startup and every 24 hours while running. Checks notify; installation is manual. Automatic checks run in the background without a progress bar. Preferences and timestamps persist independently, and failed checks retain the last success with a retry delay. App updates remain separate in Sparkle / Velopack.

Configuration and Skills survive CLI repair, updates and removal. The npm prefix must be writable; the App does not elevate permissions, edit global npm settings or alter PATH. Add the selected npm global command directory to your terminal PATH when using short commands; Skills use the full invocation. Compatibility follows the protocol version, not matching product versions.

Published npm 0.1.24 and earlier do not contain a compatible independent CLI. Until a compatible release is available, the App explains the limitation and never runs the old wrapper’s Python installer. You can also look for a standalone CLI ZIP on the release page. If no compatible download is available, wait for a new release or select an existing compatible bundle.

Extract the complete standalone ZIP, then choose **Select existing CLI…** in Overview and select `smart-search.exe` (Windows) or `smart-search` (macOS). Keep its runtime files in the same directory. The App verifies its version and protocol before connecting. This option needs no Node/npm; you manage its updates. Moving or removing the directory requires selecting it again.

Skills synced from a manual CLI include its full invocation path and configuration directory, with instructions to replace the bare `smart-search` command. No PATH is changed. In the Agent, use that full invocation with `--version`, then `agent-guide`. Skill file status and actual Agent invocation are separate checks.

### Windows and WSL

The Windows App can also connect to a CLI inside WSL. Both can be installed at the same time; the App connects to one of them, and manages that side's configuration, Skills and activity. Agents running on Windows use the Windows copy, and Agents running in WSL use the WSL copy.

- Running distributions are detected automatically. Stopped distributions are only listed and never started; **Detect WSL** in **Environment details…** starts them to look for the CLI (a cold start takes a few seconds).
- A detected installation appears as "WSL distribution · version" in the same list as Windows installations; select it and choose **Use selected installation**. The App reconnects to the last selected side on later launches, and only reports a problem if that side becomes unavailable instead of switching to the other one.
- With both available and no previous choice, the App connects to Windows. While connected to WSL, Overview shows "WSL distribution".
- A CLI installed with npm in WSL can be updated from the App: use **Update CLI** in Overview for the selected installation, or **Update the CLI in WSL distribution** in **Environment details…** for another one. The App uses the Node.js that runs that CLI and its own npm, and installs into the same directory.
- An environment without the CLI gets **Install in Windows** or **Install in WSL distribution**: in Overview when nothing is installed yet, otherwise under **Environments without the CLI** in **Environment details…**. Installing in WSL needs Node.js 18 or later in that distribution and uses its npm global directory.
- The App never uses `sudo`. When the npm global directory belongs to root (for example Node.js from apt), when mise manages the CLI, or when the App cannot tell how the CLI was installed, it shows the command to run in a WSL terminal instead. Remove a CLI in WSL from a terminal as well.
- The App connects to a CLI in WSL from version 0.1.29; older versions are shown as needing an update.
- The App finds `smart-search` with a login shell (`bash -lc`), then an interactive shell (`bash -ic`, for nvm), and afterwards starts it directly without a shell or a network connection. While connected to WSL the folder picker cannot change the configuration directory; set `SMART_SEARCH_CONFIG_DIR` in WSL instead.

## Everyday pages

| Page | Use it to |
| --- | --- |
| Overview | Check missing capabilities and the next setup step |
| Providers | Edit, test, preview and save provider settings |
| Search & research | Search, read URLs, map sites, look up docs, plan offline research or run online research; copy/export results |
| Activity | See actual stages, providers, models and elapsed time; cancel tasks started by this App |
| Update Skills | Read Skills from the selected CLI; back up, sync or remove Agent targets |
| Settings & about | Choose the configuration directory, observe additional activity directories, set theme/language, reset health status and check updates |

Search results need source checking. A hit or snippet is a candidate source, not proof that its page was read. See [Search, research and evidence](research.md).

## Language

Use **Settings & about → Language** to select automatic, 简体中文 or English. Automatic uses Chinese for a Chinese system language and English otherwise. The choice is saved for this App. Switching retains unsaved provider drafts and running searches; protected installation or update writes must finish first.

The independent CLI saves its own preference. Changing the App does not change that preference, provider configuration, AI language, queries, answers or source pages. Third-party installation logs may remain in their original language.

For a manual check, switch to English, visit each page, then switch to Chinese and restart the App. Confirm that the choice persists, the draft remains intact, buttons wrap at the minimum window size and keyboard navigation works. Check an invalid local setting and its error as well; no paid request is needed for these checks.

## App and CLI independence

The selected independent CLI provides search, configuration and Skill operations. It remains usable after the App closes or is removed. App updates do not replace the CLI.

Both can share provider settings by selecting the same configuration directory. Windows defaults to `%LOCALAPPDATA%\smart-search`, with the legacy home directory supported. `SMART_SEARCH_CONFIG_DIR` or the App's directory selector can isolate configurations. Different inherited environment variables can still produce different effective settings.

The App manages only its own protocol process. It does not stop CLI tasks started by terminals or Agents.

## Activity, updates and removal

Activity refreshes every two seconds and observes only the current or explicitly added directories. By default it records metadata rather than queries, answers, headers or keys. Completed entries are retained for at most seven days / 1,000 entries by default. Clearing activity does not delete configuration, research evidence or exports. An expired heartbeat means the status is stale, not that the task succeeded.

Closing the window with a running App task offers continuing in the background, cancelling App tasks and exiting, or returning. Restore the background App from its tray/menu icon; launching it again restores the same window. Independent CLI tasks started by a terminal or AI are not cancelled by the App.

In Settings & about, App updates use Velopack on Windows and Sparkle on macOS. When enabled, automatic checks run at each new App process launch; there is no 24-hour polling while it stays open. Restoring an existing window is not a new launch. A new version opens a dialog: on Windows it appears once the App is connected, where **Update now** downloads and restarts the App and **Later** leaves it for this page; on macOS Sparkle shows its prompt to install, remind later or skip the version. Nothing opens when the update feed cannot be reached. Manual checks remain available when automatic checks are disabled. The primary button changes from **Check for updates** to **Download update**, with retry on failure and download progress/cancellation retained. macOS confirmation and installation progress use Sparkle’s native window. Errors are never reported as “up to date”.

The frameworks download, verify and install the App independently, using a delta when applicable and a verified full package as fallback. Before restart, finish App tasks, CLI/environment/Skills writes and handle unsaved drafts. The App never cancels independent CLI tasks. A completed download is not a completed installation; check the actual version after restart.

The first move from an Inno Setup installation requires a full installation: finish writes, close the old App, uninstall its App entry in Windows Settings, run the new official Setup, then use its new shortcut. Detection and the included migration guide do not uninstall anything automatically. On macOS, close the old App and replace it once with the full download. Shared configuration, independent CLI, SmartSearchTools, Agent Skills, research evidence and exports stay in their original locations. Subsequent App updates use the framework.

Windows release signatures remain self-signed. Sparkle uses a separate EdDSA update signature, which is not Apple Developer ID signing or notarization. Local macOS builds default to ad-hoc, CI tests use disposable certificates, and formal candidates require the maintainer's fixed certificate. A candidate without a configured update key disables updates. Unpacked Windows development builds likewise require a full framework install before updates work.

Build and protocol details: [desktop README](../../../desktop/README.md), [desktop protocol](../../../desktop/PROTOCOL.md). Problems: [Troubleshooting](troubleshooting.md).
