# Smart Search desktop protocol v1

Both native clients implement this contract. The Python core owns configuration,
validation, routing and status. Do not open an HTTP listener or invoke a shell.

Launch the user-selected independent CLI with `--desktop-backend`. For npm installations, use the identified Node executable and package wrapper with that argument. Probe `--desktop-capabilities` for `product:smart-search` and `desktop_protocol_version:1` first. Product versions need not match. Its `launch_command` is the argv that starts the same CLI without a shell (the npm Node and wrapper, a frozen executable, or Python with `-m smart_search.cli`); the Windows App uses it for a CLI inside WSL as `wsl.exe -d <distro> --cd ~ --exec <launch_command…> --desktop-backend`. The native App contains no CLI or Python runtime. An explicitly selected development path may override discovery.
Redirect UTF-8 stdin/stdout/stderr; keep the console hidden on Windows. Each stdin
and stdout line is one compact JSON object. stderr is diagnostic, never protocol.

Request: `{"id":1,"method":"initialize","params":{"protocol_version":1}}`.
Response: `{"id":1,"result":{...}}` or
`{"id":1,"error":{"code":"parameter_error","message":"..."}}`.
Events: `{"event":"activity","data":{...}}`,
`{"event":"run","data":{"run_id":"...","status":"finished","result":{...}}}`.
IDs are positive integers and each request receives one response. Each process has
a new `generation` UUID; discard data from a previous client/process generation.
Methods below return result objects. Ordinary business errors have `ok:false`.

| Method | Parameters | Result |
| --- | --- | --- |
| `ping` | `{}` | `protocol_version`, `version`, `generation` |
| `initialize` | `protocol_version:1`, optional absolute `config_dir`, `app_version`, `lang:auto\|zh\|en`, `independent_cli:true`, `enable_update_checks:false` for native clients | full state below |
| `language.set` | `lang:auto\|zh\|en` | refreshed state; refuses changes during environment writes or CLI updates |
| `get_state` | `{}` | full state, local/read-only |
| `profile.select` | absolute `config_dir` | full state |
| `config.preview` | `set` object, `unset` key array | `ok`, `minimum_profile_ok`, `missing`, `capability_status` |
| `config.apply` | `set`, `unset`, `revision` from state | `ok`, `error`, `error_type`, refreshed `status` |
| `provider.test` | `provider`, `overrides` containing ONLY actual edited values (not masked placeholders) | `ok`, `run_id`; completion via run event/result |
| `run.start` | `command` catalog id, `arguments` string array (arguments following the command) | `ok`, `run_id` |
| `run.cancel` | `run_id` owned by this backend | `ok`, `status:"cancelling"`; wait for terminal event |
| `run.result` | `run_id` | `ok`, `run_id`, `status`, `result` or null |
| `providers.reset` | optional `providers` id array | `ok`, `cleared` |
| `skills.status` | optional `targets` id array | `ok`, `targets` array |
| `skills.install` | nonempty `targets` array | `ok`, `run_id` |
| `skills.catalog` | `{}` | all Agent targets compared with the selected CLI’s local Skill source; `source`, `cached`, `targets`, `cli_version`, `compatibility`, `plan_id`, `can_sync` |
| `skills.check` | `{}` | refresh the current CLI source and local target state; never downloads an independent Skill source |
| `skills.auto` | `enabled` boolean | persisted CLI-owned maintenance preference for connected targets |
| `skills.sync` | `confirm:true`, nonempty `targets`, `plan_id` from catalog | explicit backup and sync; completion via `skills` event with `result.installed` (paths and backups) / `result.failed` |
| `skills.remove` | `confirm:true`, nonempty `targets` | back up selected directories, remove maintenance receipts; `result.removed` / `result.failed` |
| `activity.list` | optional absolute `directories` array, `limit` 1..1000 | `ok`, `runs`, `errors`, `enabled` |
| `activity.clear` | `{}` | `ok`, clears completed metadata only |
| `activity.enabled` | `enabled` boolean | `ok`, `enabled` |
| `activity.details` | `run_id`, optional absolute `config_dir` | `ok`, `run`, metadata-only `events`, `events_truncated` |
| `cli.status` | `{}` | current CLI identity and protocol, without discovering another CLI when `independent_cli:true` |
| `cli.enable` | `confirm:true`, sent only by explicit user action | `ok`, `path`, `message`; refuses command conflicts |
| `environment.status` | `{}` | current environment snapshot without probing or network |
| `environment.check` | `{}` | starts read-only local discovery; completion via `environment` event |
| `environment.verify` | `{}` | starts local Node/independent-engine checks; no repair or provider/AI request |
| `environment.install` | `confirm:true`, `plan_id` from detection, `targets` (`codex`/`claude`), optional `replace_modified:false` | starts the checked plan; completion via `environment` event |
| `environment.cancel` | `{}` | cancels only the cancellable download stage; package-manager writes are not force-cancelled |
| `cli.update-check` | `{}`; explicit manual CLI check | independent CLI update state; completion via `updates` event |
| `updates.state` | `{}` | latest update state (no network) |
| `updates.auto` | `enabled` boolean | legacy CLI check preference; never controls the App SDK scheduler |
| `cli.update` | `confirm:true`, exact checked `version` | call only the identified npm/mise manager; terminal event includes actual version and bounded sanitized log |
| `app.update-prepare` | `{}` | reject owned runs or protected writes, then lock requests until `shutdown`; the native SDK installs only after backend shutdown |
| `shutdown` | `{}` | `ok`; cancels own work and exits |

