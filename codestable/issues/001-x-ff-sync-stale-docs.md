---
kind: issue
title: "按代码和最新发版说明修正过时文档"
type: ff
status: closed
created: 2026-10-31
---

# 按代码和最新发版说明修正过时文档

整理 Project Spec 入口页时发现几份文档与代码、v0.1.32 发版说明对不上，按用户的决定修正：App 只在启动时检查一次更新；macOS 正式包已改用维护者的固定自签名证书；App 只安装自带运行时的 CLI 版本；平台验证范围不再停在 0.1.19。

- 改动：`desktop/PROTOCOL.md` 第 118 行、`docs/app-cli-boundary.md` 第 3 行 — App 更新检查从「启动和每 24 小时」改为每次启动一次；CLI 每 24 小时查 npm 的两处（`docs/app-cli-boundary.md` 第 17 行前半、`desktop/PROTOCOL.md` 第 126 行）没动
- 改动：`docs/app-cli-boundary.md` 第 17 行末句 — 去掉「正式 npm 0.1.24 尚为旧 Python 安装包」，改写成 App 按 `smartSearchBinary` 判断能否安装
- 改动：`README.md`、`README.zh-CN.md` — macOS 正式包从 ad-hoc 改为维护者的固定自签名证书，并链到 `docs/macos-signing.md`
- 改动：`PRODUCT.md` 第 9、41 行 — 去掉 0.1.19 的说法，验证范围以发版说明为准；签名写成两端沿用的自签名身份
- 验证：逐条对照 `AppUpdater.swift`、`MainWindow.xaml.cs`、两端的 `CLIInstallationManager`、`desktop-build.yml` 的签名模式和 v0.1.32 发版说明；`git diff --check` 通过
- codestable：无影响

顺手发现：「允许跳过指定版本」只有 macOS（Sparkle）做了，Windows 的更新弹窗只有「立即更新」和「稍后」；`docs/app-cli-boundary.md` 第 3 行和 `desktop/PROTOCOL.md` 第 118 行仍写成两端都能跳过，不在本次范围。
