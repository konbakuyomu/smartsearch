# Smart Search desktop protocol v1

Both native clients implement this contract. The Python core owns configuration,
validation, routing and status. Do not open an HTTP listener or invoke a shell.

Launch bundled `backend/smart-search.exe --desktop-backend` on Windows;
`Contents/Resources/backend/smart-search --desktop-backend` in the macOS bundle.
The native UI has no backend-path or timeout setting. Test harnesses may supply an explicit backend path.
The packaged entry accepts private backend/worker switches and `--version`; it rejects public CLI commands and is never exposed through PATH.
Redirect UTF-8 stdin/stdout/stderr; keep the console hidden on Windows. Each stdin
and stdout line is one compact JSON object. stderr is diagnostic, never protocol.

Request: `{"id":1,"method":"initialize","params":{"protocol_version":1}}`.
Response: `{"id":1,"result":{...}}` or
`{"id":1,"error":{"code":"parameter_error","message":"..."}}`.
Events: `{"event":"tick","data":{}}` (lightweight owned-run reconciliation),
`{"event":"run","data":{"run_id":"...","status":"finished","result":{...}}}`.
IDs are positive integers and each request receives one response. Each process has
a new `generation` UUID; discard data from a previous client/process generation.
Methods below return result objects. Ordinary business errors have `ok:false`.

| Method | Parameters | Result |
| --- | --- | --- |
| `ping` | `{}` | `protocol_version`, `version`, `generation` |
| `initialize` | `protocol_version:1`, optional absolute `config_dir`, `app_version`, `lang:auto\|zh\|en`, `enable_update_checks:true` for production native clients | full state below |
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
| `skills.catalog` | `{}` | all Agent targets compared with verified stable Skills or clearly labelled bundled/cache fallback; `source`, `cached`, `targets`, `cli_version`, `compatibility`, `plan_id`, `can_sync` |
| `skills.update` | `confirm:true`, nonempty `targets` | one action: check the stable source, revalidate selected target fingerprints, back up and sync; completion via `skills` event; no separate plan/check required |
| `skills.check` | `{}` | check and cache official npm stable Skills; completion via `skills` event; never writes Agent directories |
| `skills.auto` | `enabled` boolean | persisted daily Skills check preference; no automatic installation |
| `skills.sync` | `confirm:true`, nonempty `targets`, `plan_id` from catalog | explicit backup and sync; completion via `skills` event with `result.installed` (paths and backups) / `result.failed` |
| `activity.list` | optional absolute `directories` array, `limit` 1..1000 | `ok`, `runs`, `errors`, `enabled` |
| `activity.clear` | `{}` | `ok`, clears completed metadata only |
| `activity.enabled` | `enabled` boolean | `ok`, `enabled` |
| `activity.details` | `run_id`, optional absolute `config_dir` | `ok`, `run`, metadata-only `events`, `events_truncated` |
| `cli.status` | `{}` | `external_path`, `external_version`, `external_runtime_verified`, ownership and update eligibility; no bundled command path |
| `environment.prepare` | `confirm:true` | detect and execute a fresh validated CLI installation/repair plan; no Skill targets; completion via `environment` event |
| `environment.status` | `{}` | current environment snapshot without probing or network |
| `environment.check` | `{}` | starts read-only local discovery; completion via `environment` event |
| `environment.verify` | `{}` | starts local Node/independent-engine checks; no repair or provider/AI request |
| `environment.install` | `confirm:true`, `plan_id` from detection, `targets` (`codex`/`claude`), optional `replace_modified:false` | starts the checked plan; completion via `environment` event |
| `environment.cancel` | `{}` | cancels only the cancellable download stage; package-manager writes are not force-cancelled |
| `cli.update-check` | `{}`; explicit manual CLI check | independent CLI update state; completion via `updates` event |
| `updates.state` | `{}` | latest update state (no network) |
| `updates.auto` | `enabled` boolean | persist shared automatic-check preference; native clients synchronize their SDK scheduler |
| `cli.update` | `confirm:true`, exact checked `version` | call only the identified npm/mise manager; terminal event includes actual version and bounded sanitized log |
| `app.update-prepare` | `{}` | reject owned runs or protected writes, then lock requests until `shutdown`; the native SDK installs only after backend shutdown |
| `shutdown` | `{}` | `ok`; cancels own work and exits |