`run.start` catalog identifiers can include subcommands, e.g.
`model/current`. `diagnose` selects its provider via its catalog fields. Arguments do not repeat command
tokens. A secret configuration mutation uses `config.apply`, not CLI arguments.
`provider.test` tests a snapshot of the effective configuration at click time,
merged with any actual edits. No configuration or health changes are persisted.
Its completion scope is `current` when overrides are empty and `draft` when edits
are supplied. UI labels say “测试” or “用未保存的修改测试” accordingly.

Full state extends `smart_search.ui_api.state()`:

- `ok`, `values` (masked effective values), `saved_values` (masked file values),
  `sources` (`environment/config_file/default`), `revision`, `config_path`;
- `minimum_profile` (`ok/required/missing`), `capability_status`,
  `capability_chains`, `provider_health`, `provider_profiles`, `probe_kinds`;
- `provider_checks`: last in-memory test per provider for this App session, with
  `status/checked_at/source/scope/probe/message`. Scope is `current` or `draft`, and a draft
  test must never be described as a verified saved configuration. No entry means
  not tested during this session; cooldown `closed` alone is not a successful probe.
- `metadata.fields`: key, section, tier, kind, label_zh/en, help_zh/en, default, placeholder,
  choices, provider, capabilities, key_url, docs_url; sections include
  getting_started, providers, routing, reliability, diagnostics. Consume
  `metadata.sections` order, label_zh/en and blurb_zh/en instead of alphabetic ordering;
- `skill_targets`: id, label, default;
- `protocol_version:1`, `version`, `generation`, `config_dir`, `cli`, `updates`, `environment`, `skills`,
  `commands` (catalog below), `activity` (activity.list result).

Catalog entry: `id`, `label`, `description`, `experimental`, `fields`.
Field: `name` (argparse dest), `label`, `help`, `flags` (empty for positional),
`kind` (`text/int/float/bool/choice`), `choices`, `required`, `default`, `multiple`.
Send positionals in catalog order; optional values as flag then value; checked
boolean flags as a standalone flag; repeated values repeat the flag. Do not send
empty optional fields. Forms can show advanced parameters in an expander.
Commands already represented by config/skills/provider UI are not duplicated in
the ordinary tool catalog. CLI compatibility does not require arbitrary shell UI.

Activity run fields: `run_id`, `command`, `origin` (`app/cli`), `config_dir`,
`version`, `pid`, `status` (`running/finished/failed/cancelled/stale/interrupted`),
`phase`, `provider`, `model`, `started_at`, `updated_at`, `finished_at`,
`elapsed_ms`, `error_type`, `exit_code`, `sources_count`, `sequence`, `config_revision`.
Timestamps are Unix seconds. Live rows update at least every two seconds when
events arrive; duration may tick locally, but never fabricate percent complete.
No request arguments, query, content, headers or credentials are in the journal.
`config_revision` in an activity row is an opaque identifier for that invocation's
frozen snapshot, not a hash of secret values or the optimistic-save revision.

Editing rules: empty untouched or erased secret input means KEEP; an explicit
Clear control adds the key to `unset`; entering a replacement adds `set[key]`.
Read-only environment fields show the masked effective value and its source.
Save sends the displayed revision; conflicts keep the draft and offer refresh.

