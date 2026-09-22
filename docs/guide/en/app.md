[Guide](../README.md) · [简体中文](../zh-CN/app.md)

# Set up and use the App

The App configures and tests services and installs CLI/Skills. Everyday requests use the independent CLI. These steps describe the four-page configurator in the current source; older releases may show the previous pages.

## Install and open

Download the package for your operating system and architecture from [Releases](https://github.com/konbakuyomu/smartsearch/releases/latest). Windows installs for the current user. The App includes its own runtime; using the App does not require a separate Python, Node.js, or CLI installation.

Environment preparation and full App/CLI language switching are available from v0.1.21; the Update Skills page is available from v0.1.22. Windows self-signing and the new transparent icon are available from v0.1.23. Windows `-signed.exe` packages use a self-signed certificate that Windows does not trust by default, so SmartScreen may still appear. Check the official release source and [public certificate fingerprint](../../windows-signing.md), then decide whether to use the options allowed by your system. This does not permanently trust the certificate or require disabling security protection. Older `-unsigned-test.exe` packages remain unsigned; older macOS packages use ad-hoc signing; after maintainer setup, new packages use a fixed self-signed identity, without Developer ID or notarization. See [macOS signing](../../macos-signing.md). Complete macOS/Windows ARM64 device use, clean-machine operation and the DPI matrix still require manual validation.

Version 0.1.24 introduces the first official Velopack/Sparkle update feeds and the refreshed native interface. For older installations that cannot update, see [troubleshooting](troubleshooting.md#app-update-failed-or-is-unavailable). This first framework release provides complete update packages; later releases can add deltas against its verified baseline.

Open **Smart Search** from the Start menu or Applications. Configuration opens by default and reuses your existing settings.

### macOS installation and first launch

1. Choose a Mac installer from the release download table. The universal version supports both Apple Silicon and Intel.
2. Open the DMG, drag **Smart Search** to **Applications**, and wait for the copy to finish.
3. Double-click **Smart Search** in Applications once to attempt the first launch.
4. If macOS cannot verify the developer or check the app, confirm it came from this project's release page. Open **Apple menu → System Settings → Privacy & Security**, scroll to Security, and click **Open Anyway** beside the Smart Search message.
5. Authenticate if requested, then click **Open** in the confirmation dialog. macOS remembers the exception for this app; future launches can use Applications directly.

If Open Anyway is missing, try launching the app again before returning to Settings. Organization-managed Macs may restrict this setting. See [Apple's first-launch instructions](https://support.apple.com/en-us/102445). For a damaged-app or will-damage-your-computer warning, first check the source, integrity and signature using the [macOS troubleshooting guide](troubleshooting.md#macos-says-the-app-is-damaged-or-the-developer-cannot-be-verified), rather than treating it as an unidentified-developer warning.

## Configure services

1. In **Configuration**, select a provider and enter its address, API key and model. Official documentation and key registration links remain available; see [Providers and configuration](configuration.md).
2. Test the current values or unsaved draft when needed, then preview and save. Testing does not save the draft. Cancel a running test where you started it.
3. In **Test**, choose search, page reading, Context7 library/docs, route preview or offline smoke, then read, copy or export the result.

Provider and online tests may use paid quota; opening the App does not run them. Drafts remain unsaved until you save. Use the key-clearing control and save to remove a key. Environment-provided fields are read-only. Page changes, language changes and state refresh preserve drafts.

## Install the independent CLI and Skills

1. Open **CLI & Skills**. Select **Install CLI** or **Repair CLI** when needed. The App checks ownership, reuses healthy components, prepares missing dependencies and verifies the actual version.
2. Select Agents and choose **Install/update selected Skills**. No separate check or refresh is required. Selecting any target enables submission when no conflicting operation is running.
3. The action fetches and validates Skill files from the latest official stable npm package, backs up changed content and syncs selected targets. Matching files report **Selected Skills are up to date** without rewriting. A failed check keeps existing files; retry with the same button.
4. Reopen the Agent session; Gemini supports `/skills reload`. Ask the Agent to run `smart-search --version`, then test a search when needed.

Checkboxes select targets for this operation. Clearing them does not uninstall files. Extra files, unselected targets and legacy copies remain; results show backup paths. Background checks only notify. App/CLI upgrades do not automatically sync Skills.

New CLI components live in `%LOCALAPPDATA%/SmartSearchTools` or `~/.local/share/smart-search-tools`, outside the App. Existing npm/mise installations keep their manager. Unknown or conflicting sources report the reason instead of creating another copy. Failed installs keep completed components and allow retry. Only downloads can be cancelled; package-manager writes must finish.

CLI versions and Skill contents are checked separately. An unverified CLI does not block Skill content sync, but prepare it before real calls. Existing invocation notes are kept while unverified; a verified independent invocation is included in the Skill. Matching files do not prove the Agent loaded or successfully invoked them.

Registered targets include Codex, Claude Code, Cursor, Copilot, Gemini, OpenCode, Cline and Roo Code. Codex uses `~/.agents/skills/smart-search-cli`, which other compatible Agents may also read; old `.codex/skills` copies remain. Claude respects an absolute `CLAUDE_CONFIG_DIR`; OpenCode uses `~/.config/opencode/skills`. WSL, remote hosts and Cloud Agents need their own setup.

## Four pages

| Page | Purpose |
| --- | --- |
| Configuration | Edit providers and routing, test drafts, preview and save |
| Test | Verify configuration with a request, cancel it, read and export results |
| CLI & Skills | Install/repair/update the independent CLI; select and install/update Agent Skills |
| Settings | Language, appearance, configuration directory, App updates and about |

The full search and research interface remains in the [CLI](cli.md). Check important claims against source pages; see [Search, research and evidence](research.md).

## Settings and updates

Choose system language, 简体中文 or English in **Settings**. The App and CLI save separate language preferences. Switching preserves drafts and running tests; protected writes must finish first. Changing configuration directories protects drafts, and a custom directory offers a restore-default action.

Use the single App update action in Settings to check, update or retry. Velopack on Windows and Sparkle on macOS handle downloads, validation, installation and delta/full fallback. Save or discard drafts and finish current operations before restart. A completed download is not a completed installation. Test builds without updates link to the release installer.

App updates do not replace the independent CLI. CLI checks/updates remain in **CLI & Skills**, update only Smart Search through its identified manager and verify actual execution before reporting completion. Offline and signature failures never report up to date.

## App and CLI independence

The private App process is only for configuration, testing and installation management. It cannot execute public CLI searches and is never added to PATH. Terminals and Agents use the independent CLI after the App closes, updates or is uninstalled.

Both can share provider settings by selecting the same configuration directory. Windows defaults to `%LOCALAPPDATA%\smart-search`, with the legacy home directory supported. Use `SMART_SEARCH_CONFIG_DIR` or the App selector for isolated configuration. Different inherited environment variables can still change effective values.

Closing a window with active App work offers background continuation, cancelling owned tasks and quitting, or returning. Restore it from the tray/menu icon. The App does not kill CLI processes started by terminals or Agents. Uninstalling the App does not remove shared configuration, independent CLI, Skills, research evidence or exported files.

Build and protocol details: [desktop README](../../../desktop/README.md), [desktop protocol](../../../desktop/PROTOCOL.md). Installation, signature and older-version update issues: [Troubleshooting](troubleshooting.md).