`run.start` accepts the focused test catalog: `search`, `fetch`, `context7-library`,
`context7-docs`, `route`, and `smoke`. Full public CLI functionality is unchanged.
Arguments do not repeat command tokens. Secret configuration mutations use `config.apply`.
`cli.enable` is removed. Legacy metadata/check/sync RPCs remain internal compatibility
interfaces, not separate native UI actions. Each client permits one business test
at a time and places cancellation beside the current test/provider.
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
  `commands` (catalog below). Activity history is not part of normal state refresh.

Catalog entry: `id`, `label`, `description`, `experimental`, `fields`.
Field: `name` (argparse dest), `label`, `help`, `flags` (empty for positional),
`kind` (`text/int/float/bool/choice`), `choices`, `required`, `default`, `multiple`.
Send positionals in catalog order; optional values as flag then value; checked
boolean flags as a standalone flag; repeated values repeat the flag. Do not send
empty optional fields. Forms can show advanced parameters in an expander.
Commands already represented by config/skills/provider UI are not duplicated in
the ordinary tool catalog. CLI compatibility does not require arbitrary shell UI.

Internal activity records (retained for compatibility and external-CLI write exclusion) have fields: `run_id`, `command`, `origin` (`app/cli`), `config_dir`,
`version`, `pid`, `status` (`running/finished/failed/cancelled/stale/interrupted`),
`phase`, `provider`, `model`, `started_at`, `updated_at`, `finished_at`,
`elapsed_ms`, `error_type`, `exit_code`, `sources_count`, `sequence`, `config_revision`.
Timestamps are Unix seconds. The native configurator has no activity workspace;
owned-run events and lightweight ticks update local progress and cancellation.
No request arguments, query, content, headers or credentials are in the journal.
`config_revision` in an activity row is an opaque identifier for that invocation's
frozen snapshot, not a hash of secret values or the optimistic-save revision.

Editing rules: empty untouched or erased secret input means KEEP; an explicit
Clear control adds the key to `unset`; entering a replacement adds `set[key]`.
Read-only environment fields show the masked effective value and its source.
Save sends the displayed revision; conflicts keep the draft and offer refresh.

Native UI destinations: Configuration (default), Test, CLI & Skills, Settings. Use native controls/theme/keyboard/focus.
Current results render readable content and sources, with JSON in an advanced
expander and explicit copy/export. Never make raw JSON the primary UI.
Business `result.display_text` reuses the existing CLI Markdown formatter, keeping
plans, lists, diagnostics and sources readable without a second native formatter.
This additive desktop-only field is not added to public CLI JSON output.
Close with own active work offers background/stop-and-quit/return. Background
has a tray/menu-bar entry. Never terminate external CLI processes.

The backend update state contains the shared automatic-check preference, independent
CLI metadata and `cli_update` status. `app` reports only the current bundled identity
with `managed_by: "native"`; historical App download caches are not restored.
Only npm CLI metadata is fetched by this module. CLI/Skills checks retain their
production handshake opt-in and daily throttle.

Velopack (Windows) and Sparkle (macOS) own App metadata, downloads, integrity checks,
full/delta packages and installation. Their native state is not fabricated by the
Python backend. Both keep automatic downloads disabled and honor the saved
`updates.auto` preference. There is no second App downloader in this protocol.

Native clients protect unsaved drafts and UI operations before requesting
`app.update-prepare`. The backend rejects active owned runs, environment work,
CLI upgrades and Skills writes; after success it rejects every request except
`shutdown`. Clients stop the backend before allowing the SDK to replace the App.
If the SDK cannot apply the update, the client reconnects a fresh backend. No
external CLI process is killed or relocated. Normal shutdown remains available.

`cli.status` and full refresh re-resolve the effective entry. Ownership fields
include `manager/manager_label/can_update/resolved_path/update_note`; unknown,
project, ambiguous, or unsupported constrained installations remain manual.
CLI updates use the original manager with an exact checked version, no shell or
bulk upgrade. The frontends prevent quit/reconnect during the manager operation;
no forced cancellation or rollback is promised. Readback must confirm the target
effective version and private Python runtime before `cli_update.status` becomes
`finished`. If the manager skipped lifecycle scripts, the explicit update prepares
the verified target package's private venv and installs its bundled Python project,
using the same commands as environment setup. Source/manager changes refuse this
step; ordinary discovery never initializes a runtime. Fresh metadata can enable a
same-version retry when `cli.runtime_needs_repair` is true. Installer failures retain
their logs and do not count as successful updates. CLI cards explain cached results
and incomplete runtimes next to the action.

