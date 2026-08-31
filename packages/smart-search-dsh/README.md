# Smart Search for DeepSeek Harness

`@konbakuyomu/smart-search-dsh` is a separate DeepSeek Harness (DSH) bundle.
It exposes two bounded tools that invoke only the public Smart Search CLI JSON
contract. It does not add DSH dependencies to the core `@konbakuyomu/smart-search`
package.

## Compatibility

This bundle is tested against the developer-preview baseline
`@deepseek-ai/dsh@0.1.1-rc.2` and its matching
`@deepseek-ai/dsh-tools@0.1.1-rc.2` API. DSH is explicitly preview software;
do not treat this as a compatibility promise for later RC, alpha, or stable
releases without rerunning the isolated lifecycle check.

Both DSH packages are exact optional peers: the running Harness supplies them,
so installing this bundle does not add a second DSH runtime to a profile.

## Install

After `@konbakuyomu/smart-search-dsh` has been published to npm, DSH owns
profile creation, the profile `package.json`, bundle order,
`pnpm-workspace.yaml`, and credentials. Until then, use the packed-tarball
command below for local verification.

`dsh plugin` delegates package operations to `pnpm`; make `pnpm >=10`
available before using add, update, or remove. This bundle's
archive declares no install lifecycle script, so it does not add an
`allowBuilds` approval requirement.

Use DSH's public plugin command instead of editing those files yourself:

```sh
dsh plugin --profile web add @konbakuyomu/smart-search-dsh@0.1.0
dsh --profile web --dump-config
```

For a locally packed release candidate, replace the registry spec with the
explicit tarball path:

```sh
dsh plugin --profile web add ./konbakuyomu-smart-search-dsh-0.1.0.tgz
```

The config dump should contain the `smart-search-dsh` row and
`@konbakuyomu/smart-search-dsh` bundle layer. Importing the package does not
create or edit a DSH profile.

## Tools

| Tool | Input | Public CLI call |
| --- | --- | --- |
| `smart_search_search` | required non-empty `query` | `smart-search search QUERY --timeout SECONDS --format json` |
| `smart_search_fetch` | required credential-free absolute HTTP(S) `url` | `smart-search fetch URL --format json` |

The bundle does not expose Smart Search configuration, setup, credential,
provider-selection, research-execution, shell, or arbitrary-command tools.
Smart Search continues to own its own configuration and provider credentials.
DSH credentials are never mapped into Smart Search arguments or configuration.

## Bounds and Errors

The bundle defaults are defined in `cordis.patch.yml`:

```yaml
executable: smart-search
executableArgs: []
timeoutMs: 181000
maxOutputBytes: 262144
```

`executableArgs` is a profile-owned fixed vector for deployment adapters; it is
not tool input. The 181000 ms default preserves Smart Search's 180-second
search budget and reserves one second for JSON serialization. `timeoutMs` must
be from 1000 through 600000, and
`maxOutputBytes` must be from 4096 through 1048576. The process is started with
an argument vector, never a model-provided shell command. On Windows, npm
PowerShell shims are preferred. A `.cmd`-only fallback permits ordinary input
but rejects command-processor metacharacters rather than treating model input
as shell syntax.

Successful tool results are:

```json
{
  "ok": true,
  "command": "search",
  "result": { "ok": true }
}
```

Expected failures return a structured envelope with one of
`SMART_SEARCH_INVALID_INPUT`, `SMART_SEARCH_EXECUTABLE_NOT_FOUND`,
`SMART_SEARCH_TIMEOUT`, `SMART_SEARCH_CANCELLED`,
`SMART_SEARCH_OUTPUT_TOO_LARGE`, `SMART_SEARCH_INVALID_JSON`,
`SMART_SEARCH_UNSUPPORTED_INPUT`, or `SMART_SEARCH_CLI_ERROR`. The bridge keeps byte counts and public CLI JSON
where available, but never forwards raw process stderr into the tool result.

## Update, Remove, and Rollback

```sh
dsh plugin --profile web update @konbakuyomu/smart-search-dsh
dsh plugin --profile web remove @konbakuyomu/smart-search-dsh
dsh --profile web --dump-config
```

To roll back, remove the current bundle and add an exact earlier package or
tarball version with the same DSH command. Do not hand-edit the profile
manifest, profile patch, bundle order, pnpm workspace, or credentials.

## Verification

The local package checks need no Smart Search or provider credential:

```sh
npm test
npm run check:package
```

The isolated lifecycle tool deliberately requires a new work directory and
never removes it. It scrubs secret-like and package-manager configuration
environment variables, disables DSH telemetry, and puts `DSH_HOME`, home,
application-data paths, npm cache, pnpm home, and pnpm store under that
directory. It creates an isolated DSH profile through `dsh plugin`, installs a
packed tarball, dumps the config, invokes a registered tool through a no-secret
mock CLI, removes the bundle, re-adds that exact tarball to exercise rollback,
removes it again, and byte-compares unrelated profile files.

Install DSH only below an ignored local runtime directory, then pass its direct
JavaScript entrypoint rather than a user profile or global shim:

```powershell
$runtime = Join-Path $PWD 'node_modules/.dsh-runtime'
$runtimeStore = Join-Path $runtime '.pnpm-store'
New-Item -ItemType Directory -Path $runtime -ErrorAction Stop | Out-Null
$env:PNPM_STORE_DIR = $runtimeStore
$env:PNPM_CONFIG_STORE_DIR = $runtimeStore
pnpm --dir $runtime init
pnpm --dir $runtime add --ignore-scripts --lockfile=false @deepseek-ai/dsh@0.1.1-rc.2
$entry = Join-Path $runtime 'node_modules/@deepseek-ai/dsh/lib/bin.js'
$work = Join-Path $PWD 'node_modules/.smart-search-dsh-lifecycle-001'
node .\scripts\isolated-profile-lifecycle.mjs --dsh-entry $entry --work-dir $work
```

This is an isolated lifecycle check, not an authorized live-provider smoke.
Run a live Smart Search call only with user-supplied configuration and separate
authorization.

## License

MIT. See [LICENSE](./LICENSE).