Native UI destinations: Overview, Providers, Search & Research, Activity,
Update Skills, Settings & About. Use native controls/theme/keyboard/focus.
Current results render readable content and sources, with JSON in an advanced
expander and explicit copy/export. Never make raw JSON the primary UI.
Business `result.display_text` reuses the existing CLI Markdown formatter, keeping
plans, lists, diagnostics and sources readable without a second native formatter.
This additive desktop-only field is not added to public CLI JSON output.
Close with own active work offers background/stop-and-quit/return. Background
has a tray/menu-bar entry. Never terminate external CLI processes.

The native App owns its update settings and scheduler. Sparkle / Velopack check once per launch while enabled. Automatic downloads remain off. Only macOS (Sparkle) can skip a version; the skip persists across launches and manual checks can reveal it again. Windows offers only “Update now” and “Later”. App update checks and prompts do not require a CLI connection.

Native clients protect unsaved drafts, owned tasks and protected writes before installation. If connected, request `app.update-prepare` and stop the App-owned protocol process; if disconnected, the SDK can still update the App. No external CLI process is terminated and no CLI installation is replaced by an App update.

## Independent CLI management

The App's Swift / C# installation manager runs outside this protocol. It discovers the user's npm or accepts a manual npm path, binds its Node executable and original global prefix, and manages only that npm installation. Invalid explicit paths do not fall back to another environment. Install, repair, update and removal invoke npm directly, without a working CLI or Python dependency. The npm platform package supplies its own runtime; the App verifies the installed CLI version and protocol before connecting. The App never downloads Node/Python, elevates permissions or changes PATH/npm settings. Configuration and Skills survive CLI removal and App removal.

Native clients check npm latest at startup and every 24 hours while enabled. CLI preferences, timestamps and environment identity are independent of App updates; failed checks retain the last successful result and defer retries. Only versions declaring self-contained platform packages are offered for installation.

`cli.enable`, `cli.update*`, `updates.*` and `environment.*` remain compatibility APIs for older clients. Current native clients do not call them to manage installations or App updates. `cli.enable` rejects independent mode.

## Agent Skills updates

Skills state has `auto_check`, `last_attempt`, `checking`, `busy`, `source` (`version`, `managed_by:cli`), `error`, `targets`, `cli_version`, `cli_ready`, `plan_id`, `can_sync`, `result` and `maintenance`.

Catalog, source bytes, target paths, comparison, writes, backups and removal are owned by the selected CLI. The installed short Skill entry calls `smart-search agent-guide [relative-path]` to read that CLI's current documentation. Explicit sync rechecks `plan_id` and registers the selected target for automatic maintenance. Removal moves files to a backup and unregisters the target.

Automatic maintenance checks during normal CLI use, immediately after a CLI version change and daily thereafter. It needs neither a running App nor a network request. Receipts bind each target to its original CLI installation and config directory, and retain hashes of installed files. Personal edits, missing files and unregistered targets are preserved. Process locks serialize receipt and target writes; disabling maintenance persists across App/CLI restarts. Metadata probes and `skills status` stay read-only.

Every target uses the shared registry/path resolver, including Cline and Roo Code.
Managed local invocation notes are composed consistently and recognized by the
generic CLI comparator. Explicit sync backs up changed trees, atomically replaces
files, preserves extras and refuses linked paths. Each target includes
`needs_update`, `content_stale_files` and `invocation_changed`. Clients enable sync
only when a selected target needs an update; unchanged targets are a no-op.
`stale` means content or local invocation details differ,
not an Agent software version or proof that its Skill is loaded. Clients keep
selection across refresh, show changed filenames and backup paths, and instruct
users to reload the Agent before testing real invocation.

## Interface language

Native clients resolve their independent App preference and pass `lang` at initialize.
Legacy protocol v1 clients omitting it keep Chinese presentation. State includes the
resolved `language`. `language.set` refreshes local metadata without reconnecting,
restarting tasks, changing CLI preferences or making provider requests. Subsequent
status events render owned message templates in the current App language. Completed
results and task input snapshots retain their original contents. JSON keys, status
codes, provider/model IDs and upstream/user content remain unchanged. Raw third-party
errors are redacted but not translated by matching their text against a dictionary.
