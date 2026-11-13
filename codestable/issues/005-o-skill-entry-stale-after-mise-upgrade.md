---
kind: issue
title: "mise 安装的 CLI 升级后，自动维护停掉的 Skill 停在旧版本路径，CLI 看不出来"
type: bug
status: open
created: 2026-11-13
---

# mise 安装的 CLI 升级后，自动维护停掉的 Skill 停在旧版本路径，CLI 看不出来

## 做成以后是什么样

用 mise 的 npm 后端安装的 CLI 升级、旧版本目录被清掉以后，已接入的各 Agent 照 Skill 里写的命令仍能调用 CLI。如果某个目标因为文件被改过而不能自动维护，`smart-search skills status` 会直接说明，并给出接管命令；不再只有 App 能看到。

**范围：** 包含 Skill「本机独立 CLI」一节写入的调用入口，以及 `skills status` 对自动维护状态的报告。不包含 CC Switch 等外部工具的同步行为，这里只把它记作触发条件。

## 当前坏在哪

**预期：** `docs/app-cli-boundary.md` 写的是「安装的 Skill 使用稳定入口……自动维护仅针对用户已接入的目标，遇到个人修改保留文件并报告」。

**实际：** 2026-11-13，一台 Windows 电脑用 mise 的 npm 后端装了 0.1.34。`~/.claude/skills/smart-search-cli/SKILL.md` 的调用前缀还指向 0.1.25 的安装目录，而 mise 升级时已经删掉了这个目录，Claude Code 照 Skill 调用会失败。另一个 Agent 手工把各处 SKILL.md 改成 0.1.34 的路径后，`skills status` 对 claude 报 `extra_files`，看起来正常；但自动维护仍然把它判为 `personal_changes`，下次升级还会坏。

现场证据（本机文件和日志）。自动维护每改一次文件，就在 `%LOCALAPPDATA%/SmartSearchTools/skills/backups/` 留一份旧内容，下表的时间是这些备份目录的创建时间：

| 时间 | 发生了什么 | 证据 |
|---|---|---|
| 10-21 01:21 | 自动维护把 codex、claude、cursor 三个目标从 0.1.29 一起改成 0.1.31 的路径 | 三份同一时刻的备份；`state.json` 里 claude 回执的 `cli_version` 从此停在 0.1.31 |
| 10-29 08:16 | CC Switch 打开该 Skill 的 Claude、Codex 开关，把它 9-27 保存的快照（0.1.25 路径）同步过去；Codex 那份因为建不了符号链接，改成复制到 `~/.codex/skills` | CC Switch 日志：「Skill smart-search-cli 的 Claude 状态已更新为 true」，以及回退为文件复制的警告 |
| 10-29 08:35 | 升级到 0.1.32 后的第一次自动维护，只改了 codex、cursor，跳过 claude | 这一刻只有 codex、cursor 的备份 |
| 11-01 18:02、19:54 | 升级到 0.1.33、0.1.34，同样只改 codex、cursor；mise 的 installs 下只剩 0.1.34 | 备份；installs 目录列表 |
| 11-13 09:52 | 另一个 Agent 直接改写了 claude、gemini 的 SKILL.md，没有通过 `skills update`，回执没有更新 | 10:20 的自动维护仍报 claude `personal_changes`；回执哈希和文件哈希不一致 |

## 根因

1. **入口带版本号。** 「本机独立 CLI」一节的调用前缀来自 `SMART_SEARCH_PACKAGE_ROOT` 和 `SMART_SEARCH_NODE_PATH`（`skill_installer._local_skill_files`、`desktop_environment.invocation`）。App 管理的 CLI 装在 `SmartSearchTools/cli`，`npm -g` 装在全局前缀，这两种路径都不随版本变化。mise 的 npm 后端则是 `installs/npm-konbakuyomu-smart-search/<版本>/node_modules/.mise/@konbakuyomu+smart-search@<版本>/...`，Node 也是 `installs/node/<版本>/node.exe`。所以这条路径只有在每次升级都被自动维护重写时才有效，和「稳定入口」不符。
2. **自动维护一停就不再恢复，CLI 也不报告。** 文件哈希和回执不一致时，`skill_maintenance._maintain_locked` 记一条 `personal_changes`，以后一直跳过这个目标；这符合「个人修改优先」的设计。但这条结果只写进 `state.json`，只有 App 会显示（`desktop/windows/MainWindow.Skills.cs:79`、`desktop/macos/Sources/SmartSearchDesktop/ContentView.swift:1648`）。`skills status` 只拿文件和这一版 CLI 会写出的内容比，不看回执，所以不用 App 的用户和 Agent 都看不到维护已经停了。
3. **触发条件在外部。** 别的工具改写了 Skill 目录，产品拦不住。但有了 1 和 2，这个改写的后果要等下次升级才出现，而且出现时没有提示。

## 方向（未决定）

- **A. mise 安装时换成不随版本变化的入口**，例如 mise shims 目录里的 `smart-search`（`skill_maintenance._owner_identity` 已经能认出 mise 的安装目录）。动手前要穿刺：Agent 的工作目录里有别的 `mise.toml` 时，shim 是否仍然解析到全局版本；Windows 上 shim 是 `.exe` 还是 `.cmd`，各 Agent 能不能直接调用。
- **B. `skills status` 报告每个目标的维护状态**：已接入且回执一致、文件被改过（回执不一致）、未接入。文件被改过时提示 `smart-search skills update --targets <id>` 可以接管；Markdown 输出也要显示。
- **C.（可选）只修调用说明。** 自动维护发现只有「本机独立 CLI」一节不同、而且里面的路径已经不存在时，只更新这一节。这会放松「个人修改优先」的规则，需要单独决定。

建议先做 B：改动小，也不改变维护规则。A 要先穿刺 shim 的行为再定。

## 验证

- B：在临时 home 下登记目标、改动文件，`skills status` 显示「文件被改过」；运行 `skills update` 之后显示「已接入」。
- A：在隔离的 mise 环境里升级并清掉旧版本，不经过自动维护，直接用 Skill 里的命令调用新版本，能成功。
- 用原来坏的方式再看一眼：Windows 上 mise 升级以后，按各 Agent Skill 里写的完整调用前缀运行 `--version` 和一次搜索。

## 执行记录

2026-11-13，只处理了那台电脑，产品代码没有改：

- 运行 `smart-search skills update --targets claude,gemini`，文件内容没变（`changed_files` 为 0），回执重新登记；codex、claude、cursor、gemini 四个目标的回执哈希都等于文件哈希。
- 用 Skill 里的完整调用前缀运行 `--version`、`agent-guide` 和一次真实搜索，全部通过。
- 外部状态，已告知用户：CC Switch 里这个 Skill 的 Claude、Codex 开关仍然打开（它自己的说明写着不要用开关覆盖）；`~/.codex/skills/smart-search-cli` 是它复制到旧位置的副本，不在 CLI 的维护范围内，下次升级后会过期。

## 关闭时

- 回写候选：`codestable/spec/` 里写清 Skill 入口和自动维护现在怎样工作；如果选 A，同步改 `docs/app-cli-boundary.md` 对「稳定入口」的说法。
- 遗留：C 是否要做。
