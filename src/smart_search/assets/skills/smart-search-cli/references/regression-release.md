# Regression And Release

## Table of Contents

- Regression
- Smoke matrix
- Release lanes
- Release closeout lessons

## Regression

Run `smart-search regression` before considering CLI or skill changes complete.

- In a source checkout, it runs offline pytest coverage for CLI, service, smoke, provider, and skill contract behavior.
- In npm / mise packaged installs, repository test files are not bundled; since v0.1.8 it falls back to built-in mock smoke regression so users can still verify installed CLI health.
- For release validation, use a source checkout for full pytest-backed regression and use packaged-install regression only as an install-health check.
- Provider architecture changes must be verified as distributable CLI behavior, not as behavior that only works because one developer machine has a specific wrapper, shell profile, or local config file.
- After provider-routing changes, run source-checkout regression plus `smart-search smoke --mock --format json`. If live keys were used, run a targeted secret scan for exact key substrings before committing.

## Smoke Matrix

- Deep Research smoke coverage is mock-full plus live-limited.
- Mock-full coverage should cover trigger phrases, normal search requests that should not trigger Deep Research, required `research_plan` fields, allowed tool whitelist, `fetch_before_claim`, evidence paths, capability boundaries, `intent_signals`, `capability_plan`, `gap_check`, simple current prompts such as `深度搜索一下最近的比特币行情`, docs/API prompts, claim-verification prompts, user-provided URL fetch-first flows, missing-provider failure guidance, research provider advantage routing, same-capability research fallback, and the rule that fixed topic recipe ids are not required schema.
- Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch` when real keys are available and live checks are expected; add one small `research` smoke when configured keys make it stable.
- If a smoke issue is found, fix the affected docs/code/tests and rerun the affected smoke until it passes or is proven to be an external provider blocker.

## Release Lanes

- Stable releases are pushed as `vX.Y.Z` Git tags and publish npm `X.Y.Z` with dist-tag `latest`.
- Test releases are pushed from `main` and publish `<package.json version>-beta.N` with dist-tag `next`. The beta counter resets per base version, so `0.1.9-beta.1` and `0.1.10-beta.1` are separate sequences.
- Stable bump commits must use `chore(release): bump version to X.Y.Z`; the branch push is skipped by the npm workflow so the matching `vX.Y.Z` tag is the only publisher for npm `latest`.
- Stable GitHub release notes should be stored as `.github/releases/vX.Y.Z.md` before tagging. The publish workflow appends npm package, dist-tag, and workflow-run metadata to that body automatically.
- Historical test builds can be backfilled through GitHub Actions `workflow_dispatch` by supplying an explicit `target_ref`, exact `version`, and a non-`latest` npm tag such as `backfill`.
- npm versions are immutable. Old `*-dev.*` packages cannot be renamed in place; publish replacement `*-beta.N` packages and optionally deprecate the old names when npm owner credentials are available.

## Release Closeout Lessons

- Always read back npm before and after publishing with `npm view @konbakuyomu/smart-search versions --json` and `npm view @konbakuyomu/smart-search dist-tags --json`. A test release must leave `latest` on the stable version and move only `next` or the explicitly supplied non-`latest` tag.
- Backfill jobs can publish npm successfully even if GitHub release creation fails because the workflow token cannot access the release API. In that case, leave npm intact and create the missing GitHub prerelease with authenticated local `gh release create ... --prerelease --latest=false`.
- If concurrent backfill jobs hit npm `E409`, re-dispatch only the affected versions serially after checking whether the version already appeared in the registry.
- Finish with a diff-style gap check: expected beta version list minus npm versions equals empty, and expected `vX.Y.Z-beta.N` list minus GitHub prereleases equals empty.
- Local verification after a test release must use an exact install target, such as `mise use -g "npm:@konbakuyomu/smart-search@0.1.10-beta.3" -y --pin`, followed by `mise reshim`, `where.exe smart-search`, `smart-search --version`, packaged `smart-search regression`, and `smart-search smoke --mock --format json`.
- Also pipe a non-ASCII JSON command such as `smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json` to verify the Windows npm/mise wrapper is emitting UTF-8 JSON, not locale-encoded bytes.
