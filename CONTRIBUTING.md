# Contributing

[中文](#中文)

Thank you for helping. Smart Search routes one question across many search, fetch and model providers, so a change in one place often shows up somewhere else. These rules keep that manageable.

## Every pull request

- Run the **full** test suite, not a subset: `mise run test` (or `python -m pytest -q` in your virtualenv). Also run `mise run parity` (`node npm/scripts/check-skill-parity.js`) when you touch `skills/`, and `python scripts/generate_references.py` when you add commands or configuration keys (the guide's reference pages are generated and tested).
- New user-facing messages go through `source_message(...)` and need a Chinese and English pair in `src/smart_search/assets/i18n/messages.json` (the macOS copy must stay byte-identical).
- Configuration keys must be registered in `Config._CONFIG_KEYS` and described in `ui_metadata.py`, otherwise the App and the local settings page cannot save them.
- Changes under `src/`, `desktop/`, `npm/` or `packages/` must update `codestable/spec/` or add a short record in `codestable/issues/` saying how the current spec is affected. The pre-commit hook (`git config core.hooksPath .githooks`) checks this.
- Keep one topic per pull request. Large changes that mix unrelated fixes are hard to verify and may be split or re-done by maintainers.

## Adding a provider you work for

We welcome providers contributed by the people who build them. Because the project recommends nothing by default, these pull requests must meet extra conditions. Maintainers apply them to every vendor equally.

1. **Disclose.** State in the pull request how you relate to the provider (employee, founder, partner) and whether the change was prepared with AI assistance.
2. **Bring your own key, off until configured.** The provider runs only after the user sets its key, and it has a `*_ENABLED` switch. With no user credential, `_provider_configured()` returns false, and `providers status`, `doctor` and the UI must not show it as configured. No vendor-specific entry points, default recommendations or fixed places in the UI.
3. **Last in line.** Append the provider to the end of each capability it serves, so `PROVIDER_PROFILES`, `RESEARCH_PROFILE_ORDER`, the fetch fallback and the capability status all list the same order. Jev may still choose any configured provider by its description; do not claim it is never chosen first.
4. **Neutral description.** The entries in `provider_descriptions.py` are what Jev uses to choose channels. Say what the provider does and what it does not do, the way existing entries do. No marketing words such as "best", "verified" or "most accurate".
5. **Complete wiring.** Diagnostics: a `doctor` and `providers test` probe that covers every declared capability. Network: respect `ssl_verify`, and do not follow redirects on requests that carry credentials. Tests: missing key, 401, 429, 5xx, timeout, malformed responses and secret redaction. Docs: the README provider tables (English and Chinese), the configuration guide, both copies of the skill references, and a `codestable/` record.
6. **Let maintainers verify it.** Provide a free tier or a temporary test key that covers every declared capability. The key is never committed or used in CI. Until a maintainer has run it against the live service and recorded the date and result, the provider is marked `experimental`.
7. **Keyless or anonymous endpoints** are offered only as an explicitly named command that sends just the typed query after the user confirms each call. They are never listed as configured and never join automatic routing.
8. **Maintenance.** Name a contact for API changes. If the upstream API breaks, shuts down or stays unusable for 30 days without a fix, maintainers may mark the provider experimental, take it out of the fallback chains, or remove it.

The reasoning behind these rules is in `.agents/notes/implemented/process/2026-11-24-vendor-provider-contributions.md`.

---

## 中文

谢谢参与。Smart Search 把一个问题分派给许多搜索、抓取和模型服务商，一处改动常常在别处冒出来，所以有下面这些规矩。

### 每个 PR

- 跑**全量**测试 `mise run test`（或在虚拟环境里 `python -m pytest -q`），不要只挑几个文件。改了 `skills/` 跑 `mise run parity`（即 `node npm/scripts/check-skill-parity.js`）；加了命令或配置键跑 `python scripts/generate_references.py`（指南的参考页是生成的，有测试校验）。
- 面向用户的新文字用 `source_message(...)`，并在 `src/smart_search/assets/i18n/messages.json` 补中英两条（macOS 那份副本必须逐字节一致）。
- 配置键要登记进 `Config._CONFIG_KEYS`，并在 `ui_metadata.py` 里描述，否则 App 和本地配置页存不进去。
- 改了 `src/`、`desktop/`、`npm/`、`packages/`，要同时更新 `codestable/spec/`，或者在 `codestable/issues/` 留一条短记录写明对现状规格的影响。pre-commit（`git config core.hooksPath .githooks`）会检查。
- 一个 PR 只做一件事。把几件不相干的修复混在一起很难验证，维护者可能会拆开或重做。

### 提交你所在公司的服务商

欢迎服务商的开发者自己来接入。因为项目默认不推荐任何一家，这类 PR 要多满足几条，维护者对每家一视同仁：

1. **披露关系**：PR 里写明你和服务商的关系（员工、创始人、合作方），以及是否借助 AI 准备。
2. **用户自带 key，没配置就不启用**：用户设了 key 才会调用，并且有 `*_ENABLED` 开关。没有用户凭据时 `_provider_configured()` 返回 false，`providers status`、`doctor` 和界面都不能显示为已配置。不接受专属入口、默认推荐或界面上的固定位置。
3. **排在最后**：接在所属能力回退链的末尾，`PROVIDER_PROFILES`、`RESEARCH_PROFILE_ORDER`、抓取回退和能力状态里的顺序要一致。Jev 仍会按描述在已配置的服务商里挑选，文档不能说它永远不会被首选。
4. **描述中立**：`provider_descriptions.py` 是 Jev 选路的依据，要像现有条目那样写清擅长什么、不适合什么，不写「最好」「已核验」「最准确」之类的词。
5. **接线完整**：
   - 诊断：`doctor` 和 `providers test` 的探针要覆盖声明的每项能力；
   - 网络：遵守 `ssl_verify`，带凭据的请求不跟随重定向；
   - 测试：覆盖缺 key、401、429、5xx、超时、响应格式不对、密钥脱敏；
   - 文档：中英 README 服务商表、配置指南、技能参考的两份副本，外加 `codestable/` 记录。
6. **让维护者能实测**：提供免费额度或临时测试 key，要覆盖声明的全部能力；key 不进仓库，也不进 CI。维护者实测过、记下日期和结果之前，标为 `experimental`。
7. **免 key 或匿名端点**只能做成按名显式调用的命令：每次经用户确认，只发送本次输入的查询，不显示为已配置，也不进入自动选路。
8. **维护**：留一个接口变更的联系人。上游接口坏了、停服，或者 30 天不可用又没人修，维护者可以把它降为实验性、移出回退链或删除。

为什么这样定，见 `.agents/notes/implemented/process/2026-11-24-vendor-provider-contributions.md`。