Environment snapshots/events contain `status`, `busy`, `can_cancel`, `message`,
`error`, bounded sanitized `log`, `steps`, `node`, `python`, `cli`, `targets`,
`plan`, `plan_id`, `can_install`, `blocked`, `checked_at`, `tools_dir`, `config_dir`
and a shell-quoted `invocation` for the user's AI test instructions. Download
stages add actual `received`/`total` bytes. `ready` means the operation ended;
each step and target must still be inspected. It never means an AI has invoked
the skill. Files, installed AI commands, local engine execution and provider
configuration are distinct facts. Checks do not run legacy auto-repair wrappers.

New runtimes and the npm prefix live in `%LOCALAPPDATA%/SmartSearchTools` or
`~/.local/share/smart-search-tools`, outside the App bundle. Their manifest stores
only independent paths, not secrets. AI skills invoke that independent Node/npm
installation with absolute paths; no App executable or running App is required.
Windows publishes only the new installation's user PATH entries and preserves
existing entries; already running clients require a refreshed environment. A
sibling node.exe makes the npm shim independent of another Node earlier in PATH.
macOS GUI clients use the absolute invocation without modifying shell profiles.

Codex user skills use `.agents/skills`, with `.codex/skills` reported as a legacy
location; Claude uses `.claude/skills` or its explicit `CLAUDE_CONFIG_DIR`. Changed
skill files are kept unless replacement was explicitly chosen; replacement first
backs up the old tree and preserves extra files. Installation is checked again
against `plan_id` before mutation. Environment writes exclude competing CLI/App
updates, skills writes and profile switching; clients keep the operation busy
across page changes and guard exit/reconnect until its actual terminal event.

## Agent Skills updates

Skills state has `auto_check`, `last_attempt`, `checking`, `busy`, `source`
(`version`, `checked_at`, `integrity`, `url`), `cached`, `error`, all `targets`,
`cli_version`, `cli_ready`, `compatibility`, `plan_id`, `can_sync`, and `result`.
Automatic checks use the production handshake opt-in and the independent daily
Skills preference. They download only official npm data, with SHA512 and bounded
archive validation; no lifecycle script or package code runs. A failed check keeps
old installations and labels previous data as cached. The single `skills.update` action performs its own fresh successful check before writing. Package versions do not determine Skill content changes or
block sync when the CLI is older or unverified. CLI readiness is informational;
unverified local invocation notes are preserved, not regenerated.
The confirmed fingerprint is rechecked against the current source, target files
and CLI invocation. Skills writes exclude environment/CLI updates, language and
profile changes; closing waits for the writer. Existing `skills.status/install`
remain compatible bundled-source APIs; native clients use the new stable-source
`skills.update` and `environment.prepare` actions; CLI preparation writes no Skills.

Every target uses the shared registry/path resolver, including Cline and Roo Code.
Managed local invocation notes are composed consistently and recognized by the
generic CLI comparator. Explicit sync backs up changed trees, atomically replaces
files, preserves extras and refuses linked paths. Each target includes
`needs_update`, `content_stale_files` and `invocation_changed`. Clients enable the update action whenever at least one target is selected and no
conflicting operation is running. `can_sync`, cached source state and `needs_update`
do not gate selection. Unchanged targets report up to date without writes or backups.
`stale` means content or local invocation details differ,
not an Agent software version or proof that its Skill is loaded. Clients keep
selection across refresh and completion, and show errors and backup paths inline.
Agent reload and actual invocation remain separate from file synchronization.

## Interface language

Native clients resolve their independent App preference and pass `lang` at initialize.
Legacy protocol v1 clients omitting it keep Chinese presentation. State includes the
resolved `language`. `language.set` refreshes local metadata without reconnecting,
restarting tasks, changing CLI preferences or making provider requests. Subsequent
status events render owned message templates in the current App language. Completed
results and task input snapshots retain their original contents. JSON keys, status
codes, provider/model IDs and upstream/user content remain unchanged. Raw third-party
errors are redacted but not translated by matching their text against a dictionary.
