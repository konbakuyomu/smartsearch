# smart-search

面向 AI 与命令行用户的搜索、网页抓取和研究工具：Python 核心在 `src/smart_search`，npm 入口在 `npm/`，Windows 与 macOS 桌面 App 在 `desktop/`，DSH 包在 `packages/`。产品定位见 `PRODUCT.md`，桌面设计见 `DESIGN.md`，App 与 CLI 的边界见 `docs/app-cli-boundary.md`，桌面协议见 `desktop/PROTOCOL.md`。命令和依赖以 `package.json`、`pyproject.toml`、`mise.toml` 为准，发版说明在 `.github/releases/`。

<!-- knowledge-sync:start -->
## CodeStable 与知识同步

- 入口是 `/cs`。小改走快改并留下 `ff`；纯格式、错别字、依赖版本号这类改动视为"不要痕迹"，不留 `ff`。
- 现状规格就是 `codestable/spec/`，不另建 ARCHITECTURE.md、GLOSSARY.md；统一语言写在 `codestable/spec/index.md` 和各子层的入口页。
- 决定（为什么这样选、否掉了什么）写 `.agents/notes/`，格式按 write-notes-like-deepseek，提交前跑 verify；Issue 的方案一节链接过去。`codestable/notes/` 只放坑点和操作经验。
- 结构路径在 `.arch-check.json`。改了这些目录，同一次提交必须改 `codestable/spec/` 或 `.agents/notes/`，或者在本次 `ff` / Issue 的「codestable」一栏写明影响；pre-commit 会检查，被拒绝时按提示补，不要绕过。
- `/cs` 的技能文件不在仓里，因为上游没有许可证：会话开始时 `.githooks/ensure-cs.mjs` 按固定提交把它取到 .claude/skills/cs，云端会话自动装，本地缺了就运行它并加 --install。技能列表里没有 cs 时，直接读 .claude/skills/cs/SKILL.md。
- 关闭 Issue 或 `ff` 落盘并提交成功后，在仓库目录运行 `board log "<一句话进展>"`。云端会话经 winhand 到 Windows 的检出里运行，加 --evidence 和 PR 链接；没有 winhand 就把这句进展写进 PR 描述。
<!-- knowledge-sync:end -->

## 历史与边界

- 2026-10-31 起本仓试点 CodeStable-Lite 做入口，为期两周；为什么这样选、怎么验收见 `.agents/notes/proposed/process/2026-10-31-codestable-lite-pilot.md`。
- `.comet/config.yaml` 是以前 Comet 工作流的配置，不路由新工作。v0.1.18 删掉的带点目录 `.trellis/`、`.codestable/` 属于旧工作流，不要恢复；现在的 `codestable/`（不带点）是 Lite 的。
- `codestable/`、`.githooks/`、`.claude/settings.json`、`.agents/notes/` 只在仓里，不进 npm 包（`package.json` 的 `files` 白名单）。
