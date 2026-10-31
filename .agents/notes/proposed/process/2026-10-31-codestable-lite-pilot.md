# Agent Note: 软件仓试点 CodeStable-Lite 做入口，知识同步门禁兜底

Status: proposed

## Problem

本仓没有"项目现在是什么"的常驻描述：`PRODUCT.md` 写定位，`DESIGN.md` 写桌面设计，`docs/` 下是逐项验收记录，新会话要靠读代码和 README 重建全局。改动由本地与云端多个会话提交，最近 9 个合并的 PR 都来自云端会话的 `claude/*` 分支；文档是否随代码更新没有任何约束，近两个月的改动也都没有走仓里遗留的 Comet 配置。v0.1.18 把 `.trellis/`、`.codestable/` 和 Trellis 的 AGENTS.md 块当作本地写作辅助删掉以后，仓里没有任何给代理看的项目说明。

## Proposal

以 CodeStable-Lite 的 `/cs` 为唯一入口：`codestable/spec/` 保存当前仍成立的现状与边界，Issue 与 `ff` 记每次改动，坑点进 `codestable/notes/`，决定仍写本目录（write-notes-like-deepseek 格式）。`.arch-check.json` 列出结构路径（`src`、`desktop/windows`、`desktop/macos`、`npm`、`packages`），pre-commit 用 dev-board 的 arch-check 把关：结构变了，规格或笔记必须同提交跟上，或者本次 `ff` 写明影响。

云端会话只读得到仓里的东西，所以 `AGENTS.md`、`codestable/`、`.githooks/`、`.claude/settings.json` 和本目录都进仓：`.gitignore` 对 `.agents/`、`.claude/` 改成整目录忽略、只放行这两处。它们都不在 npm 包的 `files` 白名单里。`/cs` 技能本身不进仓：`.claude/settings.json` 的 SessionStart hook 运行 `.githooks/ensure-cs.mjs`，在云端会话里按固定提交 `bf8ecc8` 从上游取到 `.claude/skills/cs`，并启用 `.githooks`；本机 Windows 检出已有同一提交的副本，hook 不做任何事。试点两周后按验收标准决定推广到第二个仓还是退回。

## Alternatives considered

- **Matt 的 spec/tickets 流程** — 最强理由是已在板子仓验证、零 hook。不选是因为它要人记住何时用哪个技能，而本仓改动多且小，`/cs` 的姿态路由把这一步交给模型。
- **继续 Comet Native** — 最强理由是仓里仍有 `.comet/config.yaml`，不用换。不选是因为按阶段禁止写入对强模型是返工成本（看板氡监测仪卡 2026-10-20 的复盘：一个 change 5 轮约 5 小时），且本仓近两月的改动都没有走它。
- **只靠约定不设门禁** — 最强理由是零摩擦。不选是因为同批不改文档的债基本不会补，园丁只能发现不能阻止。
- **把 `cs` 技能提交进本仓** — 最强理由是不依赖网络，版本跟着仓走。不选是因为 CodeStable-Lite 上游没有许可证，本仓公开，提交就是再分发；按固定提交现取同样钉死版本，在云端容器里实测约 2 秒装好，取到的 `SKILL.md` 与本机副本哈希一致。
- **试点期间只在 Windows 检出上做，不合进 main** — 最强理由是不动公开仓的默认分支。不选是因为本仓的改动主要来自云端会话，它们克隆 main，读不到分支上的规则。

## Acceptance criteria

两周内：`codestable/` 的文件数与行数可数；至少一次 Issue 或 `ff` 真正改了 `codestable/spec/`；一个全新会话只读 `codestable/` 与代码能答对"现在是什么、为什么这样、踩过什么坑"；门禁至少拦下并被按提示修复一次，而不是用 `ARCH_CHECK=skip` 绕过；至少一个云端会话里 `/cs` 可用、pre-commit 生效。

## Risks

每个小改一个 `ff` 文件，目录会长，按需用 arch-check 的 `tidy` 整理；结构路径过宽会误拦，`.arch-check.json` 可调。SessionStart 现取要求会话能访问 github.com，访问不了时 hook 只提示、不挡会话，那次会话没有 `/cs`。会话开始后才出现的技能可能不进那次会话的技能列表（2026-10-31 在一个云端会话里实测，中途新建的项目技能调不到），所以 hook 的提示让模型直接读 `SKILL.md`。公开仓里的 hook 也会在别人的 Claude Code 里运行：现取只在云端会话里自动发生，本地只提示。合进 main 的那次推送带 `[skip ci]`，避免 `publish-npm.yml` 为纯文档改动发一个 npm beta 和 GitHub 预发布。
