---
kind: issue
title: "跳过版本只写 macOS，DSH README 标明实验性"
type: ff
status: closed
created: 2026-10-31
---

# 跳过版本只写 macOS，DSH README 标明实验性

接 `001-x-ff-sync-stale-docs.md` 的顺手发现：「允许跳过指定版本」只有 macOS（Sparkle）实现，两份文档改成只写 macOS；DSH 插件包按入口页的定位，在自己的 README 开头标明实验性。

- 改动：`desktop/PROTOCOL.md` 第 118 行、`docs/app-cli-boundary.md` 第 3 行 — 跳过版本只属于 macOS；Windows 只有“立即更新”和“稍后”
- 改动：`packages/smart-search-dsh/README.md` — 标题下加实验性说明，指向 Compatibility 一节
- 验证：对照 `MainWindow.xaml.cs` 第 700–701 行的更新弹窗（只有两个按钮）和 `AppUpdater.swift` 的 Sparkle 提示；按钮英文名取自共享译文；`check-package.mjs` 只查 README 是否随包，不查内容；`git diff --check` 通过
- codestable：无影响（入口页已把 DSH 标为实验性）
